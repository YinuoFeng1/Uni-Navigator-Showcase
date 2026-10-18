import json
from pathlib import Path

from app.config import PROJECT_ROOT
from app.scripts.evaluate_retrieval import _summary
from app.services.policy_safety import assess_policy_safety

EVALUATION_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "official_retrieval_evaluation.json"
)
OFFICIAL_SOURCE_IDS = {
    "uq-academic-progression-procedure",
    "uq-assessment-procedure",
    "uq-enrolment-procedure",
    "uq-examinations-procedure",
    "uq-removal-courses-special-circumstances-procedure",
}
REQUIRED_FIELDS = {
    "question_id",
    "question",
    "scope_label",
    "expected_source_ids",
    "acceptable_source_ids",
    "expected_page_ranges",
    "expected_retrieval_status",
    "expected_escalation",
    "reviewer_notes",
}


def test_official_evaluation_dataset_has_complete_unique_labels() -> None:
    questions = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))

    assert len(questions) >= 25
    assert len({item["question_id"] for item in questions}) == len(questions)
    assert all(REQUIRED_FIELDS <= set(item) for item in questions)
    assert all(
        set(item["expected_source_ids"]) <= OFFICIAL_SOURCE_IDS
        and set(item["acceptable_source_ids"]) <= OFFICIAL_SOURCE_IDS
        for item in questions
    )
    assert {item.get("task_category") for item in questions} >= {
        "academic_progression",
        "assessment",
        "enrolment",
        "examinations",
        "course_removal",
        "cross_document",
        "ambiguous",
        "out_of_corpus",
    }
    for item in questions:
        relevant = set(item["expected_source_ids"]) | set(
            item["acceptable_source_ids"]
        )
        assert all(
            page_range["source_id"] in relevant
            and page_range["page_start"] <= page_range["page_end"]
            for page_range in item["expected_page_ranges"]
        )


def test_retrieval_metric_summary_calculates_hits_and_leakage() -> None:
    rows = [
        {
            "expected_source_ids": ["source-a"],
            "acceptable_source_ids": [],
            "expected_page_ranges": [{"source_id": "source-a"}],
            "retrieved_source_ids": ["source-a"],
            "ranks": [1],
            "scores": [0.8],
            "hit_at_1": True,
            "hit_at_3": True,
            "hit_at_5": True,
            "reciprocal_rank": 1.0,
            "page_range_match": True,
            "no_result_correct": False,
            "prepared_source_leakage": 0,
            "inactive_source_retrieval": 0,
            "pass": True,
        },
        {
            "expected_source_ids": [],
            "acceptable_source_ids": [],
            "expected_page_ranges": [],
            "retrieved_source_ids": [],
            "ranks": [],
            "scores": [],
            "hit_at_1": False,
            "hit_at_3": False,
            "hit_at_5": False,
            "reciprocal_rank": 0.0,
            "page_range_match": True,
            "no_result_correct": True,
            "prepared_source_leakage": 0,
            "inactive_source_retrieval": 0,
            "pass": True,
        },
    ]

    metrics = _summary(rows)

    assert metrics["hit_at_1"] == 1.0
    assert metrics["hit_at_5"] == 1.0
    assert metrics["mean_reciprocal_rank"] == 1.0
    assert metrics["no_result_accuracy"] == 1.0
    assert metrics["prepared_source_leakage_count"] == 0


def test_overseas_student_language_triggers_visa_escalation() -> None:
    assessment = assess_policy_safety(
        "What document must an overseas student in a CRICOS program hold?"
    )

    assert assessment.high_stakes_detected is True
    assert "visa" in assessment.categories
