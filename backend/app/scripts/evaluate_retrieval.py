import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import PROJECT_ROOT, get_settings
from app.services.policy_safety import assess_policy_safety
from app.services.corpus_scope_service import (
    apply_scope_to_retrieval_status,
    decide_corpus_scope,
    load_scope_registry,
)
from app.services.escalation_service import decide_escalation_category
from app.services.retrieval_service import (
    classify_retrieval_status,
    get_corpus_status,
    retrieve_policy_chunks,
)

DEFAULT_QUESTIONS_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "official_retrieval_evaluation.json"
)
RESULTS_DIR = PROJECT_ROOT / "data" / "evaluation" / "results"


def load_evaluation_questions(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("Retrieval evaluation file must contain a JSON list")
    questions = [item for item in payload if isinstance(item, dict)]
    if not questions:
        raise ValueError("Retrieval evaluation file contains no questions")
    return questions


def evaluate_retrieval(
    question_path: Path = DEFAULT_QUESTIONS_PATH,
    output_path: Path | None = None,
    source_mode: str = "official",
    top_k: int = 5,
) -> dict[str, Any]:
    settings = get_settings()
    questions = load_evaluation_questions(question_path)
    corpus_status = get_corpus_status(settings)
    scope_registry = load_scope_registry(settings.scope_registry_path)
    rows: list[dict[str, Any]] = []

    for question in questions:
        text = str(question.get("question") or "")
        expected = {
            str(source_id)
            for source_id in question.get("expected_source_ids", [])
            if source_id
        }
        acceptable = {
            str(source_id)
            for source_id in question.get("acceptable_source_ids", [])
            if source_id
        }
        relevant = expected | acceptable
        results = retrieve_policy_chunks(
            text,
            top_k=top_k,
            settings=settings,
            source_mode=source_mode,
        )
        raw_status = classify_retrieval_status(results, settings=settings)
        scope_decision = decide_corpus_scope(
            text,
            results,
            scope_registry,
            partial_threshold=settings.retrieval_partial_score_threshold,
            grounded_threshold=settings.retrieval_grounded_score_threshold,
        )
        status = apply_scope_to_retrieval_status(raw_status, scope_decision)
        retrieved_ids = [str(item.get("source_id") or "") for item in results]
        ranks = [
            index
            for index, source_id in enumerate(retrieved_ids, start=1)
            if source_id in relevant
        ]
        reciprocal_rank = 1 / min(ranks) if ranks else 0.0
        page_match = _page_range_match(
            results,
            question.get("expected_page_ranges", []),
        )
        matching_text = " ".join(
            str(item.get("chunk_text") or "").lower()
            for item in results
            if item.get("source_id") in relevant
        )
        missing_keywords = [
            keyword
            for keyword in question.get("expected_keywords", [])
            if str(keyword).lower() not in matching_text
        ]
        safety = assess_policy_safety(text)
        escalation_decision = decide_escalation_category(
            question=text,
            retrieval_status=status,
            scope_decision=scope_decision,
            high_stakes_detected=safety.high_stakes_detected,
            safety_categories=safety.categories,
        )
        escalation = escalation_decision.recommended
        expected_escalation = question.get("expected_escalation")
        expected_escalation_category = _expected_escalation_category(question)
        acceptable_escalation_categories = {
            str(item)
            for item in question.get("acceptable_escalation_categories", [])
        }
        escalation_pass = escalation_decision.category in {
            expected_escalation_category,
            *acceptable_escalation_categories,
        }
        expected_status = str(question.get("expected_retrieval_status") or "")
        scope_label = str(question.get("scope_label") or "in_corpus")
        no_result_expected = scope_label in {
            "out_of_domain",
            "university_admin_but_out_of_corpus",
        }
        no_result_correct = no_result_expected and status == "insufficient_evidence"
        hit_at_5 = bool(ranks and min(ranks) <= 5)
        retrieval_reasons: list[str] = []
        evidence_reasons: list[str] = []
        if scope_label == "in_corpus" and relevant and not hit_at_5:
            retrieval_reasons.append("expected source absent from top 5")
        if no_result_expected and not no_result_correct:
            retrieval_reasons.append(
                "out-of-corpus question was not classified as insufficient"
            )
        if expected_status and status != expected_status:
            retrieval_reasons.append(f"status {status} != expected {expected_status}")
        if missing_keywords:
            evidence_reasons.append(
                "missing expected keywords: " + ", ".join(missing_keywords)
            )
        if question.get("expected_page_ranges") and not page_match:
            evidence_reasons.append("expected page range not retrieved")
        scope_pass = _scope_pass(scope_label, scope_decision.decision)
        scope_reasons = (
            []
            if scope_pass
            else [
                f"scope decision {scope_decision.decision} did not match label {scope_label}"
            ]
        )
        retrieval_pass = not retrieval_reasons
        evidence_support_pass = not evidence_reasons
        overall_pass = retrieval_pass and scope_pass and evidence_support_pass

        rows.append(
            {
                "question_id": question.get("question_id"),
                "question": text,
                "task_category": question.get("task_category"),
                "difficulty": question.get("difficulty"),
                "scope_label": scope_label,
                "scope_decision": scope_decision.decision,
                "scope_matched_topics": scope_decision.matched_topics,
                "scope_supporting_source_ids": scope_decision.supporting_source_ids,
                "scope_reasons": scope_decision.reasons,
                "scope_rule_signals": scope_decision.rule_signals,
                "scope_retrieval_signals": scope_decision.retrieval_signals,
                "scope_confidence_category": scope_decision.confidence_category,
                "scope_registry_version": scope_decision.registry_version,
                "expected_source_ids": sorted(expected),
                "acceptable_source_ids": sorted(acceptable),
                "expected_page_ranges": question.get("expected_page_ranges", []),
                "retrieved_source_ids": retrieved_ids,
                "retrieved_source_types": [
                    item.get("source_type") for item in results
                ],
                "ranks": ranks,
                "scores": [item.get("score") for item in results],
                "page_ranges": [
                    {
                        "source_id": item.get("source_id"),
                        "page_start": item.get("page_start"),
                        "page_end": item.get("page_end"),
                    }
                    for item in results
                ],
                "raw_retrieval_status": raw_status,
                "retrieval_status": status,
                "reciprocal_rank": reciprocal_rank,
                "hit_at_1": bool(ranks and min(ranks) <= 1),
                "hit_at_3": bool(ranks and min(ranks) <= 3),
                "hit_at_5": hit_at_5,
                "page_range_match": page_match,
                "no_result_correct": no_result_correct,
                "escalation_recommended": escalation,
                "expected_escalation": expected_escalation,
                "expected_escalation_category": expected_escalation_category,
                "acceptable_escalation_categories": sorted(
                    acceptable_escalation_categories
                ),
                "escalation_category": escalation_decision.category,
                "escalation_category_pass": escalation_pass,
                "prepared_source_leakage": sum(
                    item.get("source_type") == "prepared_policy" for item in results
                ),
                "inactive_source_retrieval": sum(
                    item.get("active") is False for item in results
                ),
                "retrieval_pass": retrieval_pass,
                "scope_pass": scope_pass,
                "evidence_support_pass": evidence_support_pass,
                "pass": overall_pass,
                "failure_reasons": [
                    *retrieval_reasons,
                    *scope_reasons,
                    *evidence_reasons,
                ],
            }
        )

    summary = _summary(rows)
    result = {
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "question_file": str(question_path),
        "question_count": len(questions),
        "source_mode": source_mode,
        "top_k": top_k,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "active_collection": corpus_status.get("activeCollection"),
        "embedding_dimension": corpus_status.get("embeddingDimension"),
        "partial_score_threshold": settings.retrieval_partial_score_threshold,
        "grounded_score_threshold": settings.retrieval_grounded_score_threshold,
        "corpus_status": corpus_status,
        "metrics": summary,
        "questions": rows,
    }
    target = output_path or _default_output_path(settings.embedding_provider)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    result["result_file"] = str(target)
    _print_report(result)
    return result


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    in_scope = [row for row in rows if _row_scope_label(row) == "in_corpus"]
    out_of_scope = [
        row
        for row in rows
        if _row_scope_label(row)
        in {"out_of_domain", "university_admin_but_out_of_corpus"}
    ]
    out_of_domain = [
        row for row in rows if _row_scope_label(row) == "out_of_domain"
    ]
    admin_out = [
        row
        for row in rows
        if _row_scope_label(row) == "university_admin_but_out_of_corpus"
    ]
    ambiguous = [
        row for row in rows if _row_scope_label(row) == "ambiguous_scope"
    ]
    page_labelled = [row for row in in_scope if row["expected_page_ranges"]]
    relevant_scores = [
        row["scores"][min(row["ranks"]) - 1]
        for row in in_scope
        if row["ranks"] and row["scores"][min(row["ranks"]) - 1] is not None
    ]
    out_scores = [
        row["scores"][0]
        for row in out_of_scope
        if row["scores"] and row["scores"][0] is not None
    ]
    retrieved_slots = [
        (source_id, set(row["expected_source_ids"]) | set(row["acceptable_source_ids"]))
        for row in in_scope
        for source_id in row["retrieved_source_ids"]
    ]
    return {
        "pass_count": sum(row["pass"] for row in rows),
        "failure_count": sum(not row["pass"] for row in rows),
        "in_corpus_hit_at_1": _mean(row["hit_at_1"] for row in in_scope),
        "in_corpus_hit_at_3": _mean(row["hit_at_3"] for row in in_scope),
        "in_corpus_hit_at_5": _mean(row["hit_at_5"] for row in in_scope),
        "in_corpus_mean_reciprocal_rank": _mean(
            row["reciprocal_rank"] for row in in_scope
        ),
        "hit_at_1": _mean(row["hit_at_1"] for row in in_scope),
        "hit_at_3": _mean(row["hit_at_3"] for row in in_scope),
        "hit_at_5": _mean(row["hit_at_5"] for row in in_scope),
        "mean_reciprocal_rank": _mean(row["reciprocal_rank"] for row in in_scope),
        "no_result_accuracy": _mean(
            row["no_result_correct"] for row in out_of_scope
        ),
        "out_of_corpus_rejection_accuracy": _mean(
            row["no_result_correct"]
            and row.get("scope_decision", "out_of_scope") == "out_of_scope"
            for row in out_of_scope
        ),
        "out_of_domain_rejection_accuracy": _mean(
            row["no_result_correct"]
            and row.get("scope_decision", "out_of_scope") == "out_of_scope"
            for row in out_of_domain
        ),
        "university_admin_but_out_of_corpus_rejection_accuracy": _mean(
            row["no_result_correct"]
            and row.get("scope_decision", "out_of_scope") == "out_of_scope"
            for row in admin_out
        ),
        "ambiguous_scope_accuracy": _mean(
            row.get("scope_decision") == "ambiguous"
            and row.get("retrieval_status") == "ambiguous"
            for row in ambiguous
        ),
        "false_grounded_rate_out_of_corpus": _mean(
            row.get("retrieval_status") == "grounded" for row in out_of_scope
        ),
        "false_partial_rate_out_of_corpus": _mean(
            row.get("retrieval_status") == "partial_evidence" for row in out_of_scope
        ),
        "false_insufficient_rate_in_corpus": _mean(
            row.get("retrieval_status") == "insufficient_evidence" for row in in_scope
        ),
        "official_source_precision": _mean(
            source_id in relevant for source_id, relevant in retrieved_slots
        ),
        "prepared_source_leakage_count": sum(
            row["prepared_source_leakage"] for row in rows
        ),
        "inactive_source_retrieval_count": sum(
            row["inactive_source_retrieval"] for row in rows
        ),
        "page_range_match_rate": _mean(
            row["page_range_match"] for row in page_labelled
        ),
        "page_support_accuracy": _mean(
            row["page_range_match"] for row in page_labelled
        ),
        "escalation_category_accuracy": _mean(
            row.get("escalation_category_pass", True) for row in rows
        ),
        "scope_confusion_matrix": _scope_confusion_matrix(rows),
        "relevant_score_distribution": _distribution(relevant_scores),
        "out_of_corpus_score_distribution": _distribution(out_scores),
        "threshold_separation": _threshold_separation(relevant_scores, out_scores),
    }


def _scope_pass(scope_label: str, decision: str) -> bool:
    if scope_label == "in_corpus":
        return decision in {"in_scope", "possibly_in_scope"}
    if scope_label == "ambiguous_scope":
        return decision == "ambiguous"
    return decision == "out_of_scope"


def _expected_escalation_category(question: dict[str, Any]) -> str:
    explicit = question.get("expected_escalation_category")
    if explicit:
        return str(explicit)
    if question.get("expected_escalation") is False:
        return "none"
    category = str(question.get("task_category") or "")
    if category == "examinations":
        return "contact_examinations"
    if category in {"academic_progression", "ambiguous"}:
        return "contact_authorised_university_staff"
    return "contact_faculty_or_student_centre"


def _scope_confusion_matrix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    matrix: dict[str, dict[str, int]] = {}
    for row in rows:
        expected = _row_scope_label(row)
        predicted = str(row.get("scope_decision") or "not_recorded")
        matrix.setdefault(expected, {})
        matrix[expected][predicted] = matrix[expected].get(predicted, 0) + 1
    return matrix


def _row_scope_label(row: dict[str, Any]) -> str:
    explicit = row.get("scope_label")
    if explicit:
        return str(explicit)
    return (
        "in_corpus"
        if row.get("expected_source_ids")
        else "university_admin_but_out_of_corpus"
    )


def _page_range_match(results: list[dict], labels: Any) -> bool:
    if not isinstance(labels, list) or not labels:
        return True
    for label in labels:
        if not isinstance(label, dict):
            continue
        for result in results:
            if result.get("source_id") != label.get("source_id"):
                continue
            page_start = result.get("page_start")
            page_end = result.get("page_end")
            if not isinstance(page_start, int) or not isinstance(page_end, int):
                continue
            if page_start <= int(label["page_end"]) and page_end >= int(
                label["page_start"]
            ):
                return True
    return False


def _mean(values: Any) -> float | None:
    numbers = [float(value) for value in values]
    return round(sum(numbers) / len(numbers), 4) if numbers else None


def _distribution(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"min": None, "median": None, "max": None}
    return {
        "min": round(min(values), 4),
        "median": round(statistics.median(values), 4),
        "max": round(max(values), 4),
    }


def _threshold_separation(
    relevant_scores: list[float],
    out_scores: list[float],
) -> dict[str, Any]:
    if not relevant_scores or not out_scores:
        return {"separated": None, "suggested_midpoint": None}
    minimum_relevant = min(relevant_scores)
    maximum_out = max(out_scores)
    separated = minimum_relevant > maximum_out
    return {
        "separated": separated,
        "minimum_relevant_score": round(minimum_relevant, 4),
        "maximum_out_of_corpus_score": round(maximum_out, 4),
        "suggested_midpoint": (
            round((minimum_relevant + maximum_out) / 2, 4)
            if separated
            else None
        ),
    }


def _default_output_path(provider: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return RESULTS_DIR / f"official_retrieval_{provider}_{timestamp}.json"


def _print_report(result: dict[str, Any]) -> None:
    print("Uni-Navigator retrieval evaluation")
    print(f"questions: {result['question_count']}")
    print(f"provider: {result['embedding_provider']}")
    print(f"model: {result['embedding_model']}")
    print(f"collection: {result['active_collection']}")
    for row in result["questions"]:
        outcome = "PASS" if row["pass"] else "FAIL"
        print(
            f"{outcome} {row['question_id']}: "
            f"sources={row['retrieved_source_ids']} ranks={row['ranks']} "
            f"scores={row['scores']} pages={row['page_ranges']}"
        )
        if row["failure_reasons"]:
            print("  reasons: " + "; ".join(row["failure_reasons"]))
    metrics = result["metrics"]
    print(
        "summary: "
        f"Hit@1={metrics['hit_at_1']} Hit@3={metrics['hit_at_3']} "
        f"Hit@5={metrics['hit_at_5']} MRR={metrics['mean_reciprocal_rank']} "
        f"out_rejection={metrics['out_of_corpus_rejection_accuracy']} "
        f"ambiguous_accuracy={metrics['ambiguous_scope_accuracy']} "
        f"false_grounded={metrics['false_grounded_rate_out_of_corpus']}"
    )
    print(f"result_file: {result['result_file']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate Uni-Navigator policy retrieval"
    )
    parser.add_argument("--question-file", type=Path, default=DEFAULT_QUESTIONS_PATH)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--source-mode",
        choices=["all", "prepared", "official", "prefer_official"],
        default="official",
    )
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()
    evaluate_retrieval(
        question_path=args.question_file,
        output_path=args.output,
        source_mode=args.source_mode,
        top_k=args.top_k,
    )


if __name__ == "__main__":
    main()
