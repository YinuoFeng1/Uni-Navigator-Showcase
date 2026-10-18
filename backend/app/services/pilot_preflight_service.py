from __future__ import annotations

from dataclasses import asdict, dataclass
import os
from pathlib import Path
from typing import Any, Iterable

from app.config import Settings
from app.database import DB_PATH
from app.services.corpus_manifest import manifest_path
from app.services.corpus_scope_service import load_scope_registry
from app.services.study_tasks import active_study_tasks
from app.services.vector_store import get_vector_store
from app.core.runtime_config import build_runtime_config_snapshot
from app.services.experimental_condition_service import ExperimentalConditionService
from app.services.interaction_provenance import (
    corpus_manifest_fingerprint,
    scope_registry_fingerprint,
)
from app.services.manifest_service import manifest_checksum
from app.services.pilot_release_service import (
    PilotReleaseService,
    is_pinned_app_revision,
)


@dataclass(frozen=True)
class PreflightCheck:
    check: str
    status: str
    detail: str
    check_id: str
    severity: str
    message: str
    researcher_action: str
    safe_detail: str


@dataclass(frozen=True)
class PilotPreflightReport:
    ok: bool
    checks: list[PreflightCheck]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "checks": [asdict(check) for check in self.checks],
        }


def run_pilot_preflight(
    settings: Settings,
    *,
    vector_store: Any | None = None,
    database_path: Path | None = None,
    session_labels: Iterable[str] | None = None,
    condition_service: ExperimentalConditionService | None = None,
    release_service: PilotReleaseService | None = None,
) -> PilotPreflightReport:
    checks: list[PreflightCheck] = []

    _check(
        checks,
        "study_mode",
        settings.study_mode == "pilot",
        f"configured={settings.study_mode}",
    )
    _check(
        checks,
        "answer_provider",
        settings.ai_provider == "openai"
        and bool(getattr(settings, "openai_api_key", "").strip()),
        (
            f"provider={settings.ai_provider}; answer_mode={settings.answer_mode}; "
            f"api_key_configured={bool(getattr(settings, 'openai_api_key', '').strip())}"
        ),
    )
    _check(
        checks,
        "live_answer_mode",
        settings.answer_mode == "live_llm",
        f"answer_mode={settings.answer_mode}",
    )
    _check(
        checks,
        "embedding_provider",
        settings.embedding_provider == settings.pilot_expected_embedding_provider
        and settings.embedding_provider != "mock",
        f"configured={settings.embedding_provider}; expected={settings.pilot_expected_embedding_provider}",
    )
    _check(
        checks,
        "embedding_model",
        settings.embedding_model == settings.pilot_expected_embedding_model,
        f"configured={settings.embedding_model}; expected={settings.pilot_expected_embedding_model}",
    )
    _check(
        checks,
        "vector_fallback",
        not settings.vector_store_allow_fallback,
        f"allow_fallback={settings.vector_store_allow_fallback}",
    )
    thresholds_valid = (
        settings.retrieval_partial_score_threshold > 0
        and settings.retrieval_grounded_score_threshold
        > settings.retrieval_partial_score_threshold
    )
    _check(
        checks,
        "retrieval_thresholds",
        thresholds_valid,
        (
            f"partial={settings.retrieval_partial_score_threshold}; "
            f"grounded={settings.retrieval_grounded_score_threshold}"
        ),
    )

    try:
        registry = load_scope_registry(settings.scope_registry_path)
        _check(
            checks,
            "scope_registry",
            True,
            f"version={registry.get('registry_version')}",
        )
    except ValueError as exc:
        _check(checks, "scope_registry", False, str(exc))

    expected_manifest = manifest_path(
        settings.vector_store_path, settings.vector_collection_name
    )
    _check(
        checks,
        "corpus_manifest",
        expected_manifest.is_file(),
        f"path={expected_manifest}",
    )

    store = vector_store
    status = None
    try:
        store = store or get_vector_store(settings)
        status = store.status()
        _check(
            checks,
            "vector_provider",
            status.active_provider == settings.pilot_expected_vector_provider
            and not status.fallback_used,
            (
                f"active={status.active_provider}; expected="
                f"{settings.pilot_expected_vector_provider}; fallback={status.fallback_used}"
            ),
        )
        _check(
            checks,
            "vector_collection",
            status.collection_name == settings.pilot_expected_vector_collection,
            (
                f"active={status.collection_name}; expected="
                f"{settings.pilot_expected_vector_collection}"
            ),
        )
        _check(
            checks,
            "source_count",
            status.source_count == settings.pilot_expected_source_count,
            f"active={status.source_count}; expected={settings.pilot_expected_source_count}",
        )
        _check(
            checks,
            "chunk_count",
            status.chunk_count == settings.pilot_expected_chunk_count,
            f"active={status.chunk_count}; expected={settings.pilot_expected_chunk_count}",
        )
        query_dimension = status.embedding_dimension
        if not query_dimension:
            raise RuntimeError("active collection has no embedding dimension")
        store.query([0.0] * query_dimension, top_k=1)
        _check(checks, "chroma_query", True, "query completed")
    except Exception as exc:
        _check(
            checks,
            "chroma_query",
            False,
            f"query unavailable ({type(exc).__name__})",
        )

    modern_release_boundary = hasattr(settings, "pilot_release_manifest_path")
    if modern_release_boundary:
        _run_release_checks(
            checks,
            settings=settings,
            vector_status=status,
            condition_service=condition_service,
            release_service=release_service,
        )

    try:
        tasks = active_study_tasks()
        required_fields = {
            "task_id",
            "title",
            "scenario",
            "task_type",
            "expected_safe_behaviour",
            "escalation_expected",
        }
        tasks_valid = bool(tasks) and all(
            required_fields <= set(task.keys()) for task in tasks
        )
        _check(
            checks,
            "study_tasks",
            tasks_valid,
            f"active_task_count={len(tasks)}",
        )
    except (OSError, ValueError) as exc:
        _check(checks, "study_tasks", False, f"unavailable ({type(exc).__name__})")

    db_path = database_path or DB_PATH
    parent_writable = db_path.parent.is_dir() and os.access(db_path.parent, os.W_OK)
    file_writable = not db_path.exists() or os.access(db_path, os.W_OK)
    _check(
        checks,
        "database_writable",
        parent_writable and file_writable,
        f"path={db_path}",
    )

    labels = list(session_labels) if session_labels is not None else _session_labels()
    synthetic_labels = [
        label
        for label in labels
        if any(marker in label.lower() for marker in ("synthetic", "test", "demo"))
    ]
    synthetic_ok = not synthetic_labels or settings.pilot_allow_synthetic_sessions
    _check(
        checks,
        "synthetic_sessions",
        synthetic_ok,
        (
            f"detected={len(synthetic_labels)}; explicit_warning="
            f"{settings.pilot_allow_synthetic_sessions}"
        ),
    )

    return PilotPreflightReport(
        ok=all(check.status != "FAIL" for check in checks), checks=checks
    )


def _session_labels() -> list[str]:
    try:
        from sqlmodel import Session, select

        from app.database import engine
        from app.models import StudySession

        with Session(engine) as session:
            return [
                row.participant_label
                for row in session.exec(select(StudySession)).all()
            ]
    except Exception:
        return []


def _check(
    checks: list[PreflightCheck],
    check: str,
    passed: bool,
    detail: str,
    *,
    severity: str = "critical",
    researcher_action: str = "Review this check before participant activation.",
) -> None:
    status = "PASS" if passed else "FAIL"
    checks.append(
        PreflightCheck(
            check=check,
            status=status,
            detail=detail,
            check_id=check,
            severity=severity,
            message=f"{check} {status.lower()}",
            researcher_action="" if passed else researcher_action,
            safe_detail=detail,
        )
    )


def _run_release_checks(
    checks: list[PreflightCheck],
    *,
    settings: Settings,
    vector_status: Any | None,
    condition_service: ExperimentalConditionService | None,
    release_service: PilotReleaseService | None,
) -> None:
    conditions = condition_service or ExperimentalConditionService(
        settings.condition_manifest_path
    )
    releases = release_service or PilotReleaseService(
        settings.pilot_release_manifest_path,
        settings.active_pilot_release_path,
    )
    try:
        release = releases.load_manifest()
        _check(
            checks,
            "execution_context",
            settings.execution_context == "participant_study"
            and release.get("execution_context") == "participant_study",
            (
                f"configured={settings.execution_context}; "
                f"release={release.get('execution_context')}"
            ),
        )
        _check(
            checks,
            "live_answer_mode_release",
            settings.answer_mode == "live_llm"
            and release.get("selected_answer_mode") == "live_llm"
            and release.get("allowed_answer_modes") == ["live_llm"],
            (
                f"configured={settings.answer_mode}; "
                f"release={release.get('selected_answer_mode')}"
            ),
        )
        _check(
            checks,
            "release_frozen",
            release.get("release_status") == "frozen",
            f"release_status={release.get('release_status')}",
            researcher_action=(
                "Review the complete system configuration, then explicitly freeze "
                "a new immutable pilot release."
            ),
        )
        release_provider_matches = bool(vector_status) and (
            release.get("ai_provider") == settings.ai_provider == "openai"
            and release.get("ai_model") == settings.ai_model
            and release.get("prompt_template_version")
            == settings.prompt_template_version
            and release.get("generation_temperature")
            == settings.generation_temperature
            and release.get("generation_max_tokens")
            == settings.generation_max_tokens
            and release.get("generation_reasoning_effort")
            == settings.generation_reasoning_effort
            and release.get("embedding_provider") == settings.embedding_provider
            and release.get("embedding_model") == settings.embedding_model
            and release.get("embedding_dimension")
            == getattr(vector_status, "embedding_dimension", None)
            and release.get("vector_store_provider")
            == getattr(vector_status, "active_provider", None)
            and release.get("vector_store_collection")
            == getattr(vector_status, "collection_name", None)
            and release.get("fallback_enabled") is False
            and not getattr(vector_status, "fallback_used", True)
            and release.get("retrieval_partial_threshold")
            == settings.retrieval_partial_score_threshold
            and release.get("retrieval_grounded_threshold")
            == settings.retrieval_grounded_score_threshold
            and release.get("retrieval_top_k") == settings.retrieval_top_k
            and release.get("retrieval_source_mode")
            == settings.retrieval_source_mode
            and release.get("scope_registry_fingerprint")
            == scope_registry_fingerprint(settings.scope_registry_path)
            and release.get("app_revision") == settings.app_revision
        )
        _check(
            checks,
            "release_provider_binding",
            release_provider_matches,
            "release model/prompt/generation/retrieval configuration compared with active runtime",
        )

        condition_manifest = conditions.load_manifest()
        condition_report = conditions.validate()
        _check(
            checks,
            "condition_equivalence",
            condition_report.valid,
            f"errors={len(condition_report.errors)}; warnings={len(condition_report.warnings)}",
        )
        _check(
            checks,
            "task_manifest_version",
            release.get("task_manifest_version")
            == settings.task_manifest_version,
            (
                f"release={release.get('task_manifest_version')}; "
                f"configured={settings.task_manifest_version}"
            ),
        )
        release_report = releases.validate(
            condition_manifest_checksum=manifest_checksum(condition_manifest),
        )
        _check(
            checks,
            "release_components",
            release_report.valid,
            (
                f"errors={len(release_report.errors)}; "
                f"warnings={len(release_report.warnings)}"
            ),
        )
        _check(
            checks,
            "corpus_fingerprint",
            release.get("corpus_fingerprint")
            == corpus_manifest_fingerprint(settings),
            "release corpus fingerprint compared with active ingestion manifest",
        )
        _check(
            checks,
            "scope_registry_fingerprint",
            release.get("scope_registry_fingerprint")
            == scope_registry_fingerprint(settings.scope_registry_path),
            "release scope registry fingerprint compared with active registry content",
        )
        if release.get("release_status") == "frozen" and vector_status is not None:
            releases.validate_runtime_binding(
                release=release,
                settings=settings,
                vector_status=vector_status,
            )
        runtime = build_runtime_config_snapshot(
            settings,
            environment={},
            vector_status=vector_status,
            release_context=releases.runtime_context(release),
        )
        _check(
            checks,
            "runtime_config_fingerprint",
            bool(runtime.runtime_config_fingerprint),
            f"fingerprint={runtime.runtime_config_fingerprint}",
        )
        _check(
            checks,
            "app_revision",
            is_pinned_app_revision(str(settings.app_revision)),
            f"app_revision={settings.app_revision}",
            researcher_action=(
                "Set APP_REVISION and the release manifest app_revision to the "
                "exact Git commit SHA before freezing."
            ),
        )
    except Exception as exc:
        _check(
            checks,
            "release_boundary",
            False,
            f"release validation unavailable ({type(exc).__name__})",
        )
