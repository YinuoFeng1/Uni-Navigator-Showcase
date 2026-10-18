from collections import Counter
import csv
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from app.application.chat_orchestrator import OrchestratedChatResult
from app.config import PROJECT_ROOT
from app.core.errors import ApplicationError
from app.schemas import AssistantAnswer, Citation, ScopeDecisionResponse
from app.scripts.run_technical_evaluation import (
    _build_fingerprints,
    _jsonl_contains_run_id,
)
from app.services.technical_evaluation import (
    QUESTION_TYPES,
    evaluate_technical_records,
    load_technical_evaluation_dataset,
    summarize_manual_review,
    write_manual_review_csv,
)
from app.services.escalation_service import decide_escalation_category
from app.services.policy_safety import assess_policy_safety
from app.services.technical_evaluation_service import TechnicalEvaluationService


DATASET_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "end_to_end_technical_evaluation.json"
)
REVIEW_PATH = (
    PROJECT_ROOT
    / "data"
    / "evaluation"
    / "reviews"
    / "end_to_end_technical_evaluation_2026-09-02_review.json"
)
DATASET_VERSION = "end-to-end-live-rag-2026-09-02.3"


class MemoryRepository:
    def __init__(self) -> None:
        self.records = []

    def append(self, record) -> None:
        self.records.append(record)


class FakeOrchestrator:
    def __init__(self, answers: list[str] | None = None, failure: bool = False) -> None:
        self.runtime = SimpleNamespace(
            execution_context="technical_evaluation",
            answer_mode="live_llm",
            runtime_config_fingerprint="sha256:test-runtime",
            canonical_dict=lambda: {
                "execution_context": "technical_evaluation",
                "answer_mode": "live_llm",
            },
        )
        self.answers = answers or ["Apply using the supported process [1]."]
        self.failure = failure
        self.calls = 0

    def execute(self, command, *, server_context=None):
        if self.failure:
            raise ApplicationError(
                "provider_unavailable",
                researcher_safe_detail="test provider failure",
                context={
                    "retrieval_status": "grounded",
                    "retrieval_trace": [_retrieval_trace()],
                    "generated_answer": "Rejected generated answer [1].",
                    "scope_decision": "in_scope",
                    "escalation_recommended": True,
                    "escalation_category": "contact_examinations",
                    "escalation_reasons": ["Personal confirmation is required."],
                    "high_stakes_detected": True,
                    "citations": [
                        _citation().model_dump(mode="json", by_alias=True)
                    ],
                    "provider_response_id": "resp_retry_2",
                    "provider_response_ids": ["resp_retry_1", "resp_retry_2"],
                    "provider_response_model": "test-openai-model",
                    "token_usage": {"total_tokens": 60},
                    "citation_validation_retry_count": 1,
                    "generation_attempts": [
                        {"attempt": 1, "validation_error": "missing citation"},
                        {"attempt": 2, "validation_error": None},
                    ],
                },
            )
        answer_text = self.answers[self.calls % len(self.answers)]
        self.calls += 1
        answer = AssistantAnswer(
            id=f"answer-{self.calls}",
            interactionId=f"interaction-{self.calls}",
            answer=answer_text,
            shortAnswer=answer_text,
            basedOn="Based on one official policy passage.",
            evidenceSummary="Based on one official policy passage.",
            nextStep="Contact staff if needed.",
            limitations="Limited to the cited passage.",
            uncertainty="The retrieved evidence supports the answer.",
            uncertaintyLevel="low",
            escalationRecommended=True,
            escalationCategory="contact_examinations",
            escalationReasons=["The personal outcome requires confirmation."],
            highStakesDetected=True,
            citations=[_citation()],
            retrievalStatus="grounded",
            escalationGuidance="Contact staff if needed.",
            scopeDecision=ScopeDecisionResponse(
                decision="in_scope",
                matchedTopics=["examinations"],
                supportingSourceIds=["uq-examinations-procedure"],
                reasons=[],
                ruleSignals=[],
                retrievalSignals={},
                confidenceCategory="high",
                registryVersion="test",
                escalationCategory="contact_examinations",
            ),
        )
        return OrchestratedChatResult(
            answer=answer,
            time_to_first_answer_ms=25,
            provenance={
                "execution_context": "technical_evaluation",
                "retrieval_trace": [_retrieval_trace()],
                "runtime_config_fingerprint": "sha256:test-runtime",
                "retrieval_top_k": 5,
                "ai_model_requested": "test-openai-model",
                "provider_response_model": "test-openai-model",
                "token_usage": {
                    "input_tokens": 20,
                    "output_tokens": 10,
                    "total_tokens": 30,
                },
            },
        )


def _citation() -> Citation:
    return Citation(
        id="c1",
        citationId="c1",
        label="[1]",
        sourceId="uq-examinations-procedure",
        chunkId="exam-page-11",
        documentTitle="Examinations Procedure",
        quotedText="A student may apply for a deferred examination.",
        pageNumber=11,
        pageStart=11,
        pageEnd=11,
        sourceType="official_policy",
    )


def _retrieval_trace() -> dict:
    return {
        "rank": 1,
        "chunk_id": "exam-page-11",
        "source_id": "uq-examinations-procedure",
        "source_type": "official_policy",
        "score": 0.9,
        "distance": 0.1,
        "page_start": 11,
        "page_end": 11,
        "citation_label": "[1]",
    }


def _exam_expectation() -> dict:
    return {
        "question_id": "exam-test",
        "question": "How do I request a deferred exam?",
        "question_type": "high_risk",
        "case_id": "deferred-exam-medical-evidence",
        "task_id": "task_special_consideration_illness",
        "expected_scope": "in_scope",
        "expected_retrieval_statuses": ["grounded", "individual_assessment"],
        "expected_source_ids": ["uq-examinations-procedure"],
        "acceptable_source_ids": [],
        "expected_page_ranges": [
            {
                "source_id": "uq-examinations-procedure",
                "page_start": 11,
                "page_end": 12,
            }
        ],
        "expected_escalation": True,
        "review_criteria": "Do not invent a deadline.",
    }


def test_end_to_end_dataset_has_fifty_questions_and_required_mix() -> None:
    raw_dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    assert raw_dataset["dataset_version"] == DATASET_VERSION
    assert all("expected_escalation" not in case for case in raw_dataset["cases"])
    assert all(
        isinstance(question.get("expected_escalation"), bool)
        for case in raw_dataset["cases"]
        for question in case["questions"]
    )

    dataset = load_technical_evaluation_dataset(DATASET_PATH)
    questions = dataset["questions"]
    official_source_ids = {
        json.loads(path.read_text(encoding="utf-8"))["source_id"]
        for path in (PROJECT_ROOT / "data" / "corpus" / "metadata").glob("*.json")
    }

    assert len(questions) == 50
    assert len({item["question_id"] for item in questions}) == 50
    assert {item["question_type"] for item in questions} == QUESTION_TYPES
    assert len({item["case_id"] for item in questions}) == 7
    assert sum(item["question_type"] == "ambiguous" for item in questions) == 8
    assert sum(item["question_type"] == "out_of_scope" for item in questions) == 6
    assert Counter(item["expected_scope"] for item in questions) == {
        "in_scope": 36,
        "ambiguous": 8,
        "out_of_scope": 6,
    }
    assert Counter(item["expected_escalation"] for item in questions) == {
        True: 31,
        False: 19,
    }
    for item in questions:
        relevant = set(item["expected_source_ids"]) | set(
            item.get("acceptable_source_ids", [])
        )
        assert relevant <= official_source_ids
        assert all(
            label["source_id"] in relevant
            and 1 <= label["page_start"] <= label["page_end"]
            for label in item["expected_page_ranges"]
        )


def test_dataset_has_fixed_stratified_dev_and_holdout_partitions() -> None:
    full = load_technical_evaluation_dataset(DATASET_PATH)
    dev = load_technical_evaluation_dataset(DATASET_PATH, partition="dev")
    holdout = load_technical_evaluation_dataset(
        DATASET_PATH,
        partition="holdout",
    )

    dev_ids = {question["question_id"] for question in dev["questions"]}
    holdout_ids = {
        question["question_id"] for question in holdout["questions"]
    }
    assert len(dev_ids) == 35
    assert len(holdout_ids) == 15
    assert dev_ids.isdisjoint(holdout_ids)
    assert dev_ids | holdout_ids == {
        question["question_id"] for question in full["questions"]
    }
    assert dev["partition_version"] == "stratified-fixed-2026-09-02.1"
    assert Counter(question["question_type"] for question in dev["questions"]) == {
        "standard": 4,
        "paraphrase": 13,
        "ambiguous": 6,
        "out_of_scope": 4,
        "high_risk": 8,
    }
    assert Counter(
        question["question_type"] for question in holdout["questions"]
    ) == {
        "standard": 2,
        "paraphrase": 6,
        "ambiguous": 2,
        "out_of_scope": 2,
        "high_risk": 3,
    }
    assert Counter(
        question["expected_escalation"] for question in holdout["questions"]
    ) == {True: 9, False: 6}
    assert Counter(
        question["expected_scope"] for question in holdout["questions"]
    ) == {"in_scope": 11, "ambiguous": 2, "out_of_scope": 2}
    assert len({question["case_id"] for question in holdout["questions"]}) == 7


def test_gold_label_review_matches_versioned_dataset() -> None:
    review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
    dataset = load_technical_evaluation_dataset(DATASET_PATH)
    questions = {item["question_id"]: item for item in dataset["questions"]}
    decisions = {item["question_id"]: item for item in review["decisions"]}

    assert review["reviewed_dataset"] == {
        "path": "data/evaluation/end_to_end_technical_evaluation.json",
        "version": "end-to-end-live-rag-2026-09-02.2",
        "sha256": "4e163e4d44741f76909ea69424afe597b0f305bfae3895010cbe5da547197404",
    }
    assert review["partitioned_dataset"]["version"] == DATASET_VERSION
    assert review["partitioned_dataset"]["sha256"] == hashlib.sha256(
        DATASET_PATH.read_bytes()
    ).hexdigest()
    assert review["partitioned_dataset"]["label_changes_after_review"] is False
    assert review["source_audit"]["file_name"] == (
        "Uni_Navigator_50_Question_Audit.xlsx"
    )
    assert review["summary"] == {
        "question_count": 50,
        "source_correct_count": 50,
        "page_correct_count": 43,
        "page_not_applicable_count": 7,
        "scope_counts": {
            "in_scope": 36,
            "ambiguous": 8,
            "out_of_scope": 6,
        },
        "escalation_counts": {"yes": 31, "no": 19},
    }
    assert decisions.keys() == questions.keys()
    for question_id, question in questions.items():
        decision = decisions[question_id]
        assert decision["source_review"] == "correct"
        assert decision["expected_source_ids"] == question["expected_source_ids"]
        assert decision["acceptable_source_ids"] == question["acceptable_source_ids"]
        assert decision["expected_page_ranges"] == question["expected_page_ranges"]
        assert decision["expected_scope"] == question["expected_scope"]
        assert decision["expected_escalation"] is question["expected_escalation"]


def test_escalation_rules_match_reviewed_question_labels() -> None:
    questions = load_technical_evaluation_dataset(DATASET_PATH)["questions"]
    actual_counts: Counter[bool] = Counter()

    for question in questions:
        expected_scope = question["expected_scope"]
        retrieval_status = {
            "in_scope": "grounded",
            "ambiguous": "ambiguous",
            "out_of_scope": "insufficient_evidence",
        }[expected_scope]
        scope_decision = SimpleNamespace(
            decision=expected_scope,
            escalation_category=(
                "contact_faculty_or_student_centre"
                if expected_scope == "out_of_scope"
                else "contact_authorised_university_staff"
            ),
        )
        safety = assess_policy_safety(question["question"])
        decision = decide_escalation_category(
            question=question["question"],
            retrieval_status=retrieval_status,
            scope_decision=scope_decision,
            high_stakes_detected=safety.high_stakes_detected,
            safety_categories=safety.categories,
        )

        assert decision.recommended is question["expected_escalation"], question[
            "question_id"
        ]
        actual_counts[decision.recommended] += 1

    assert actual_counts == {True: 31, False: 19}


def test_technical_service_records_complete_success_and_failure() -> None:
    success_repository = MemoryRepository()
    service = TechnicalEvaluationService(FakeOrchestrator(), success_repository)

    success = service.run(
        run_id="run-1",
        query_id="exam-test",
        question="How do I request a deferred exam?",
        repetition=2,
        task_id="task_special_consideration_illness",
        partition="dev",
    )

    assert success.status == "success"
    assert success.repetition == 2
    assert success.partition == "dev"
    assert success.answer == "Apply using the supported process [1]."
    assert success.escalation_category == "contact_examinations"
    assert success.escalation_reasons == [
        "The personal outcome requires confirmation."
    ]
    assert success.citations[0]["chunkId"] == "exam-page-11"
    assert success.provenance["technical_run_id"] == "run-1"
    assert success_repository.records == [success]

    failure_repository = MemoryRepository()
    failure_service = TechnicalEvaluationService(
        FakeOrchestrator(failure=True), failure_repository
    )
    failure = failure_service.run(
        run_id="run-2",
        query_id="exam-test",
        question="How do I request a deferred exam?",
    )

    assert failure.status == "error"
    assert failure.error_type == "provider_unavailable"
    assert failure.answer == "Rejected generated answer [1]."
    assert failure.scope_decision == "in_scope"
    assert failure.escalation_recommended is True
    assert failure.escalation_category == "contact_examinations"
    assert failure.high_stakes_detected is True
    assert failure.citation_count == 1
    assert failure.provenance["retrieval_trace"][0]["chunk_id"] == "exam-page-11"
    assert failure.provenance["provider_response_ids"] == [
        "resp_retry_1",
        "resp_retry_2",
    ]
    assert failure.provenance["citation_validation_retry_count"] == 1
    assert len(failure.provenance["generation_attempts"]) == 2
    assert failure_repository.records == [failure]


def test_evaluation_scores_automated_checks_and_repeated_answer_variation() -> None:
    repository = MemoryRepository()
    service = TechnicalEvaluationService(
        FakeOrchestrator(
            answers=[
                "Apply using the supported process [1].",
                "Use the supported process to apply [1].",
                "Apply using the supported process [1].",
            ]
        ),
        repository,
    )
    for repetition in range(1, 4):
        service.run(
            run_id="variation-run",
            query_id="exam-test",
            question="How do I request a deferred exam?",
            repetition=repetition,
        )

    report = evaluate_technical_records(repository.records, [_exam_expectation()])
    row = report["attempts"][0]

    assert report["attempt_count"] == 3
    assert report["metrics"]["expected_source_in_top_k_rate"] == 1.0
    assert report["metrics"]["expected_page_cited_rate"] == 1.0
    assert report["metrics"]["scope_accuracy"] == 1.0
    assert report["metrics"]["escalation_accuracy"] == 1.0
    assert report["metrics"]["source_top_k"] == {
        "configured_top_k_values": [5],
        "evaluated_attempt_count": 3,
        "hit_at_1_rate": 1.0,
        "hit_at_3_rate": 1.0,
        "hit_at_k_rate": 1.0,
        "mean_reciprocal_rank": 1.0,
        "missing_expected_source_count": 0,
    }
    assert report["metrics"]["escalation"]["confusion_matrix"] == {
        "correct_escalation": 3,
        "missed_escalation": 0,
        "over_escalation": 0,
        "correct_non_escalation": 0,
        "not_evaluated": 0,
    }
    assert report["metrics"]["scope"]["confusion_matrix"]["counts"][
        "in_scope"
    ]["in_scope"] == 3
    assert report["metrics"]["latency"]["median_ms"] == 25
    assert report["metrics"]["errors"]["count"] == 0
    assert report["metrics"]["by_question_type"]["high_risk"][
        "attempt_count"
    ] == 3
    assert row["automated_pass"] is True
    variation = report["variation"]["questions"][0]
    assert variation["unique_answer_count"] == 2
    assert variation["exact_answer_consistent"] is False
    assert variation["retrieval_consistent"] is True
    assert variation["citations_consistent"] is True
    assert report["variation"]["by_question_type"]["high_risk"][
        "mean_pairwise_answer_similarity"
    ] == report["variation"]["mean_pairwise_answer_similarity"]


def test_escalation_and_scope_confusion_matrices_name_all_outcomes() -> None:
    repository = MemoryRepository()
    service = TechnicalEvaluationService(FakeOrchestrator(), repository)
    service.run(
        run_id="matrix-run",
        query_id="base",
        question="How do I request a deferred exam?",
    )
    base = repository.records[0]
    records = [
        replace(base, query_id="correct-yes", escalation_recommended=True),
        replace(
            base,
            query_id="missed",
            escalation_recommended=False,
            scope_decision="possibly_in_scope",
        ),
        replace(
            base,
            query_id="over",
            escalation_recommended=True,
            scope_decision="out_of_scope",
        ),
        replace(
            base,
            query_id="correct-no",
            escalation_recommended=False,
            scope_decision="out_of_scope",
        ),
    ]
    questions = []
    for question_id, expected_escalation, expected_scope in (
        ("correct-yes", True, "in_scope"),
        ("missed", True, "in_scope"),
        ("over", False, "ambiguous"),
        ("correct-no", False, "out_of_scope"),
    ):
        questions.append(
            {
                **_exam_expectation(),
                "question_id": question_id,
                "expected_escalation": expected_escalation,
                "expected_scope": expected_scope,
            }
        )

    report = evaluate_technical_records(records, questions)

    assert report["metrics"]["escalation"]["confusion_matrix"] == {
        "correct_escalation": 1,
        "missed_escalation": 1,
        "over_escalation": 1,
        "correct_non_escalation": 1,
        "not_evaluated": 0,
    }
    scope_matrix = report["metrics"]["scope"]["confusion_matrix"]
    assert scope_matrix["counts"]["in_scope"]["in_scope"] == 1
    assert scope_matrix["counts"]["in_scope"]["possibly_in_scope"] == 1
    assert scope_matrix["counts"]["ambiguous"]["out_of_scope"] == 1
    assert scope_matrix["counts"]["out_of_scope"]["out_of_scope"] == 1


def test_manual_review_csv_and_summary(tmp_path: Path) -> None:
    repository = MemoryRepository()
    service = TechnicalEvaluationService(FakeOrchestrator(), repository)
    service.run(
        run_id="review-run",
        query_id="exam-test",
        question="How do I request a deferred exam?",
    )
    report = evaluate_technical_records(repository.records, [_exam_expectation()])
    path = tmp_path / "review.csv"
    write_manual_review_csv(path, report["attempts"])

    with path.open("r", encoding="utf-8", newline="") as source:
        rows = list(csv.DictReader(source))
    assert rows[0]["escalation_outcome"] == "correct_escalation"
    assert rows[0]["expected_escalation"] == "True"
    assert rows[0]["status"] == "success"
    assert rows[0]["error_type"] == ""
    assert rows[0]["latency_ms"] == "25"
    assert rows[0]["citation_validation_retry_count"] == "0"
    rows[0].update(
        {
            "answers_question": "yes",
            "citations_support_conclusions": "yes",
            "unsupported_rule_present": "no",
            "uncertainty_appropriate": "partial",
            "escalation_appropriate": "yes",
            "reviewer_id": "reviewer-1",
        }
    )
    with path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    summary = summarize_manual_review(path)

    assert summary["reviewed_attempt_count"] == 1
    assert summary["metrics"]["answers_question"]["yes_rate"] == 1.0
    assert summary["metrics"]["uncertainty_appropriate"]["counts"]["partial"] == 1
    assert json.loads(json.dumps(summary))["metrics"]


def test_existing_technical_run_id_is_detected(tmp_path: Path) -> None:
    path = tmp_path / "technical_runs.jsonl"
    path.write_text(
        "not-json\n" + json.dumps({"run_id": "pilot-tech-v1"}) + "\n",
        encoding="utf-8",
    )

    assert _jsonl_contains_run_id(path, "pilot-tech-v1") is True
    assert _jsonl_contains_run_id(path, "new-run") is False


def test_technical_run_id_is_scoped_to_partition(tmp_path: Path) -> None:
    path = tmp_path / "technical_runs.jsonl"
    path.write_text(
        json.dumps({"run_id": "evaluation-v1", "partition": "dev"}) + "\n",
        encoding="utf-8",
    )

    assert _jsonl_contains_run_id(
        path,
        "evaluation-v1",
        partition="dev",
    )
    assert not _jsonl_contains_run_id(
        path,
        "evaluation-v1",
        partition="holdout",
    )


def test_report_fingerprints_cover_reproducibility_inputs() -> None:
    dataset = load_technical_evaluation_dataset(DATASET_PATH, partition="dev")
    runtime = SimpleNamespace(
        app_revision="test-revision",
        prompt_template_version="grounded-v9",
        corpus_fingerprint="sha256:test-corpus",
        corpus_manifest_version="manifest-v1",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        vector_store_collection="test-collection",
        scope_registry_version="scope-v1",
        scope_registry_fingerprint="sha256:test-scope",
        runtime_config_fingerprint="sha256:test-runtime",
    )

    fingerprints = _build_fingerprints(
        dataset_path=DATASET_PATH,
        dataset=dataset,
        runtime=runtime,
    )

    assert fingerprints["dataset"]["sha256"].startswith("sha256:")
    assert fingerprints["dataset"]["partition"] == "dev"
    assert fingerprints["code"]["backend_source_sha256"].startswith("sha256:")
    assert fingerprints["code"]["git_commit"]
    assert fingerprints["prompt"]["version"] == "grounded-v9"
    assert fingerprints["prompt"]["sha256"].startswith("sha256:")
    assert fingerprints["corpus"]["sha256"] == "sha256:test-corpus"
    assert fingerprints["runtime_config"]["sha256"] == "sha256:test-runtime"
