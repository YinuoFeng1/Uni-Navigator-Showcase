from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from app.config import PROJECT_ROOT, get_settings
from app.core.container import build_application_container
from app.services.ai_provider import prompt_fingerprint
from app.services.technical_evaluation import (
    evaluate_technical_records,
    load_technical_evaluation_dataset,
    write_manual_review_csv,
)
from app.services.technical_evaluation_service import (
    JsonlTechnicalEvaluationRepository,
    TechnicalEvaluationService,
)


DEFAULT_DATASET_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "end_to_end_technical_evaluation.json"
)
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "data" / "evaluation" / "results"


def run_batch(
    *,
    dataset_path: Path,
    run_id: str,
    repetitions: int,
    output_dir: Path,
    partition: str = "dev",
) -> dict:
    if repetitions < 2:
        raise ValueError("repetitions must be at least 2 to measure answer variation")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", run_id):
        raise ValueError("run_id may contain only letters, numbers, dot, underscore and hyphen")
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"technical_evaluation_{run_id}_{partition}.json"
    review_path = (
        output_dir / f"technical_evaluation_{run_id}_{partition}_manual_review.csv"
    )
    if report_path.exists() or review_path.exists():
        raise FileExistsError(
            f"technical evaluation output already exists for run_id={run_id}"
        )
    dataset = load_technical_evaluation_dataset(
        dataset_path,
        partition=partition,
    )
    settings = get_settings()
    if _jsonl_contains_run_id(
        settings.technical_evaluation_output_path,
        run_id,
        partition=partition,
    ):
        raise FileExistsError(
            f"technical evaluation log already contains run_id={run_id}"
        )
    container = build_application_container(settings)
    service = TechnicalEvaluationService(
        container.chat_orchestrator,
        JsonlTechnicalEvaluationRepository(
            settings.technical_evaluation_output_path
        ),
    )

    records = []
    total = len(dataset["questions"]) * repetitions
    completed = 0
    for question in dataset["questions"]:
        for repetition in range(1, repetitions + 1):
            record = service.run(
                run_id=run_id,
                query_id=str(question["question_id"]),
                question=str(question["question"]),
                repetition=repetition,
                task_id=str(question.get("task_id") or "") or None,
                partition=partition,
            )
            records.append(record)
            completed += 1
            print(
                f"[{completed}/{total}] {record.query_id} repetition={repetition} "
                f"status={record.status} retrieval={record.retrieval_status or '-'}"
            )

    evaluation = evaluate_technical_records(records, dataset["questions"])
    report = {
        "schema_version": "2.0",
        "run_id": run_id,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(dataset_path),
        "dataset_version": dataset.get("dataset_version"),
        "partition": partition,
        "partition_version": dataset.get("partition_version"),
        "partition_method": dataset.get("partition_method"),
        "partition_counts": dataset.get("partition_counts"),
        "repetitions": repetitions,
        "runtime_config": container.runtime.canonical_dict(),
        "runtime_config_fingerprint": container.runtime.runtime_config_fingerprint,
        "fingerprints": _build_fingerprints(
            dataset_path=dataset_path,
            dataset=dataset,
            runtime=container.runtime,
        ),
        **evaluation,
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    write_manual_review_csv(review_path, evaluation["attempts"])
    report["report_file"] = str(report_path)
    report["manual_review_file"] = str(review_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run the versioned end-to-end live RAG technical evaluation. "
            "This makes billable OpenAI embedding and answer requests."
        )
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET_PATH)
    parser.add_argument("--run-id", default=_default_run_id())
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument(
        "--partition",
        choices=("dev", "holdout"),
        default="dev",
        help="Run the 35-question development set or 15-question holdout set.",
    )
    parser.add_argument(
        "--confirm-live-run",
        action="store_true",
        help="Confirm that the billable live OpenAI evaluation should run.",
    )
    args = parser.parse_args()
    if not args.confirm_live_run:
        parser.error("--confirm-live-run is required for billable live evaluation")

    report = run_batch(
        dataset_path=args.dataset,
        run_id=args.run_id,
        repetitions=args.repetitions,
        output_dir=args.output_dir,
        partition=args.partition,
    )
    print("\nUni-Navigator end-to-end technical evaluation")
    print(f"partition: {report['partition']}")
    print(f"questions: {report['question_count']}")
    print(f"attempts: {report['attempt_count']}")
    print(f"success_rate: {report['metrics']['success_rate']}")
    print(
        "expected_source_in_top_k_rate: "
        f"{report['metrics']['expected_source_in_top_k_rate']}"
    )
    print(
        "mean_pairwise_answer_similarity: "
        f"{report['variation']['mean_pairwise_answer_similarity']}"
    )
    print(f"report_file: {report['report_file']}")
    print(f"manual_review_file: {report['manual_review_file']}")
    return 0


def _default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _jsonl_contains_run_id(
    path: Path,
    run_id: str,
    *,
    partition: str | None = None,
) -> bool:
    if not path.exists():
        return False
    with path.open("r", encoding="utf-8") as source:
        for line in source:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(payload, dict) or payload.get("run_id") != run_id:
                continue
            recorded_partition = payload.get("partition")
            if partition is None or recorded_partition in {None, partition}:
                return True
    return False


def _build_fingerprints(
    *,
    dataset_path: Path,
    dataset: dict[str, Any],
    runtime: Any,
) -> dict[str, Any]:
    return {
        "dataset": {
            "version": dataset.get("dataset_version"),
            "sha256": _file_fingerprint(dataset_path),
            "partition": dataset.get("partition"),
            "partition_version": dataset.get("partition_version"),
            "selected_question_ids_sha256": _json_fingerprint(
                [question["question_id"] for question in dataset["questions"]]
            ),
        },
        "code": {
            "git_commit": _git_commit(PROJECT_ROOT),
            "app_revision": runtime.app_revision,
            "backend_source_sha256": _source_tree_fingerprint(
                PROJECT_ROOT / "backend" / "app"
            ),
        },
        "prompt": {
            "version": runtime.prompt_template_version,
            "sha256": prompt_fingerprint(runtime.prompt_template_version),
        },
        "corpus": {
            "sha256": runtime.corpus_fingerprint,
            "manifest_version": runtime.corpus_manifest_version,
            "embedding_provider": runtime.embedding_provider,
            "embedding_model": runtime.embedding_model,
            "vector_collection": runtime.vector_store_collection,
        },
        "scope_registry": {
            "version": runtime.scope_registry_version,
            "sha256": runtime.scope_registry_fingerprint,
        },
        "runtime_config": {
            "sha256": runtime.runtime_config_fingerprint,
        },
    }


def _file_fingerprint(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _json_fingerprint(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


def _source_tree_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    for source_path in sorted(path.rglob("*.py")):
        digest.update(source_path.relative_to(path).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(source_path.read_bytes())
        digest.update(b"\0")
    return f"sha256:{digest.hexdigest()}"


def _git_commit(project_root: Path) -> str | None:
    git_dir = project_root / ".git"
    head_path = git_dir / "HEAD"
    if not head_path.is_file():
        return None
    head = head_path.read_text(encoding="utf-8").strip()
    if not head.startswith("ref: "):
        return head or None
    ref = head.removeprefix("ref: ")
    ref_path = git_dir / ref
    if ref_path.is_file():
        return ref_path.read_text(encoding="utf-8").strip() or None
    packed_refs = git_dir / "packed-refs"
    if packed_refs.is_file():
        for line in packed_refs.read_text(encoding="utf-8").splitlines():
            if line.startswith("#") or line.startswith("^"):
                continue
            commit, _, packed_ref = line.partition(" ")
            if packed_ref == ref:
                return commit
    return None


if __name__ == "__main__":
    raise SystemExit(main())
