from __future__ import annotations

import csv
from dataclasses import asdict
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
from statistics import mean, median
from typing import Any, Iterable

from app.services.technical_evaluation_service import TechnicalEvaluationRecord


QUESTION_TYPES = {
    "standard",
    "paraphrase",
    "ambiguous",
    "out_of_scope",
    "high_risk",
}
EXPECTED_SCOPES = {"in_scope", "ambiguous", "out_of_scope"}
PARTITIONS = ("dev", "holdout")
MANUAL_REVIEW_FIELDS = (
    "answers_question",
    "citations_support_conclusions",
    "unsupported_rule_present",
    "uncertainty_appropriate",
    "escalation_appropriate",
)


def load_technical_evaluation_dataset(
    path: Path,
    *,
    partition: str | None = None,
) -> dict[str, Any]:
    if partition is not None and partition not in PARTITIONS:
        raise ValueError("partition must be dev or holdout")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("technical evaluation dataset must contain a cases list")

    questions: list[dict[str, Any]] = []
    for case in payload["cases"]:
        if not isinstance(case, dict) or not isinstance(case.get("questions"), list):
            raise ValueError("each technical evaluation case must contain questions")
        defaults = {key: value for key, value in case.items() if key != "questions"}
        for question in case["questions"]:
            if not isinstance(question, dict):
                raise ValueError("each technical evaluation question must be an object")
            questions.append({**defaults, **question})

    _validate_questions(questions)
    partitions = _validate_partitions(payload.get("partitions"), questions)
    partition_by_id = {
        question_id: partition_name
        for partition_name in PARTITIONS
        for question_id in partitions[partition_name]
    }
    questions = [
        {**question, "partition": partition_by_id[str(question["question_id"])]}
        for question in questions
    ]
    selected_questions = (
        [question for question in questions if question["partition"] == partition]
        if partition
        else questions
    )
    return {
        "schema_version": payload.get("schema_version"),
        "dataset_version": payload.get("dataset_version"),
        "purpose": payload.get("purpose"),
        "partition": partition or "all",
        "partition_version": partitions["version"],
        "partition_method": partitions["method"],
        "partition_counts": {
            name: len(partitions[name]) for name in sorted(PARTITIONS)
        },
        "questions": selected_questions,
    }


def evaluate_technical_records(
    records: list[TechnicalEvaluationRecord],
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    expectations = {str(item["question_id"]): item for item in questions}
    rows = [
        _evaluate_record(record, expectations[record.query_id])
        for record in records
        if record.query_id in expectations
    ]
    return {
        "attempt_count": len(rows),
        "question_count": len({row["question_id"] for row in rows}),
        "metrics": _metric_summary(rows),
        "variation": _variation_summary(rows),
        "attempts": rows,
    }


def write_manual_review_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "run_id",
        "question_id",
        "repetition",
        "source_case_id",
        "partition",
        "question_type",
        "question",
        "status",
        "error_type",
        "error_detail",
        "latency_ms",
        "citation_validation_retry_count",
        "review_criteria",
        "review_focus",
        "answer",
        "retrieval_status",
        "scope_decision",
        "expected_scope",
        "expected_escalation",
        "escalation_recommended",
        "escalation_outcome",
        "citation_summary",
        "expected_source_in_top_k",
        "expected_page_in_top_k",
        "expected_source_cited",
        "expected_page_cited",
        "scope_match",
        "escalation_match",
        *MANUAL_REVIEW_FIELDS,
        "reviewer_id",
        "review_notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{key: row.get(key) for key in fieldnames},
                    "citation_validation_retry_count": (
                        row.get("provenance") or {}
                    ).get("citation_validation_retry_count", 0),
                    "citation_summary": _citation_summary(row.get("citations", [])),
                    **{field: "" for field in MANUAL_REVIEW_FIELDS},
                    "reviewer_id": "",
                    "review_notes": "",
                }
            )


def summarize_manual_review(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    if not rows:
        raise ValueError("manual review CSV contains no rows")

    allowed = {
        "answers_question": {"yes", "partial", "no"},
        "citations_support_conclusions": {"yes", "partial", "no", "not_applicable"},
        "unsupported_rule_present": {"yes", "no", "unclear"},
        "uncertainty_appropriate": {"yes", "partial", "no"},
        "escalation_appropriate": {"yes", "partial", "no"},
    }
    result: dict[str, Any] = {"reviewed_attempt_count": len(rows), "metrics": {}}
    for field, accepted in allowed.items():
        values = [str(row.get(field) or "").strip().lower() for row in rows]
        invalid = sorted({value for value in values if value and value not in accepted})
        if invalid:
            raise ValueError(f"invalid {field} rating(s): {', '.join(invalid)}")
        completed = [value for value in values if value]
        counts = {value: completed.count(value) for value in sorted(accepted)}
        result["metrics"][field] = {
            "completed": len(completed),
            "missing": len(values) - len(completed),
            "counts": counts,
            "yes_rate": _rate(counts.get("yes", 0), len(completed)),
        }
    return result


def _validate_questions(questions: list[dict[str, Any]]) -> None:
    if not 40 <= len(questions) <= 60:
        raise ValueError("technical evaluation dataset must contain 40 to 60 questions")
    ids = [str(item.get("question_id") or "") for item in questions]
    if any(not item for item in ids) or len(ids) != len(set(ids)):
        raise ValueError("technical evaluation question IDs must be present and unique")

    present_types: set[str] = set()
    for item in questions:
        question = str(item.get("question") or "").strip()
        question_type = str(item.get("question_type") or "")
        expected_scope = str(item.get("expected_scope") or "")
        if not question:
            raise ValueError(f"question {item['question_id']} has no text")
        if question_type not in QUESTION_TYPES:
            raise ValueError(f"question {item['question_id']} has invalid type")
        if expected_scope not in EXPECTED_SCOPES:
            raise ValueError(f"question {item['question_id']} has invalid scope")
        if not isinstance(item.get("expected_source_ids"), list):
            raise ValueError(f"question {item['question_id']} has no source labels")
        if not isinstance(item.get("expected_page_ranges"), list):
            raise ValueError(f"question {item['question_id']} has no page labels")
        if not isinstance(item.get("expected_escalation"), bool):
            raise ValueError(f"question {item['question_id']} has no escalation label")
        present_types.add(question_type)
    if present_types != QUESTION_TYPES:
        missing = ", ".join(sorted(QUESTION_TYPES - present_types))
        raise ValueError(f"technical evaluation dataset is missing types: {missing}")


def _validate_partitions(
    value: Any,
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("technical evaluation dataset must define fixed partitions")
    version = str(value.get("version") or "").strip()
    method = str(value.get("method") or "").strip()
    if not version or not method:
        raise ValueError("technical evaluation partitions need a version and method")

    question_ids = {str(question["question_id"]) for question in questions}
    normalized: dict[str, list[str]] = {}
    for partition in PARTITIONS:
        partition_ids = value.get(partition)
        if not isinstance(partition_ids, list) or not all(
            isinstance(question_id, str) and question_id
            for question_id in partition_ids
        ):
            raise ValueError(f"partition {partition} must contain question IDs")
        if len(partition_ids) != len(set(partition_ids)):
            raise ValueError(f"partition {partition} contains duplicate question IDs")
        normalized[partition] = partition_ids

    dev_ids = set(normalized["dev"])
    holdout_ids = set(normalized["holdout"])
    if dev_ids & holdout_ids:
        raise ValueError("development and holdout partitions must be disjoint")
    if dev_ids | holdout_ids != question_ids:
        raise ValueError("development and holdout partitions must cover all questions")
    if len(dev_ids) != 35 or len(holdout_ids) != 15:
        raise ValueError("technical evaluation partitions must contain 35 and 15 questions")

    question_type_by_id = {
        str(question["question_id"]): str(question["question_type"])
        for question in questions
    }
    for partition, partition_ids in normalized.items():
        present_types = {question_type_by_id[question_id] for question_id in partition_ids}
        if present_types != QUESTION_TYPES:
            raise ValueError(f"partition {partition} must include every question type")

    return {"version": version, "method": method, **normalized}


def _evaluate_record(
    record: TechnicalEvaluationRecord,
    expected: dict[str, Any],
) -> dict[str, Any]:
    trace = record.provenance.get("retrieval_trace")
    if not isinstance(trace, list):
        trace = []
    expected_sources = {
        str(item) for item in expected.get("expected_source_ids", []) if item
    }
    acceptable_sources = {
        str(item) for item in expected.get("acceptable_source_ids", []) if item
    }
    relevant_sources = expected_sources | acceptable_sources
    retrieved_sources = [str(item.get("source_id") or "") for item in trace]
    source_ranks = [
        index
        for index, source_id in enumerate(retrieved_sources, start=1)
        if source_id in relevant_sources
    ]
    citations = record.citations
    cited_sources = {
        str(item.get("sourceId") or item.get("source_id") or "")
        for item in citations
    }
    expected_scope = str(expected["expected_scope"])
    expected_statuses = _expected_statuses(expected)
    out_of_scope = expected_scope == "out_of_scope"
    answer_labels = set(re.findall(r"\[\d+\]", record.answer or ""))
    citation_labels = {
        str(item.get("label") or "") for item in citations if item.get("label")
    }
    expected_escalation = bool(expected.get("expected_escalation"))
    source_rank = min(source_ranks) if source_ranks else None

    row = {
        **asdict(record),
        "question_id": record.query_id,
        "source_case_id": expected.get("case_id"),
        "partition": expected.get("partition"),
        "question_type": expected.get("question_type"),
        "review_criteria": expected.get("review_criteria"),
        "review_focus": expected.get("review_focus"),
        "expected_scope": expected_scope,
        "expected_retrieval_statuses": sorted(expected_statuses),
        "expected_source_ids": sorted(expected_sources),
        "acceptable_source_ids": sorted(acceptable_sources),
        "expected_page_ranges": expected.get("expected_page_ranges", []),
        "expected_escalation": expected_escalation,
        "retrieved_source_ids": retrieved_sources,
        "retrieved_chunk_ids": [
            str(item.get("chunk_id") or "") for item in trace
        ],
        "source_ranks": source_ranks,
        "expected_source_rank": source_rank,
        "expected_source_at_1": (
            source_rank == 1 if relevant_sources else None
        ),
        "expected_source_at_3": (
            source_rank is not None and source_rank <= 3
            if relevant_sources
            else None
        ),
        "reciprocal_rank": (
            1 / source_rank if source_rank is not None else 0.0
        ) if relevant_sources else None,
        "expected_source_in_top_k": (
            bool(source_ranks) if relevant_sources else None
        ),
        "expected_page_in_top_k": (
            _page_match(trace, expected.get("expected_page_ranges", []))
            if expected.get("expected_page_ranges")
            else None
        ),
        "expected_source_cited": (
            bool(cited_sources & relevant_sources) if relevant_sources else None
        ),
        "expected_page_cited": (
            _page_match(citations, expected.get("expected_page_ranges", []))
            if expected.get("expected_page_ranges")
            else None
        ),
        "scope_match": _scope_match(expected_scope, record.scope_decision),
        "retrieval_status_match": record.retrieval_status in expected_statuses,
        "escalation_match": (
            record.escalation_recommended == expected_escalation
        ),
        "escalation_outcome": _escalation_outcome(
            expected_escalation,
            record.escalation_recommended,
            record.status,
        ),
        "citation_labels_valid": answer_labels <= citation_labels,
        "unsupported_question_rejected": (
            record.retrieval_status == "insufficient_evidence" and not citations
            if out_of_scope and record.status == "success"
            else None
        ),
        "answer_generated": bool(record.answer and record.answer.strip()),
        "provider_model_matches_requested": _provider_model_matches(record),
        "token_usage_complete": _token_usage_complete(record),
        "manual_review": {field: None for field in MANUAL_REVIEW_FIELDS},
    }
    checks = [
        row["scope_match"],
        row["retrieval_status_match"],
        row["escalation_match"],
        row["citation_labels_valid"],
        row["answer_generated"],
        row["expected_source_in_top_k"],
        row["expected_page_in_top_k"],
        row["expected_source_cited"],
        row["expected_page_cited"],
        row["unsupported_question_rejected"],
        row["provider_model_matches_requested"],
        row["token_usage_complete"],
    ]
    row["automated_pass"] = record.status == "success" and all(
        check is not False for check in checks
    )
    return row


def _metric_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [row for row in rows if row["status"] == "success"]
    source_top_k = _source_top_k_summary(rows)
    page = _page_summary(rows)
    citation = _citation_summary_metrics(rows, successful)
    scope = {
        "accuracy": _boolean_rate(row["scope_match"] for row in rows),
        "confusion_matrix": _scope_confusion_matrix(rows),
    }
    escalation = {
        "accuracy": _boolean_rate(row["escalation_match"] for row in rows),
        "confusion_matrix": _escalation_confusion_matrix(rows),
    }
    latency = _latency_summary(successful)
    errors = _error_summary(rows)
    return {
        "success_rate": _boolean_rate(row["status"] == "success" for row in rows),
        "automated_pass_rate": _boolean_rate(row["automated_pass"] for row in rows),
        "expected_source_in_top_k_rate": _optional_boolean_rate(
            row["expected_source_in_top_k"] for row in rows
        ),
        "expected_page_in_top_k_rate": _optional_boolean_rate(
            row["expected_page_in_top_k"] for row in rows
        ),
        "expected_source_cited_rate": _optional_boolean_rate(
            row["expected_source_cited"] for row in rows
        ),
        "expected_page_cited_rate": _optional_boolean_rate(
            row["expected_page_cited"] for row in rows
        ),
        "scope_accuracy": scope["accuracy"],
        "retrieval_status_accuracy": _boolean_rate(
            row["retrieval_status_match"] for row in rows
        ),
        "escalation_accuracy": escalation["accuracy"],
        "citation_label_validity": _boolean_rate(
            row["citation_labels_valid"] for row in successful
        ),
        "provider_model_match_rate": _optional_boolean_rate(
            row["provider_model_matches_requested"] for row in rows
        ),
        "token_usage_complete_rate": _optional_boolean_rate(
            row["token_usage_complete"] for row in rows
        ),
        "runtime_config_consistent": len(
            {
                row["provenance"].get("runtime_config_fingerprint")
                for row in rows
                if row["provenance"].get("runtime_config_fingerprint")
            }
        )
        <= 1,
        "provider_model_consistent": len(
            {
                row["provenance"].get("provider_response_model")
                for row in successful
                if row["provenance"].get("provider_response_model")
            }
        )
        <= 1,
        "out_of_scope_rejection_rate": _optional_boolean_rate(
            row["unsupported_question_rejected"] for row in rows
        ),
        "mean_latency_ms": latency["mean_ms"],
        "error_counts": errors["by_type"],
        "source_top_k": source_top_k,
        "page": page,
        "citation": citation,
        "scope": scope,
        "escalation": escalation,
        "latency": latency,
        "errors": errors,
        "by_question_type": {
            question_type: _question_type_summary(subset)
            for question_type in sorted(QUESTION_TYPES)
            if (
                subset := [
                    row for row in rows if row["question_type"] == question_type
                ]
            )
        },
    }


def _question_type_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    successful = [row for row in rows if row["status"] == "success"]
    return {
        "attempt_count": len(rows),
        "question_count": len({row["question_id"] for row in rows}),
        "success_rate": _boolean_rate(row["status"] == "success" for row in rows),
        "automated_pass_rate": _boolean_rate(
            row["automated_pass"] for row in rows
        ),
        "source_top_k": _source_top_k_summary(rows),
        "page": _page_summary(rows),
        "citation": _citation_summary_metrics(rows, successful),
        "scope": {
            "accuracy": _boolean_rate(row["scope_match"] for row in rows),
            "confusion_matrix": _scope_confusion_matrix(rows),
        },
        "escalation": {
            "accuracy": _boolean_rate(row["escalation_match"] for row in rows),
            "confusion_matrix": _escalation_confusion_matrix(rows),
        },
        "latency": _latency_summary(successful),
        "errors": _error_summary(rows),
    }


def _source_top_k_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    relevant = [
        row for row in rows if row.get("expected_source_in_top_k") is not None
    ]
    configured_top_k = sorted(
        {
            int(value)
            for row in rows
            if isinstance(
                value := row.get("provenance", {}).get("retrieval_top_k"),
                int,
            )
        }
    )
    reciprocal_ranks = [
        float(row["reciprocal_rank"])
        for row in relevant
        if row.get("reciprocal_rank") is not None
    ]
    return {
        "configured_top_k_values": configured_top_k,
        "evaluated_attempt_count": len(relevant),
        "hit_at_1_rate": _optional_boolean_rate(
            row.get("expected_source_at_1") for row in relevant
        ),
        "hit_at_3_rate": _optional_boolean_rate(
            row.get("expected_source_at_3") for row in relevant
        ),
        "hit_at_k_rate": _optional_boolean_rate(
            row.get("expected_source_in_top_k") for row in relevant
        ),
        "mean_reciprocal_rank": (
            round(mean(reciprocal_ranks), 4) if reciprocal_ranks else None
        ),
        "missing_expected_source_count": sum(
            row.get("expected_source_in_top_k") is False for row in relevant
        ),
    }


def _page_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "retrieved_page_match_rate": _optional_boolean_rate(
            row.get("expected_page_in_top_k") for row in rows
        ),
        "cited_page_match_rate": _optional_boolean_rate(
            row.get("expected_page_cited") for row in rows
        ),
        "labelled_attempt_count": sum(
            row.get("expected_page_in_top_k") is not None for row in rows
        ),
    }


def _citation_summary_metrics(
    rows: list[dict[str, Any]],
    successful: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "expected_source_cited_rate": _optional_boolean_rate(
            row.get("expected_source_cited") for row in rows
        ),
        "expected_page_cited_rate": _optional_boolean_rate(
            row.get("expected_page_cited") for row in rows
        ),
        "label_validity_rate": _optional_boolean_rate(
            row.get("citation_labels_valid") for row in successful
        ),
        "mean_citation_count": (
            round(mean(int(row.get("citation_count") or 0) for row in successful), 2)
            if successful
            else None
        ),
    }


def _scope_confusion_matrix(rows: list[dict[str, Any]]) -> dict[str, Any]:
    evaluated = [
        row
        for row in rows
        if row.get("status") == "success" and row.get("scope_decision")
    ]
    actual_labels = sorted(
        EXPECTED_SCOPES
        | {str(row["scope_decision"]) for row in evaluated}
    )
    counts = {
        expected: {
            actual: sum(
                row.get("expected_scope") == expected
                and row.get("scope_decision") == actual
                for row in evaluated
            )
            for actual in actual_labels
        }
        for expected in sorted(EXPECTED_SCOPES)
    }
    return {
        "expected_labels": sorted(EXPECTED_SCOPES),
        "actual_labels": actual_labels,
        "counts": counts,
        "evaluated_attempt_count": len(evaluated),
        "not_evaluated_attempt_count": len(rows) - len(evaluated),
    }


def _escalation_confusion_matrix(rows: list[dict[str, Any]]) -> dict[str, int]:
    outcomes = _counts(
        row["escalation_outcome"]
        for row in rows
        if row.get("escalation_outcome")
    )
    return {
        "correct_escalation": outcomes.get("correct_escalation", 0),
        "missed_escalation": outcomes.get("missed_escalation", 0),
        "over_escalation": outcomes.get("over_escalation", 0),
        "correct_non_escalation": outcomes.get("correct_non_escalation", 0),
        "not_evaluated": outcomes.get("not_evaluated", 0),
    }


def _latency_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = sorted(int(row["latency_ms"]) for row in rows)
    if not values:
        return {
            "sample_count": 0,
            "mean_ms": None,
            "median_ms": None,
            "p95_ms": None,
            "min_ms": None,
            "max_ms": None,
        }
    p95_index = max(0, (95 * len(values) + 99) // 100 - 1)
    return {
        "sample_count": len(values),
        "mean_ms": round(mean(values), 2),
        "median_ms": round(median(values), 2),
        "p95_ms": values[p95_index],
        "min_ms": values[0],
        "max_ms": values[-1],
    }


def _error_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    errors = [row for row in rows if row["status"] != "success"]
    return {
        "count": len(errors),
        "rate": _rate(len(errors), len(rows)),
        "by_type": _counts(
            str(row.get("error_type") or "unknown_error") for row in errors
        ),
    }


def _variation_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["question_id"]), []).append(row)

    questions: list[dict[str, Any]] = []
    for question_id, attempts in sorted(grouped.items()):
        successful = [row for row in attempts if row["status"] == "success"]
        comparable = len(successful) >= 2
        answers = [_normalize_answer(row.get("answer")) for row in successful]
        similarities = [
            SequenceMatcher(None, left, right).ratio()
            for index, left in enumerate(answers)
            for right in answers[index + 1 :]
        ]
        retrieval_signatures = {
            tuple(row.get("retrieved_chunk_ids") or []) for row in successful
        }
        citation_signatures = {
            tuple(
                str(item.get("chunkId") or item.get("chunk_id") or "")
                for item in row.get("citations", [])
            )
            for row in successful
        }
        questions.append(
            {
                "question_id": question_id,
                "question_type": attempts[0].get("question_type"),
                "attempts": len(attempts),
                "successful_attempts": len(successful),
                "error_count": len(attempts) - len(successful),
                "unique_answer_count": len(set(answers)),
                "exact_answer_consistent": (
                    len(set(answers)) <= 1 if comparable else None
                ),
                "mean_pairwise_answer_similarity": (
                    round(mean(similarities), 4) if similarities else None
                ),
                "unique_retrieval_count": len(retrieval_signatures),
                "retrieval_consistent": (
                    len(retrieval_signatures) <= 1 if comparable else None
                ),
                "unique_citation_count": len(citation_signatures),
                "citations_consistent": (
                    len(citation_signatures) <= 1 if comparable else None
                ),
                "retrieval_status_consistent": (
                    len({row.get("retrieval_status") for row in successful}) <= 1
                    if comparable
                    else None
                ),
                "scope_consistent": (
                    len({row.get("scope_decision") for row in successful}) <= 1
                    if comparable
                    else None
                ),
                "escalation_consistent": (
                    len(
                        {
                            row.get("escalation_recommended")
                            for row in successful
                        }
                    )
                    <= 1
                    if comparable
                    else None
                ),
            }
        )

    return {
        **_variation_metrics(questions),
        "by_question_type": {
            question_type: _variation_metrics(
                [
                    question
                    for question in questions
                    if question["question_type"] == question_type
                ]
            )
            for question_type in sorted(QUESTION_TYPES)
        },
        "questions": questions,
    }


def _variation_metrics(questions: list[dict[str, Any]]) -> dict[str, Any]:
    repeated = [item for item in questions if item["attempts"] > 1]
    pairwise = [
        item["mean_pairwise_answer_similarity"]
        for item in repeated
        if item["mean_pairwise_answer_similarity"] is not None
    ]
    return {
        "question_count": len(questions),
        "repeated_question_count": len(repeated),
        "answer_exact_consistency_rate": _optional_boolean_rate(
            item["exact_answer_consistent"] for item in repeated
        ),
        "retrieval_consistency_rate": _optional_boolean_rate(
            item["retrieval_consistent"] for item in repeated
        ),
        "citation_consistency_rate": _optional_boolean_rate(
            item["citations_consistent"] for item in repeated
        ),
        "mean_pairwise_answer_similarity": (
            round(mean(pairwise), 4) if pairwise else None
        ),
    }


def _expected_statuses(expected: dict[str, Any]) -> set[str]:
    value = expected.get("expected_retrieval_statuses")
    if isinstance(value, list):
        return {str(item) for item in value}
    single = expected.get("expected_retrieval_status")
    return {str(single)} if single else set()


def _scope_match(expected: str, actual: str | None) -> bool:
    if expected == "in_scope":
        return actual in {"in_scope", "possibly_in_scope"}
    return actual == expected


def _escalation_outcome(
    expected: bool,
    actual: bool | None,
    status: str,
) -> str:
    if status != "success" or actual is None:
        return "not_evaluated"
    if expected and actual:
        return "correct_escalation"
    if expected and not actual:
        return "missed_escalation"
    if not expected and actual:
        return "over_escalation"
    return "correct_non_escalation"


def _page_match(items: list[dict[str, Any]], labels: Any) -> bool:
    if not isinstance(labels, list) or not labels:
        return True
    for label in labels:
        if not isinstance(label, dict):
            continue
        for item in items:
            source_id = item.get("source_id") or item.get("sourceId")
            if source_id != label.get("source_id"):
                continue
            page_start = item.get("page_start") or item.get("pageStart")
            page_end = item.get("page_end") or item.get("pageEnd") or page_start
            if not isinstance(page_start, int) or not isinstance(page_end, int):
                continue
            if page_start <= int(label["page_end"]) and page_end >= int(
                label["page_start"]
            ):
                return True
    return False


def _normalize_answer(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _provider_model_matches(record: TechnicalEvaluationRecord) -> bool | None:
    if record.status != "success":
        return None
    requested = record.provenance.get("ai_model_requested")
    active = record.provenance.get("provider_response_model")
    return bool(requested and active and str(requested) == str(active))


def _token_usage_complete(record: TechnicalEvaluationRecord) -> bool | None:
    if record.status != "success":
        return None
    usage = record.provenance.get("token_usage")
    if not isinstance(usage, dict):
        return False
    required = {"input_tokens", "output_tokens", "total_tokens"}
    return all(
        key in usage and isinstance(usage[key], int | float)
        for key in required
    )


def _citation_summary(citations: list[dict[str, Any]]) -> str:
    return " | ".join(
        f"{item.get('label')}: {item.get('sourceId') or item.get('source_id')} "
        f"p.{item.get('pageStart') or item.get('page_start') or ''} "
        f"chunk={item.get('chunkId') or item.get('chunk_id') or ''}"
        for item in citations
    )


def _optional_boolean_rate(values: Iterable[Any]) -> float | None:
    present = [bool(value) for value in values if value is not None]
    return _boolean_rate(present) if present else None


def _boolean_rate(values: Iterable[Any]) -> float | None:
    present = [bool(value) for value in values]
    return round(sum(present) / len(present), 4) if present else None


def _rate(count: int, total: int) -> float | None:
    return round(count / total, 4) if total else None


def _counts(values: Iterable[Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for value in values:
        key = str(value)
        result[key] = result.get(key, 0) + 1
    return result
