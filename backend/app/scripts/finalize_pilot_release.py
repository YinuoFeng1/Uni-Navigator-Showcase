from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from app.config import PROJECT_ROOT, get_settings
from app.services.experimental_condition_service import ExperimentalConditionService
from app.services.pilot_release_service import (
    PilotReleaseService,
    build_frozen_release_artifacts,
)
from app.services.vector_store import get_vector_store


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Review and freeze the complete pilot system configuration."
    )
    parser.add_argument("--approval-file", required=True, type=Path)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the frozen release and active release pointer.",
    )
    args = parser.parse_args()

    settings = get_settings()
    approval_path = (
        args.approval_file
        if args.approval_file.is_absolute()
        else PROJECT_ROOT / args.approval_file
    )
    approval = _load_json(approval_path)
    condition_service = ExperimentalConditionService(settings.condition_manifest_path)
    release_service = PilotReleaseService(
        settings.pilot_release_manifest_path,
        settings.active_pilot_release_path,
    )
    condition_report = condition_service.validate()
    if not condition_report.valid:
        raise SystemExit(
            "Pilot release cannot be frozen because condition validation failed."
        )

    release_manifest = release_service.load_manifest()
    release_service.validate_runtime_binding(
        release=release_manifest,
        settings=settings,
        vector_status=get_vector_store(settings).status(),
    )
    artifacts = build_frozen_release_artifacts(
        condition_manifest=condition_service.load_manifest(),
        release_manifest=release_manifest,
        approval_record=approval,
    )
    _validate_artifacts(artifacts)

    if args.apply:
        _write_json_atomic(settings.pilot_release_manifest_path, artifacts.release)
        _write_json_atomic(settings.active_pilot_release_path, artifacts.active_pointer)

    print(
        json.dumps(
            {
                "applied": args.apply,
                "releaseId": artifacts.release["release_id"],
                "releaseVersion": artifacts.release["release_version"],
                "releaseStatus": artifacts.release["release_status"],
                "answerMode": artifacts.release["selected_answer_mode"],
                "aiProvider": artifacts.release["ai_provider"],
                "aiModel": artifacts.release["ai_model"],
                "reviewer": artifacts.release["reviewed_by"],
                "nextAction": (
                    "Run pilot_preflight with the frozen configuration."
                    if args.apply
                    else "Review this dry run, then repeat with --apply."
                ),
            },
            indent=2,
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0


def _validate_artifacts(artifacts: Any) -> None:
    with tempfile.TemporaryDirectory(prefix="uni-navigator-release-") as directory:
        root = Path(directory)
        release_path = root / "release.json"
        pointer_path = root / "pointer.json"
        _write_json_atomic(release_path, artifacts.release)
        _write_json_atomic(pointer_path, artifacts.active_pointer)

        release_service = PilotReleaseService(release_path, pointer_path)
        release_report = release_service.validate(
            condition_manifest_checksum=artifacts.release[
                "condition_manifest_checksum"
            ],
        )
        release_service.resolve_active_release(require_frozen=True)
        if not release_report.valid or release_report.warnings:
            raise SystemExit("Finalized pilot release failed lifecycle validation.")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Approval record unavailable: {path}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Approval record must be a JSON object.")
    return payload


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        temporary = Path(handle.name)
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
    os.replace(temporary, path)


if __name__ == "__main__":
    raise SystemExit(main())
