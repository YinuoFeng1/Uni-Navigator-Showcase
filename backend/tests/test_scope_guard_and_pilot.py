import csv
from io import StringIO
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import Session

from app.config import PROJECT_ROOT, get_settings
from app.database import engine
from app.models import InteractionLog
from app.services.corpus_manifest import manifest_path
from app.services.corpus_scope_service import (
    apply_scope_to_retrieval_status,
    decide_corpus_scope,
    load_scope_registry,
)
from app.services.pilot_preflight_service import run_pilot_preflight


REGISTRY_PATH = PROJECT_ROOT / "data" / "corpus" / "corpus_scope.json"
EVALUATION_PATH = (
    PROJECT_ROOT / "data" / "evaluation" / "official_retrieval_evaluation.json"
)


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _chunk(
    source_id: str = "uq-assessment-procedure",
    score: float = 0.82,
    text: str = "Assessment extension requests require policy evidence.",
) -> dict:
    return {
        "chunk_id": "chunk-1",
        "source_id": source_id,
        "title": "Policy",
        "document_name": "Policy",
        "section": "General",
        "url": "https://example.invalid/policy",
        "source_type": "official_policy",
        "chunk_text": text,
        "page_start": 1,
        "page_end": 1,
        "score": score,
        "active": True,
    }


def _decision(question: str, chunks: list[dict] | None = None):
    return decide_corpus_scope(
        question,
        chunks or [],
        load_scope_registry(REGISTRY_PATH),
        partial_threshold=0.35,
        grounded_threshold=0.55,
    )


def test_scope_registry_is_researcher_reviewable() -> None:
    registry = load_scope_registry(REGISTRY_PATH)

    assert registry["registry_version"]
    assert len(registry["topics"]) == 8
    required = {
        "topic_id",
        "display_name",
        "supported_intents",
        "representative_terms",
        "common_paraphrases",
        "source_ids",
        "unsupported_adjacent_topics",
        "default_escalation_category",
    }
    assert all(required <= set(topic) for topic in registry["topics"])


def test_scope_decision_for_clearly_in_scope_question() -> None:
    decision = _decision(
        "What evidence is needed for an assessment extension request?",
        [_chunk()],
    )

    assert decision.decision == "in_scope"
    assert decision.matched_topics == ["assessment"]
    assert decision.supporting_source_ids == ["uq-assessment-procedure"]


def test_scope_membership_accepts_usable_evidence_below_grounded_threshold() -> None:
    decision = _decision(
        "What evidence can support an internal appeal?",
        [
            _chunk(
                source_id="uq-academic-administrative-appeals-procedure",
                score=0.49,
                text="An internal appeal should include documentary evidence.",
            )
        ],
    )

    assert decision.decision == "in_scope"
    assert decision.confidence_category == "medium"


@pytest.mark.parametrize(
    ("question", "source_id", "passage"),
    [
        (
            "Can I enrol in extra courses this semester?",
            "uq-enrolment-procedure",
            "The semester enrolment limit may be extended.",
        ),
        (
            "Does withdrawing after census affect fees or grades?",
            "uq-removal-courses-special-circumstances-procedure",
            "Withdrawal after census may affect fees and grades.",
        ),
        (
            "How can a student challenge an administrative decision?",
            "uq-academic-administrative-appeals-procedure",
            "A student may challenge an administrative decision by appeal.",
        ),
        (
            "What should a student do after a progression notice?",
            "uq-academic-progression-procedure",
            "A student must respond to a progression notice.",
        ),
    ],
)
def test_reviewed_general_policy_phrasings_are_in_scope(
    question: str,
    source_id: str,
    passage: str,
) -> None:
    decision = _decision(question, [_chunk(source_id=source_id, text=passage)])

    assert decision.decision == "in_scope"


def test_practice_room_phrasing_is_out_of_scope() -> None:
    decision = _decision(
        "Can I book an instrument room on campus?",
        [_chunk(score=0.72)],
    )

    assert decision.decision == "out_of_scope"


def test_supported_extension_plus_practice_room_is_ambiguous() -> None:
    decision = _decision(
        "My assessment extension was approved. Where do I book a music practice room?",
        [_chunk(score=0.72)],
    )

    assert decision.decision == "ambiguous"


@pytest.mark.parametrize(
    "question",
    [
        "Can I overload to graduate before my visa expires, and will UQ approve it?",
        "Can I get my course fees refunded because of a landlord dispute?",
        "Can I get my course fees refunded because of a dispute with my landlord?",
    ],
)
def test_reviewed_personal_outcome_phrasings_are_ambiguous(question: str) -> None:
    decision = _decision(question, [_chunk(score=0.72)])

    assert decision.decision == "ambiguous"


def test_scope_decision_for_out_of_domain_question_ignores_high_similarity() -> None:
    decision = _decision(
        "What is the weather forecast for Brisbane tomorrow?",
        [_chunk(score=0.91)],
    )

    assert decision.decision == "out_of_scope"
    assert "unsupported_phrase:weather forecast" in decision.rule_signals


def test_scope_decision_for_university_admin_out_of_corpus_question() -> None:
    decision = _decision("How do I appeal a library fine?", [_chunk(score=0.73)])

    assert decision.decision == "out_of_scope"
    assert decision.escalation_category == "contact_faculty_or_student_centre"


def test_scope_decision_for_ambiguous_mixed_question() -> None:
    decision = _decision(
        "If I remove a course, what are the international student visa consequences?",
        [
            _chunk(
                source_id="uq-removal-courses-special-circumstances-procedure",
                text="A student may apply to remove a course in special circumstances.",
            )
        ],
    )

    assert decision.decision == "ambiguous"
    assert decision.escalation_category == "international_student_or_visa_support"


def test_parking_regression_cannot_be_partial_or_grounded() -> None:
    decision = _decision(
        "How do I apply for a student parking permit at UQ?",
        [_chunk(score=0.74)],
    )

    status = apply_scope_to_retrieval_status("grounded", decision)
    assert decision.decision == "out_of_scope"
    assert status == "insufficient_evidence"


def test_out_of_scope_chat_has_no_citations_and_cannot_be_grounded(
    client, monkeypatch
) -> None:
    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: pytest.fail(
            "explicitly out-of-scope questions must not call embeddings"
        ),
    )

    response = client.post(
        "/api/chat",
        json={"question": "How do I apply for a student parking permit at UQ?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["retrievalStatus"] == "insufficient_evidence"
    assert payload["citations"] == []
    assert payload["scopeDecision"]["decision"] == "out_of_scope"
    assert "not have enough matching official policy evidence" in payload["shortAnswer"]


def _runtime_settings(**overrides):
    values = {
        "embedding_provider": "openai",
        "embedding_model": "text-embedding-3-small",
        "pilot_expected_embedding_provider": "openai",
        "pilot_expected_embedding_model": "text-embedding-3-small",
        "vector_store_allow_fallback": False,
        "answer_mode": "live_llm",
        "ai_provider": "openai",
        "openai_api_key": "test-key",
        "pilot_expected_vector_provider": "chroma",
        "pilot_expected_vector_collection": "pilot_collection",
        "pilot_expected_source_count": 10,
        "pilot_expected_chunk_count": 77,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_development_chat_remains_available(client) -> None:
    response = client.post(
        "/api/chat", json={"question": "Where can I find policy information?"}
    )

    assert response.status_code == 200
    assert response.json()["scopeDecision"]["decision"] in {
        "out_of_scope",
        "ambiguous",
    }


def test_interaction_provenance_is_logged(client) -> None:
    response = client.post(
        "/api/chat",
        json={
            "question": "Where can I find assessment extension information?",
            "taskId": "task_special_consideration_illness",
        },
    )
    interaction_id = response.json()["interactionId"]

    with Session(engine) as session:
        interaction = session.get(InteractionLog, interaction_id)
    assert interaction is not None
    assert interaction.embedding_provider == "mock"
    assert interaction.embedding_model == "text-embedding-3-small"
    assert interaction.vector_collection == "uni_navigator_policy_chunks"
    assert interaction.retrieval_top_k == 5
    assert interaction.retrieval_partial_threshold == 0.15
    assert interaction.retrieval_grounded_threshold == 0.35
    assert interaction.answer_mode == "live_llm"
    assert interaction.task_version
    assert interaction.app_version


def test_old_interaction_rows_are_readable_and_csv_remains_compatible(client) -> None:
    with Session(engine) as session:
        session.add(
            InteractionLog(
                id="interaction-old-row",
                condition="C_HIGHLIGHT",
                question="Old question",
                answer_id="answer-old",
                short_answer="Old answer",
                uncertainty_level="high",
                escalation_recommended=True,
                citation_count=0,
            )
        )
        session.commit()

    admin_response = client.get("/api/admin/logs")
    assert admin_response.status_code == 200
    old_item = next(
        item
        for item in admin_response.json()["items"]
        if item["id"] == "interaction-old-row"
    )
    assert old_item["embeddingProvider"] is None
    csv_response = client.get("/api/admin/logs/export.csv")
    rows = list(csv.DictReader(StringIO(csv_response.text)))
    csv_row = next(
        row
        for row in rows
        if row["row_type"] == "interaction"
        and row["interaction_id"] == "interaction-old-row"
    )
    assert csv_row["question"] == "Old question"
    assert csv_row["embedding_provider"] == ""
    assert "scope_registry_version" in csv_row


class _FakeVectorStore:
    def __init__(self, status) -> None:
        self._status = status
        self.query_count = 0

    def status(self):
        return self._status

    def query(self, query_embedding, top_k=1):
        self.query_count += 1
        return []


def _preflight_settings(tmp_path: Path):
    settings = _runtime_settings()
    settings.study_mode = "pilot"
    settings.ai_model = "fixed-v1"
    settings.retrieval_partial_score_threshold = 0.35
    settings.retrieval_grounded_score_threshold = 0.55
    settings.scope_registry_path = REGISTRY_PATH
    settings.vector_store_path = tmp_path / "vectors"
    settings.vector_collection_name = "pilot_collection"
    settings.vector_store_provider = "chroma"
    settings.retrieval_source_mode = "official"
    settings.pilot_allow_synthetic_sessions = False
    manifest = manifest_path(
        settings.vector_store_path, settings.vector_collection_name
    )
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text('{"sources":{"source":{"active":true}}}', encoding="utf-8")
    return settings


def _preflight_status(**overrides):
    values = {
        "active_provider": "chroma",
        "fallback_used": False,
        "collection_name": "pilot_collection",
        "source_count": 10,
        "chunk_count": 77,
        "embedding_dimension": 1536,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_preflight_succeeds_for_valid_live_answer_pilot_configuration(
    tmp_path: Path,
) -> None:
    settings = _preflight_settings(tmp_path)
    store = _FakeVectorStore(_preflight_status())

    report = run_pilot_preflight(
        settings,
        vector_store=store,
        database_path=tmp_path / "logs" / "pilot.db",
        session_labels=[],
    )

    assert report.ok is False  # Parent directory is intentionally not writable yet.
    (tmp_path / "logs").mkdir()
    report = run_pilot_preflight(
        settings,
        vector_store=store,
        database_path=tmp_path / "logs" / "pilot.db",
        session_labels=[],
    )
    assert report.ok is True
    assert store.query_count >= 1


def test_preflight_fails_for_empty_or_wrong_collection(tmp_path: Path) -> None:
    settings = _preflight_settings(tmp_path)
    (tmp_path / "logs").mkdir()
    report = run_pilot_preflight(
        settings,
        vector_store=_FakeVectorStore(
            _preflight_status(collection_name="wrong", source_count=0, chunk_count=0)
        ),
        database_path=tmp_path / "logs" / "pilot.db",
        session_labels=[],
    )

    assert report.ok is False
    failed = {check.check for check in report.checks if check.status == "FAIL"}
    assert {"vector_collection", "source_count", "chunk_count"} <= failed


def test_expanded_evaluation_has_required_scope_mix_and_preserves_baseline() -> None:
    questions = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
    counts: dict[str, int] = {}
    for question in questions:
        counts[question["scope_label"]] = counts.get(question["scope_label"], 0) + 1

    assert len(questions) >= 60
    assert counts["in_corpus"] >= 28
    assert counts["out_of_domain"] + counts[
        "university_admin_but_out_of_corpus"
    ] >= 20
    assert counts["ambiguous_scope"] >= 10
    assert all(question.get("reviewer_notes") for question in questions)
