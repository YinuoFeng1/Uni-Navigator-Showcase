import json

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models import InteractionLog, StudyEventLog
from app.services.ai_provider import AIProviderError, AIProviderResult, OpenAIProvider
from app.services.answer_strategies import LiveLlmAnswerStrategy


def _official_chunk() -> dict:
    return {
        "chunk_id": "uq_assessment_chunk_001",
        "source_id": "uq-assessment-procedure",
        "title": "Assessment Procedure",
        "document_name": "Assessment Procedure",
        "section": "Assessment extensions",
        "url": "https://policies.uq.edu.au/document/view-current.php?id=54",
        "source_type": "official_policy",
        "chunk_text": (
            "Students applying for an assessment extension may need supporting "
            "evidence explaining the effect of their circumstances."
        ),
        "page_start": 8,
        "page_end": 8,
        "score": 0.91,
        "active": True,
    }


def test_chat_rejects_empty_question(client) -> None:
    response = client.post("/api/chat", json={"question": ""})
    assert response.status_code == 422


def test_chat_returns_frontend_compatible_live_answer(client) -> None:
    response = client.post(
        "/api/chat",
        json={
            "question": "Can I apply for special consideration after missing an exam?",
            "participantId": "P001",
            "taskId": "T001",
            "condition": "C_HIGHLIGHT",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "id",
        "interactionId",
        "answer",
        "shortAnswer",
        "basedOn",
        "evidenceSummary",
        "nextStep",
        "limitations",
        "uncertainty",
        "uncertaintyLevel",
        "escalationRecommended",
        "escalationCategory",
        "escalationReasons",
        "highStakesDetected",
        "citations",
        "retrievalStatus",
        "escalationGuidance",
        "scopeDecision",
    }
    assert data["interactionId"].startswith("interaction_")
    assert data["answer"] == data["shortAnswer"]
    assert data["retrievalStatus"] == "insufficient_evidence"
    assert data["citations"] == []
    assert data["scopeDecision"]["decision"] == "possibly_in_scope"


def test_development_chat_uses_live_llm_provenance(client) -> None:
    response = client.post("/api/chat", json={"question": "When should I contact staff?"})

    assert response.status_code == 200
    interaction_id = response.json()["interactionId"]
    with Session(engine) as session:
        log = session.get(InteractionLog, interaction_id)
    assert log is not None
    assert log.answer_mode == "live_llm"
    assert log.ai_provider == "openai"
    assert log.execution_context == "development"


def test_openai_provider_missing_key_raises_instead_of_falling_back() -> None:
    provider = OpenAIProvider(
        model_name="gpt-4o-mini",
        timeout_seconds=1,
        api_key="",
        prompt_template_version="grounded-v9",
        generation_temperature=0,
        generation_max_tokens=100,
        generation_reasoning_effort="none",
    )
    with pytest.raises(AIProviderError, match="OPENAI_API_KEY"):
        provider.generate_answer("What is the policy?")


def test_provider_error_fails_closed_without_interaction_log(client) -> None:
    class FailingOpenAIProvider:
        provider_name = "openai"

        def generate_answer(self, *args, **kwargs):
            raise AIProviderError("provider unavailable")

    client.app.state.container.chat_orchestrator.answer_strategy = (
        LiveLlmAnswerStrategy(FailingOpenAIProvider())
    )
    response = client.post(
        "/api/chat",
        json={"question": "What evidence is needed for an assessment extension?"},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["errorCode"] == "provider_unavailable"
    with Session(engine) as session:
        assert session.get(InteractionLog, detail["interactionId"]) is None


def test_chat_returns_only_selected_official_citations(monkeypatch, client) -> None:
    prepared = {
        **_official_chunk(),
        "chunk_id": "prepared-1",
        "source_type": "prepared_policy",
    }
    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [_official_chunk(), prepared],
    )
    response = client.post(
        "/api/chat",
        json={"question": "What evidence is needed for an assessment extension?"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["retrievalStatus"] == "grounded"
    assert "[1]" in data["shortAnswer"]
    assert len(data["citations"]) == 1
    citation = data["citations"][0]
    assert citation["chunkId"] == "uq_assessment_chunk_001"
    assert citation["sourceType"] == "official_policy"
    assert citation["pageNumber"] == 8


def test_chat_logs_complete_retrieval_metadata(monkeypatch, client) -> None:
    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [_official_chunk()],
    )
    response = client.post(
        "/api/chat",
        json={"question": "What evidence is needed for an assessment extension?"},
    )

    assert response.status_code == 200
    data = response.json()
    with Session(engine) as session:
        log = session.get(InteractionLog, data["interactionId"])

    assert log is not None
    assert log.short_answer == data["shortAnswer"]
    assert log.full_answer == data["answer"]
    assert log.retrieval_status == data["retrievalStatus"]
    assert data["highStakesDetected"] is True
    assert data["escalationRecommended"] is False
    assert data["escalationCategory"] == "none"
    assert "escalationGuidance" not in data
    assert log.escalation_recommended is False
    assert log.escalation_category == "none"
    assert json.loads(log.escalation_reasons_json or "[]") == data[
        "escalationReasons"
    ]
    assert log.escalation_guidance is None
    assert log.citation_count == 1
    assert log.retrieved_context_count == 1
    assert log.citation_ids is not None and "c1" in log.citation_ids
    citations = json.loads(log.citations_json or "[]")
    assert citations[0]["chunkId"] == "uq_assessment_chunk_001"
    assert log.source_ids is not None and "uq-assessment-procedure" in log.source_ids
    retrieval_trace = json.loads(log.retrieval_trace_json or "[]")
    assert retrieval_trace == [
        {
            "citation_label": "[1]",
            "chunk_id": "uq_assessment_chunk_001",
            "distance": None,
            "page_end": 8,
            "page_start": 8,
            "rank": 1,
            "score": 0.91,
            "source_id": "uq-assessment-procedure",
            "source_type": "official_policy",
        }
    ]
    assert log.answer_mode == "live_llm"
    assert log.retrieval_mode == "official"
    assert log.response_time_ms is not None
    assert log.error_type is None
    assert log.ai_model_requested
    assert log.provider_response_model == "test-openai-model"
    assert log.provider_response_id == "resp_test_fixture"
    assert log.input_tokens == 120
    assert log.output_tokens == 30
    assert log.total_tokens == 150
    assert json.loads(log.token_usage_json or "{}")["total_tokens"] == 150
    assert log.prompt_template_version == "grounded-v9"
    assert log.scope_registry_fingerprint
    assert log.runtime_config_fingerprint
    assert json.loads(log.runtime_config_json or "{}")["retrieval_top_k"] == 5


def test_retrieval_error_fails_closed(monkeypatch, client) -> None:
    def fail_retrieval(*args, **kwargs):
        raise RuntimeError("vector store unavailable")

    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        fail_retrieval,
    )
    response = client.post(
        "/api/chat",
        json={"question": "What evidence is needed for an assessment extension?"},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["errorCode"] == "vector_store_unavailable"
    with Session(engine) as session:
        event = session.exec(
            select(StudyEventLog).where(
                StudyEventLog.interaction_id == detail["interactionId"]
            )
        ).one()
    payload = json.loads(event.payload_json or "{}")
    assert payload["error_code"] == "vector_store_unavailable"
    assert payload["response_time_ms"] >= 0
    assert payload["retrieval_status"] == "not_completed"
    assert payload["retrieval_trace"] == []
    assert payload["token_usage"] == {}
    assert payload["runtime_config"]["prompt_template_version"] == "grounded-v9"
    assert "openai_api_key" not in payload["runtime_config"]
    assert event.runtime_config_fingerprint


def test_missing_llm_citation_fails_validation(monkeypatch, client) -> None:
    class UncitedOpenAIProvider:
        provider_name = "openai"

        def __init__(self) -> None:
            self.calls = 0

        def generate_answer(self, *args, **kwargs) -> AIProviderResult:
            self.calls += 1
            return AIProviderResult(
                text="The policy may require evidence.",
                provider_name="openai",
                model_name="test-model",
                provider_mode="openai",
            )

    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [_official_chunk()],
    )
    provider = UncitedOpenAIProvider()
    client.app.state.container.chat_orchestrator.answer_strategy = (
        LiveLlmAnswerStrategy(provider)
    )
    response = client.post(
        "/api/chat",
        json={"question": "What evidence is needed for an assessment extension?"},
    )

    assert response.status_code == 503
    detail = response.json()["detail"]
    assert detail["errorCode"] == "citation_validation_failed"
    assert provider.calls == 2
    with Session(engine) as session:
        event = session.exec(
            select(StudyEventLog).where(
                StudyEventLog.interaction_id == detail["interactionId"]
            )
        ).one()
    failure_payload = json.loads(event.payload_json or "{}")
    assert failure_payload["retrieval_status"] == "grounded"
    assert failure_payload["retrieval_trace"][0]["rank"] == 1
    assert failure_payload["retrieval_trace"][0]["score"] == 0.91
    assert failure_payload["runtime_config"]["retrieval_top_k"] == 5


def test_invalid_first_draft_gets_one_audited_citation_revision(
    monkeypatch, client
) -> None:
    class RepairingOpenAIProvider:
        provider_name = "openai"

        def __init__(self) -> None:
            self.calls: list[dict] = []

        def generate_answer(self, *args, **kwargs) -> AIProviderResult:
            self.calls.append(kwargs)
            call_number = len(self.calls)
            return AIProviderResult(
                text=(
                    "The policy may require evidence."
                    if call_number == 1
                    else "The policy may require evidence [1]."
                ),
                provider_name="openai",
                model_name="test-model",
                provider_mode="openai",
                provider_response_id=f"resp_{call_number}",
                token_usage={
                    "input_tokens": 10 * call_number,
                    "output_tokens": 2 * call_number,
                    "total_tokens": 12 * call_number,
                },
            )

    provider = RepairingOpenAIProvider()
    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [_official_chunk()],
    )
    client.app.state.container.chat_orchestrator.answer_strategy = (
        LiveLlmAnswerStrategy(provider)
    )

    response = client.post(
        "/api/chat",
        json={"question": "What evidence is needed for an assessment extension?"},
    )

    assert response.status_code == 200
    assert len(provider.calls) == 2
    assert provider.calls[1]["previous_answer"] == "The policy may require evidence."
    assert "citation label" in provider.calls[1]["validation_feedback"]
    with Session(engine) as session:
        log = session.get(InteractionLog, response.json()["interactionId"])
    assert log is not None
    assert log.provider_response_id == "resp_2"
    assert log.input_tokens == 30
    assert log.output_tokens == 6
    assert log.total_tokens == 36


def test_unavailable_llm_citation_fails_validation(monkeypatch, client) -> None:
    class InventedCitationProvider:
        provider_name = "openai"

        def generate_answer(self, *args, **kwargs) -> AIProviderResult:
            return AIProviderResult(
                text="Supporting evidence may be required [9].",
                provider_name="openai",
                model_name="test-model",
                provider_mode="openai",
            )

    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [_official_chunk()],
    )
    client.app.state.container.chat_orchestrator.answer_strategy = (
        LiveLlmAnswerStrategy(InventedCitationProvider())
    )

    response = client.post(
        "/api/chat",
        json={"question": "What evidence is needed for an assessment extension?"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["errorCode"] == "citation_validation_failed"


def test_each_policy_sentence_requires_a_citation(monkeypatch, client) -> None:
    class PartlyCitedProvider:
        provider_name = "openai"

        def __init__(self) -> None:
            self.calls: list[dict] = []

        def generate_answer(self, *args, **kwargs) -> AIProviderResult:
            self.calls.append(kwargs)
            return AIProviderResult(
                text=(
                    "Supporting evidence may be required [1]. "
                    "The application must be submitted within five days."
                ),
                provider_name="openai",
                model_name="test-model",
                provider_mode="openai",
            )

    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [_official_chunk()],
    )
    provider = PartlyCitedProvider()
    client.app.state.container.chat_orchestrator.answer_strategy = (
        LiveLlmAnswerStrategy(provider)
    )

    response = client.post(
        "/api/chat",
        json={"question": "What evidence is needed for an assessment extension?"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["errorCode"] == "citation_validation_failed"
    assert len(provider.calls) == 2
    assert "application must be submitted" in provider.calls[1][
        "validation_feedback"
    ].lower()


@pytest.mark.parametrize(
    "limitation",
    [
        (
            "Whether UQ will approve your request is not established by the "
            "retrieved policy evidence."
        ),
        (
            "If your situation involves special circumstances, the retrieved "
            "official policy evidence does not establish whether it applies."
        ),
        (
            "Your personal booking step needs confirmation by authorised "
            "university staff."
        ),
        (
            "For your personal outcome, authorised university staff would "
            "need to confirm whether the decision is appealable."
        ),
    ],
)
def test_structured_uncertainty_sentences_do_not_require_citations(
    monkeypatch, client, limitation: str
) -> None:
    class LimitedOpenAIProvider:
        provider_name = "openai"

        def generate_answer(self, *args, **kwargs) -> AIProviderResult:
            return AIProviderResult(
                text=f"Supporting evidence may be required [1]. {limitation}",
                provider_name="openai",
                model_name="test-model",
                provider_mode="openai",
            )

    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [_official_chunk()],
    )
    client.app.state.container.chat_orchestrator.answer_strategy = (
        LiveLlmAnswerStrategy(LimitedOpenAIProvider())
    )

    response = client.post(
        "/api/chat",
        json={"question": "What evidence is needed for an assessment extension?"},
    )

    assert response.status_code == 200


def test_policy_claim_before_uncertainty_marker_still_requires_citation(
    monkeypatch, client
) -> None:
    class MixedClaimOpenAIProvider:
        provider_name = "openai"

        def generate_answer(self, *args, **kwargs) -> AIProviderResult:
            return AIProviderResult(
                text=(
                    "Supporting evidence may be required [1]. The deadline is "
                    "five days, but the retrieved official policy evidence does "
                    "not establish your eligibility."
                ),
                provider_name="openai",
                model_name="test-model",
                provider_mode="openai",
            )

    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [_official_chunk()],
    )
    provider = MixedClaimOpenAIProvider()
    client.app.state.container.chat_orchestrator.answer_strategy = (
        LiveLlmAnswerStrategy(provider)
    )

    response = client.post(
        "/api/chat",
        json={"question": "What evidence is needed for an assessment extension?"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["errorCode"] == "citation_validation_failed"


def test_source_backed_answer_cannot_begin_with_retrieval_narration(
    monkeypatch, client
) -> None:
    class RetrievalNarrationProvider:
        provider_name = "openai"

        def generate_answer(self, *args, **kwargs) -> AIProviderResult:
            return AIProviderResult(
                text="Based on the retrieved evidence, supporting evidence may be required [1].",
                provider_name="openai",
                model_name="test-model",
                provider_mode="openai",
            )

    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [_official_chunk()],
    )
    client.app.state.container.chat_orchestrator.answer_strategy = (
        LiveLlmAnswerStrategy(RetrievalNarrationProvider())
    )

    response = client.post(
        "/api/chat",
        json={"question": "What evidence is needed for an assessment extension?"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["errorCode"] == "citation_validation_failed"


def test_out_of_scope_answer_cannot_add_an_uncited_policy_rule(client) -> None:
    class HallucinatingProvider:
        provider_name = "openai"

        def generate_answer(self, *args, **kwargs) -> AIProviderResult:
            return AIProviderResult(
                text="Students may book a music room for two hours.",
                provider_name="openai",
                model_name="test-model",
                provider_mode="openai",
            )

    client.app.state.container.chat_orchestrator.answer_strategy = (
        LiveLlmAnswerStrategy(HallucinatingProvider())
    )

    response = client.post(
        "/api/chat",
        json={"question": "Where can I book a xylophone practice room?"},
    )

    assert response.status_code == 503
    assert response.json()["detail"]["errorCode"] == "citation_validation_failed"


def test_out_of_scope_answer_accepts_plain_insufficient_evidence_contraction(
    client,
) -> None:
    class SafeInsufficientEvidenceProvider:
        provider_name = "openai"

        def generate_answer(self, *args, **kwargs) -> AIProviderResult:
            return AIProviderResult(
                text=(
                    "There isn’t enough matching official policy evidence to "
                    "answer this question. Contact authorised university staff "
                    "for help with the next step."
                ),
                provider_name="openai",
                model_name="test-model",
                provider_mode="openai",
            )

    client.app.state.container.chat_orchestrator.answer_strategy = (
        LiveLlmAnswerStrategy(SafeInsufficientEvidenceProvider())
    )

    response = client.post(
        "/api/chat",
        json={"question": "Where can I book a xylophone practice room?"},
    )

    assert response.status_code == 200
    assert response.json()["retrievalStatus"] == "insufficient_evidence"
    assert response.json()["citations"] == []


def test_paraphrased_questions_keep_concrete_official_evidence(
    monkeypatch, client
) -> None:
    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [_official_chunk()],
    )
    questions = [
        "What evidence is needed for an assessment extension?",
        "I need more time for an assignment. What proof could I have to provide?",
    ]

    answers = [client.post("/api/chat", json={"question": item}) for item in questions]

    assert all(response.status_code == 200 for response in answers)
    for response in answers:
        payload = response.json()
        assert "supporting evidence" in payload["answer"].lower()
        assert "[1]" in payload["answer"]
        assert payload["citations"][0]["sourceType"] == "official_policy"


def test_openai_provider_forwards_generation_config_and_allowed_labels(
    monkeypatch,
) -> None:
    captured: dict = {}

    class Response:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "id": "resp_generation_config",
                "model": "gpt-4o-mini-2024-07-18",
                "output_text": "Supporting evidence may be required [1].",
                "usage": {
                    "input_tokens": 42,
                    "output_tokens": 8,
                    "total_tokens": 50,
                    "input_tokens_details": {"cached_tokens": 10},
                },
            }

    class RecordingClient:
        def __init__(self, *, timeout: float) -> None:
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            return None

        def post(self, url: str, *, headers: dict, json: dict) -> Response:
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = json
            return Response()

    monkeypatch.setattr("app.services.ai_provider.httpx.Client", RecordingClient)
    provider = OpenAIProvider(
        model_name="gpt-4o-mini-2024-07-18",
        timeout_seconds=12,
        api_key="test-key",
        prompt_template_version="grounded-v9",
        generation_temperature=0.2,
        generation_max_tokens=321,
        generation_reasoning_effort="none",
    )

    result = provider.generate_answer(
        "What evidence is needed?",
        retrieved_context="[1]\npassage: Supporting evidence may be required.",
        citation_labels=["[1]"],
        retrieval_status="grounded",
    )

    assert result.text.endswith("[1].")
    assert result.model_name == "gpt-4o-mini-2024-07-18"
    assert result.provider_response_id == "resp_generation_config"
    assert result.token_usage["total_tokens"] == 50
    assert result.token_usage["input_tokens_details"]["cached_tokens"] == 10
    assert captured["timeout"] == 12
    assert captured["payload"]["temperature"] == 0.2
    assert captured["payload"]["max_output_tokens"] == 321
    assert captured["payload"]["reasoning"] == {"effort": "none"}
    assert "Allowed citation labels: [1]" in captured["payload"]["input"]
    assert "Start with a direct answer" in captured["payload"]["instructions"]
    assert "Never write a standalone" in captured["payload"]["instructions"]
    assert "one sentence per paragraph" in captured["payload"]["instructions"]
    assert "silence is not policy evidence" in captured["payload"]["instructions"]
    assert "highest-ranked excerpt" in captured["payload"]["instructions"]
