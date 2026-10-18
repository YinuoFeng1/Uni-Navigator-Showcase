from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from app.core.errors import ApplicationError
from app.core.runtime_config import RuntimeConfigError, build_runtime_config_snapshot
from app.domain.lifecycle import (
    InteractionState,
    StudySessionState,
    StudyTaskState,
    guard_final_response,
    guard_session_activation,
    guard_task_completion,
    guard_task_start,
)
from app.models import InteractionLog, StudyEventLog
from app.services.event_repository import EventRepository
from app.services.experimental_condition_service import ExperimentalConditionService
from app.services.manifest_service import manifest_checksum
from app.services.pilot_release_service import (
    PilotReleaseService,
    build_frozen_release_artifacts,
)
from app.services.provider_registry import ProviderRegistry
from app.services.technical_evaluation_service import TechnicalEvaluationService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONDITION_PATH = PROJECT_ROOT / "data" / "study" / "experimental_conditions.json"
RELEASE_PATH = PROJECT_ROOT / "data" / "study" / "pilot_release_manifest.json"
EVALUATION_PATH = PROJECT_ROOT / "data" / "evaluation" / "live_rag_task_questions.json"


def _runtime_settings(**overrides):
    values = {
        "study_mode": "development",
        "execution_context": "development",
        "answer_mode": "live_llm",
        "app_revision": "test-revision",
        "ai_provider": "openai",
        "ai_model": "gpt-4o-mini",
        "prompt_template_version": "grounded-v9",
        "generation_temperature": 0.0,
        "generation_max_tokens": 500,
        "generation_reasoning_effort": "none",
        "embedding_provider": "mock",
        "embedding_model": "mock-embedding",
        "vector_store_provider": "local_json",
        "vector_collection_name": "test_collection",
        "vector_store_allow_fallback": True,
        "retrieval_partial_score_threshold": 0.15,
        "retrieval_grounded_score_threshold": 0.35,
        "retrieval_top_k": 5,
        "retrieval_source_mode": "official",
        "task_manifest_version": "tasks-v1",
        "openai_api_key": "secret-must-not-appear",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_runtime_snapshot_fingerprint_is_stable_and_secret_free() -> None:
    settings = _runtime_settings()
    first = build_runtime_config_snapshot(settings, environment={})
    second = build_runtime_config_snapshot(settings, environment={})

    assert first.runtime_config_fingerprint == second.runtime_config_fingerprint
    serialized = json.dumps(first.canonical_dict(), sort_keys=True)
    assert "secret-must-not-appear" not in serialized
    assert "OPENAI_API_KEY" not in serialized


def test_runtime_snapshot_change_and_precedence() -> None:
    settings = _runtime_settings(ai_model="settings-model")
    environment_snapshot = build_runtime_config_snapshot(
        settings,
        environment={"AI_MODEL": "environment-model"},
        local_config={"ai_model": "local-model"},
    )
    override_snapshot = build_runtime_config_snapshot(
        settings,
        environment={"AI_MODEL": "environment-model"},
        local_config={"ai_model": "local-model"},
        overrides={"ai_model": "override-model"},
    )

    assert environment_snapshot.ai_model == "environment-model"
    assert override_snapshot.ai_model == "override-model"
    assert (
        environment_snapshot.runtime_config_fingerprint
        != override_snapshot.runtime_config_fingerprint
    )


@pytest.mark.parametrize(
    ("answer_mode", "ai_provider", "message"),
    [
        ("mock", "openai", "answer_mode"),
        ("live_llm", "mock", "ai_provider"),
        ("validated_fixed", "openai", "answer_mode"),
    ],
)
def test_participant_runtime_rejects_non_live_or_mock_configuration(
    answer_mode: str, ai_provider: str, message: str
) -> None:
    settings = _runtime_settings(
        study_mode="pilot",
        execution_context="participant_study",
        answer_mode=answer_mode,
        ai_provider=ai_provider,
        vector_store_provider="chroma",
        vector_store_allow_fallback=False,
    )
    with pytest.raises(RuntimeConfigError, match=message):
        build_runtime_config_snapshot(
            settings,
            environment={},
            release_context={
                "pilot_release_id": "release-test",
                "pilot_release_version": "1.0.0",
            },
        )


def test_participant_runtime_accepts_live_openai_configuration() -> None:
    settings = _runtime_settings(
        study_mode="pilot",
        execution_context="participant_study",
        answer_mode="live_llm",
        ai_provider="openai",
        embedding_provider="openai",
        vector_store_provider="chroma",
        vector_store_allow_fallback=False,
    )
    snapshot = build_runtime_config_snapshot(
        settings,
        environment={},
        release_context={
            "pilot_release_id": "release-test",
            "pilot_release_version": "1.0.0",
        },
    )
    assert snapshot.answer_mode == "live_llm"
    assert snapshot.ai_provider == "openai"


class _FakeAI:
    provider_name = "openai"


class _FakeEmbedding:
    provider_name = "openai"


class _FakeVector:
    def __init__(self, *, fallback: bool = False):
        self._status = SimpleNamespace(
            active_provider="chroma",
            fallback_used=fallback,
            embedding_dimension=1536,
            collection_name="test_collection",
        )

    def status(self):
        return self._status


def test_provider_registry_prohibits_participant_vector_fallback() -> None:
    settings = _runtime_settings(
        execution_context="participant_study",
        answer_mode="live_llm",
        ai_provider="openai",
        embedding_provider="openai",
        vector_store_provider="chroma",
    )
    with pytest.raises(ApplicationError) as exc_info:
        ProviderRegistry(
            settings,
            ai_provider=_FakeAI(),
            embedding_provider=_FakeEmbedding(),
            vector_store=_FakeVector(fallback=True),
        )
    assert exc_info.value.code == "vector_store_unavailable"


def test_condition_manifest_uses_only_live_llm(tmp_path: Path) -> None:
    service = ExperimentalConditionService(CONDITION_PATH)
    assert service.validate().valid is True
    assert {item["answer_mode"] for item in service.load_manifest()["conditions"]} == {
        "live_llm"
    }

    manifest = deepcopy(service.load_manifest())
    manifest["conditions"][0]["answer_mode"] = "mock"
    manifest["manifest_checksum"] = manifest_checksum(manifest)
    path = tmp_path / "conditions.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert ExperimentalConditionService(path).validate().valid is False


def test_release_lifecycle_blocks_draft_and_retired(tmp_path: Path) -> None:
    release = deepcopy(json.loads(RELEASE_PATH.read_text(encoding="utf-8")))
    release_path = tmp_path / "release.json"
    pointer_path = tmp_path / "pointer.json"
    pointer = {
        "active_release_id": release["release_id"],
        "active_release_version": release["release_version"],
    }
    release_path.write_text(json.dumps(release), encoding="utf-8")
    pointer_path.write_text(json.dumps(pointer), encoding="utf-8")
    service = PilotReleaseService(release_path, pointer_path)
    with pytest.raises(ApplicationError) as draft_error:
        service.resolve_active_release(require_frozen=True)
    assert draft_error.value.code == "release_not_frozen"

    release["release_status"] = "retired"
    release["manifest_checksum"] = manifest_checksum(release)
    release_path.write_text(json.dumps(release), encoding="utf-8")
    with pytest.raises(ApplicationError) as retired_error:
        service.resolve_active_release(require_frozen=True)
    assert retired_error.value.code == "release_retired"


def test_release_finalization_freezes_system_configuration() -> None:
    conditions = json.loads(CONDITION_PATH.read_text(encoding="utf-8"))
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    release["app_revision"] = "0123456789abcdef0123456789abcdef01234567"
    approval = {
        "release_id": "uq-pilot-2026-01",
        "release_version": "1.0.0",
        "reviewer": "test-reviewer",
        "reviewed_at": "2026-08-27T10:00:00+10:00",
        "reviewer_notes": "Model, prompt, retrieval and corpus configuration reviewed.",
        "human_review_confirmed": True,
    }

    artifacts = build_frozen_release_artifacts(
        condition_manifest=conditions,
        release_manifest=release,
        approval_record=approval,
    )
    assert artifacts.release["release_status"] == "frozen"
    assert artifacts.release["selected_answer_mode"] == "live_llm"
    assert artifacts.release["ai_provider"] == "openai"
    assert artifacts.release["manifest_checksum"] == manifest_checksum(
        artifacts.release
    )
    assert artifacts.active_pointer["active_release_id"] == "uq-pilot-2026-01"

    approval["human_review_confirmed"] = False
    with pytest.raises(ApplicationError):
        build_frozen_release_artifacts(
            condition_manifest=conditions,
            release_manifest=release,
            approval_record=approval,
        )


def test_release_finalization_rejects_unpinned_app_revision() -> None:
    conditions = json.loads(CONDITION_PATH.read_text(encoding="utf-8"))
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    release["app_revision"] = "development"
    approval = {
        "release_id": "uq-pilot-2026-01",
        "release_version": "1.0.0",
        "reviewer": "test-reviewer",
        "reviewed_at": "2026-08-27T10:00:00+10:00",
        "reviewer_notes": "System configuration reviewed.",
        "human_review_confirmed": True,
    }

    with pytest.raises(ApplicationError) as error:
        build_frozen_release_artifacts(
            condition_manifest=conditions,
            release_manifest=release,
            approval_record=approval,
        )

    assert "Git commit SHA" in error.value.researcher_safe_detail


def test_lifecycle_guards_cover_critical_transitions() -> None:
    with pytest.raises(ApplicationError):
        guard_session_activation(
            notice_acknowledged=False, release_frozen=True, preflight_ok=True
        )
    with pytest.raises(ApplicationError):
        guard_task_start(
            session_state=StudySessionState.COMPLETED,
            current_task_id=None,
            task_id="task-1",
        )
    with pytest.raises(ApplicationError):
        guard_task_start(
            session_state=StudySessionState.ACTIVE,
            current_task_id="task-1",
            task_id="task-2",
        )
    with pytest.raises(ApplicationError):
        guard_task_completion(
            task_state=StudyTaskState.ACTIVE, final_response_exists=False
        )
    with pytest.raises(ApplicationError):
        guard_final_response(
            task_state=StudyTaskState.ACTIVE,
            interaction_state=InteractionState.FAILED,
        )


def test_event_repository_envelope_idempotency_and_privacy(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'events.db'}")
    SQLModel.metadata.create_all(engine)
    repository = EventRepository()
    with Session(engine) as session:
        first = repository.append(
            session,
            event_type="system_failure",
            payload={
                "error_code": "provider_unavailable",
                "failure_stage": "answer_provider",
                "researcher_action": "pause",
            },
            idempotency_key="same-event",
        )
        second = repository.append(
            session,
            event_type="system_failure",
            payload={
                "error_code": "provider_unavailable",
                "failure_stage": "answer_provider",
                "researcher_action": "pause",
            },
            idempotency_key="same-event",
        )
        session.commit()
        events = session.exec(select(StudyEventLog)).all()
    assert first.event_id == second.event_id
    assert len(events) == 1

    with Session(engine) as session, pytest.raises(ValueError):
        repository.append(
            session,
            event_type="system_failure",
            payload={"question": "sensitive participant text"},
        )


def test_interaction_schema_has_no_fixed_answer_fields() -> None:
    fields = set(InteractionLog.model_fields)
    assert "answer_package_id" not in fields
    assert "answer_package_version" not in fields
    assert "package_content_checksum" not in fields
    assert "package_match_method" not in fields


def test_converted_question_dataset_has_no_prebuilt_answers() -> None:
    payload = json.loads(EVALUATION_PATH.read_text(encoding="utf-8"))
    assert len(payload["cases"]) == 7
    assert all(case["questions"] for case in payload["cases"])
    serialized = json.dumps(payload)
    for obsolete_key in (
        "plain_language_answer",
        "answer_package_id",
        "package_version",
        "content_checksum",
    ):
        assert obsolete_key not in serialized


class _FakeTechnicalRepository:
    def __init__(self):
        self.records = []

    def append(self, record):
        self.records.append(record)


def test_technical_evaluation_rejects_participant_persistence() -> None:
    orchestrator = SimpleNamespace(
        runtime=SimpleNamespace(
            execution_context="technical_evaluation", answer_mode="live_llm"
        )
    )
    repository = _FakeTechnicalRepository()
    service = TechnicalEvaluationService(orchestrator, repository)
    with pytest.raises(ApplicationError) as exc_info:
        service.run(
            run_id="run-1",
            query_id="query-1",
            question="A technical query",
            participant_session_id="session-forbidden",
        )
    assert exc_info.value.code == "client_context_mismatch"
    assert repository.records == []
