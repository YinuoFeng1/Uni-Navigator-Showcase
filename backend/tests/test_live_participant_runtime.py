from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.api.chat import _resolve_server_context, chat
from app.application.chat_orchestrator import ChatOrchestrator
from app.core.errors import ApplicationError
from app.core.runtime_config import RuntimeConfigSnapshot
from app.models import InteractionLog, StudyEventLog, StudySession
from app.schemas import ChatRequest
from app.services.ai_provider import AIProviderResult
from app.services.answer_strategies import LiveLlmAnswerStrategy
from app.services.event_repository import EventRepository


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class _ObservableOpenAIProvider:
    provider_name = "openai"

    def __init__(self) -> None:
        self.questions: list[str] = []

    def generate_answer(self, question: str, **kwargs) -> AIProviderResult:
        self.questions.append(question)
        labels = " ".join(kwargs.get("citation_labels") or [])
        return AIProviderResult(
            text=(
                "A student may apply for a deferred examination after illness "
                f"{labels}."
            ),
            provider_name="openai",
            model_name="gpt-4o-mini-2024-07-18",
            provider_mode="openai",
            retrieval_status="grounded",
            limitations="Limited to the retrieved policy evidence.",
            provider_response_id="resp_live_test",
            token_usage={
                "input_tokens": 80,
                "output_tokens": 20,
                "total_tokens": 100,
            },
        )


class _VectorStore:
    def status(self):
        return SimpleNamespace(
            active_provider="chroma",
            fallback_used=False,
            embedding_dimension=1536,
            collection_name="uni_navigator_policy_chunks_openai",
        )


class _ReleaseService:
    release = {
        "release_id": "release-live-test",
        "release_version": "1.0.0",
    }

    def resolve_active_release(self, *, require_frozen: bool):
        assert require_frozen is True
        return self.release

    def validate(self, *, condition_manifest_checksum: str):
        assert condition_manifest_checksum
        return SimpleNamespace(valid=True)

    def validate_runtime_binding(self, *, release, settings, vector_status) -> None:
        assert release == self.release
        assert settings.execution_context == "participant_study"
        assert vector_status.active_provider == "chroma"

    def validate_session_binding(
        self, *, session_release_id, session_release_version, release
    ) -> None:
        assert session_release_id == release["release_id"]
        assert session_release_version == release["release_version"]


class _ConditionService:
    def load_manifest(self):
        return {"condition_manifest": "test"}

    def get_condition(self, condition_id: str):
        assert condition_id == "C_HIGHLIGHT"
        return {
            "condition_id": condition_id,
            "condition_version": "2.0.0",
            "answer_mode": "live_llm",
            "active": True,
        }


def _settings() -> SimpleNamespace:
    return SimpleNamespace(
        study_mode="pilot",
        execution_context="participant_study",
        answer_mode="live_llm",
        app_revision="test-revision",
        ai_provider="openai",
        ai_model="gpt-4o-mini-2024-07-18",
        prompt_template_version="grounded-v9",
        generation_temperature=0.0,
        generation_max_tokens=400,
        generation_reasoning_effort="none",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        vector_store_provider="chroma",
        vector_store_allow_fallback=False,
        vector_store_path=PROJECT_ROOT / "data" / "vector_store" / "unused-test",
        vector_collection_name="uni_navigator_policy_chunks_openai",
        retrieval_partial_score_threshold=0.35,
        retrieval_grounded_score_threshold=0.55,
        retrieval_top_k=5,
        retrieval_source_mode="official",
        scope_registry_path=PROJECT_ROOT / "data" / "corpus" / "corpus_scope.json",
        task_manifest_version="study-tasks-test",
    )


def _runtime() -> RuntimeConfigSnapshot:
    return RuntimeConfigSnapshot(
        study_mode="pilot",
        execution_context="participant_study",
        answer_mode="live_llm",
        app_revision="test-revision",
        ai_provider="openai",
        ai_model="gpt-4o-mini-2024-07-18",
        prompt_template_version="grounded-v9",
        generation_temperature=0.0,
        generation_max_tokens=400,
        generation_reasoning_effort="none",
        embedding_provider="openai",
        embedding_model="text-embedding-3-small",
        embedding_dimension=1536,
        vector_store_provider_requested="chroma",
        vector_store_provider_active="chroma",
        vector_store_collection="uni_navigator_policy_chunks_openai",
        vector_store_fallback_enabled=False,
        retrieval_partial_threshold=0.35,
        retrieval_grounded_threshold=0.55,
        retrieval_top_k=5,
        retrieval_source_mode="official",
        corpus_fingerprint="sha256:test-corpus",
        corpus_manifest_version="test-corpus-v1",
        scope_registry_version="2026-09-02.1",
        scope_registry_fingerprint="sha256:test-scope",
        pilot_release_id="release-live-test",
        pilot_release_version="1.0.0",
        condition_id=None,
        condition_version=None,
        task_manifest_version="study-tasks-test",
    )


@pytest.mark.parametrize("chat_workflow", [False, True])
def test_formal_participant_chat_logs_only_live_llm_provenance(
    monkeypatch, tmp_path: Path, chat_workflow: bool
) -> None:
    question = "I missed my exam because I was unwell. How do I apply?"
    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *_, **__: [
            {
                "chunk_id": "uq_examinations_procedure_chunk_0011",
                "source_id": "uq-examinations-procedure",
                "title": "Examinations Procedure",
                "document_name": "Examinations Procedure",
                "section": "Deferred examinations",
                "url": "https://policies.uq.edu.au/example",
                "source_type": "official_policy",
                "chunk_text": "A student may apply for a deferred examination after illness.",
                "page_start": 12,
                "page_end": 12,
                "score": 0.91,
                "active": True,
            }
        ],
    )
    settings = _settings()
    provider = _ObservableOpenAIProvider()
    orchestrator = ChatOrchestrator(
        settings=settings,
        runtime=_runtime(),
        answer_strategy=LiveLlmAnswerStrategy(provider),
        embedding_provider=object(),
        vector_store=_VectorStore(),
    )
    container = SimpleNamespace(
        releases=_ReleaseService(),
        conditions=_ConditionService(),
        chat_orchestrator=orchestrator,
        events=EventRepository(),
        runtime=_runtime(),
    )
    monkeypatch.setattr("app.api.chat.get_settings", lambda: settings)

    engine = create_engine(f"sqlite:///{tmp_path / 'participant.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            StudySession(
                session_id="session-live-test",
                participant_label="P-LIVE",
                study_condition="C_HIGHLIGHT",
                current_task_id=None if chat_workflow else "task_special_consideration_illness",
                metadata_json=json.dumps({"workflow": "chat", "roundId": "pilot-01"}) if chat_workflow else None,
                state="active",
                release_id="release-live-test",
                release_version="1.0.0",
                condition_version="2.0.0",
                runtime_config_fingerprint=_runtime().runtime_config_fingerprint,
            )
        )
        session.commit()
        answer = chat(
            ChatRequest(
                question=question,
                sessionId="session-live-test",
                taskId=None if chat_workflow else "task_special_consideration_illness",
                condition="C_HIGHLIGHT",
            ),
            SimpleNamespace(
                app=SimpleNamespace(state=SimpleNamespace(container=container))
            ),
            session,
        )
        interaction = session.get(InteractionLog, answer.interactionId)
        served_event = session.exec(
            select(StudyEventLog).where(
                StudyEventLog.interaction_id == answer.interactionId,
                StudyEventLog.event_type == "interaction_served",
            )
        ).one()

    assert provider.questions == [question]
    assert answer.shortAnswer == (
        "A student may apply for a deferred examination after illness [1]."
    )
    assert interaction is not None
    assert interaction.answer_mode == "live_llm"
    assert interaction.ai_provider == "openai"
    assert interaction.ai_model_requested == "gpt-4o-mini-2024-07-18"
    assert interaction.provider_response_model == "gpt-4o-mini-2024-07-18"
    assert interaction.provider_response_id == "resp_live_test"
    assert interaction.total_tokens == 100
    assert interaction.scope_registry_fingerprint
    assert interaction.runtime_config_fingerprint == _runtime().runtime_config_fingerprint
    assert interaction.full_answer == answer.answer
    assert json.loads(interaction.retrieval_trace_json or "[]")[0]["rank"] == 1
    assert not any("package" in key for key in interaction.model_dump())
    event_payload = json.loads(served_event.payload_json or "{}")
    assert event_payload["answer_mode"] == "live_llm"
    assert not any("package" in key for key in event_payload)


def test_participant_chat_rejects_a_session_from_another_runtime(
    tmp_path: Path,
) -> None:
    settings = _settings()
    runtime = _runtime()
    container = SimpleNamespace(
        releases=_ReleaseService(),
        conditions=_ConditionService(),
        runtime=runtime,
        chat_orchestrator=SimpleNamespace(vector_store=_VectorStore()),
    )
    engine = create_engine(f"sqlite:///{tmp_path / 'runtime-mismatch.db'}")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(
            StudySession(
                session_id="session-old-runtime",
                participant_label="P-OLD",
                study_condition="C_HIGHLIGHT",
                current_task_id="task_special_consideration_illness",
                state="active",
                release_id="release-live-test",
                release_version="1.0.0",
                condition_version="2.0.0",
                runtime_config_fingerprint="sha256:old-runtime",
            )
        )
        session.commit()

        with pytest.raises(ApplicationError) as exc_info:
            _resolve_server_context(
                session,
                ChatRequest(
                    question="What should I do?",
                    sessionId="session-old-runtime",
                    taskId="task_special_consideration_illness",
                    condition="C_HIGHLIGHT",
                ),
                container,
                settings,
            )

    assert exc_info.value.code == "release_component_mismatch"
