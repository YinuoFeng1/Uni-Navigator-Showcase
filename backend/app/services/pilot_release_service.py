from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any

from app.core.errors import ApplicationError
from app.services.corpus_manifest import load_ingestion_manifest
from app.services.corpus_scope_service import load_scope_registry
from app.services.interaction_provenance import (
    corpus_manifest_fingerprint,
    scope_registry_fingerprint,
)
from app.services.manifest_service import manifest_checksum


RELEASE_STATES = {"draft", "review_required", "approved", "frozen", "retired"}
FROZEN_SYSTEM_FIELDS = {
    "execution_context",
    "selected_answer_mode",
    "allowed_answer_modes",
    "ai_provider",
    "ai_model",
    "prompt_template_version",
    "generation_temperature",
    "generation_max_tokens",
    "generation_reasoning_effort",
    "embedding_provider",
    "embedding_model",
    "embedding_dimension",
    "vector_store_provider",
    "vector_store_collection",
    "fallback_enabled",
    "corpus_fingerprint",
    "corpus_manifest_version",
    "scope_registry_version",
    "scope_registry_fingerprint",
    "retrieval_partial_threshold",
    "retrieval_grounded_threshold",
    "retrieval_top_k",
    "retrieval_source_mode",
    "task_manifest_version",
    "condition_manifest_checksum",
    "app_revision",
}


@dataclass(frozen=True)
class PilotReleaseValidation:
    valid: bool
    errors: list[str]
    warnings: list[str]


@dataclass(frozen=True)
class FrozenPilotReleaseArtifacts:
    release: dict[str, Any]
    active_pointer: dict[str, Any]


class PilotReleaseService:
    def __init__(self, manifest_path: str | Path, active_pointer_path: str | Path) -> None:
        self.manifest_path = Path(manifest_path)
        self.active_pointer_path = Path(active_pointer_path)

    def load_manifest(self) -> dict[str, Any]:
        return self._load_json(self.manifest_path, "pilot release manifest")

    def load_active_pointer(self) -> dict[str, Any]:
        return self._load_json(self.active_pointer_path, "active release pointer")

    def resolve_active_release(self, *, require_frozen: bool) -> dict[str, Any]:
        manifest = self.load_manifest()
        pointer = self.load_active_pointer()
        active_id = pointer.get("active_release_id")
        active_version = pointer.get("active_release_version")
        if not active_id or not active_version:
            raise ApplicationError(
                "release_not_frozen",
                researcher_safe_detail="no active pilot release is selected",
            )
        if (
            active_id != manifest.get("release_id")
            or active_version != manifest.get("release_version")
        ):
            raise ApplicationError(
                "release_component_mismatch",
                researcher_safe_detail="active pointer does not match release manifest",
            )
        if manifest.get("release_status") == "retired":
            raise ApplicationError(
                "release_retired",
                researcher_safe_detail="active release is retired",
            )
        if require_frozen and manifest.get("release_status") != "frozen":
            raise ApplicationError(
                "release_not_frozen",
                researcher_safe_detail="active release is not frozen",
            )
        return manifest

    def validate(
        self,
        *,
        condition_manifest_checksum: str | None = None,
        require_active_pointer: bool = True,
    ) -> PilotReleaseValidation:
        release = self.load_manifest()
        errors: list[str] = []
        warnings: list[str] = []
        if release.get("release_status") not in RELEASE_STATES:
            errors.append("invalid release state")
        if release.get("manifest_checksum") != manifest_checksum(release):
            errors.append("release manifest checksum mismatch")
        if condition_manifest_checksum and release.get(
            "condition_manifest_checksum"
        ) != condition_manifest_checksum:
            errors.append("condition manifest checksum mismatch")
        missing_fields = sorted(
            field for field in FROZEN_SYSTEM_FIELDS if field not in release
        )
        if missing_fields:
            errors.append(
                f"release is missing system configuration fields: {', '.join(missing_fields)}"
            )
        if release.get("selected_answer_mode") != "live_llm":
            errors.append("participant release must select live_llm")
        if release.get("allowed_answer_modes") != ["live_llm"]:
            errors.append("participant release must allow only live_llm")
        if release.get("ai_provider") != "openai":
            errors.append("participant release must use the OpenAI provider")
        if not _is_versioned_model(str(release.get("ai_model") or "")):
            errors.append("participant release must pin a dated model snapshot")
        app_revision_pinned = is_pinned_app_revision(
            str(release.get("app_revision") or "")
        )
        if release.get("release_status") == "frozen" and not app_revision_pinned:
            errors.append("frozen release must pin an exact Git commit revision")
        elif not app_revision_pinned:
            warnings.append(
                "draft app revision is not an exact Git commit; update it before freezing"
            )
        if release.get("fallback_enabled") is not False:
            errors.append("participant release must disable vector fallback")
        if release.get("release_status") != "frozen":
            warnings.append("release is not frozen and cannot start participant sessions")
        if require_active_pointer:
            pointer = self.load_active_pointer()
            if not pointer.get("active_release_id"):
                warnings.append("no active release pointer is selected")
            elif (
                pointer.get("active_release_id") != release.get("release_id")
                or pointer.get("active_release_version")
                != release.get("release_version")
            ):
                errors.append("active release pointer mismatch")
        return PilotReleaseValidation(not errors, errors, warnings)

    def validate_runtime_binding(
        self,
        *,
        release: dict[str, Any],
        settings: Any,
        vector_status: Any,
    ) -> None:
        expected = {
            "execution_context": settings.execution_context,
            "selected_answer_mode": settings.answer_mode,
            "ai_provider": settings.ai_provider,
            "ai_model": settings.ai_model,
            "prompt_template_version": settings.prompt_template_version,
            "generation_temperature": settings.generation_temperature,
            "generation_max_tokens": settings.generation_max_tokens,
            "generation_reasoning_effort": settings.generation_reasoning_effort,
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
            "embedding_dimension": getattr(vector_status, "embedding_dimension", None),
            "vector_store_provider": getattr(vector_status, "active_provider", None),
            "vector_store_collection": getattr(vector_status, "collection_name", None),
            "fallback_enabled": settings.vector_store_allow_fallback,
            "corpus_fingerprint": corpus_manifest_fingerprint(settings),
            "corpus_manifest_version": load_ingestion_manifest(
                settings.vector_store_path,
                settings.vector_collection_name,
            ).get("latest_ingestion_at"),
            "scope_registry_version": load_scope_registry(
                settings.scope_registry_path
            ).get("registry_version"),
            "scope_registry_fingerprint": scope_registry_fingerprint(
                settings.scope_registry_path
            ),
            "retrieval_partial_threshold": settings.retrieval_partial_score_threshold,
            "retrieval_grounded_threshold": settings.retrieval_grounded_score_threshold,
            "retrieval_top_k": settings.retrieval_top_k,
            "retrieval_source_mode": settings.retrieval_source_mode,
            "task_manifest_version": settings.task_manifest_version,
            "app_revision": settings.app_revision,
        }
        mismatches = [
            field
            for field, active_value in expected.items()
            if release.get(field) != active_value
        ]
        if getattr(vector_status, "fallback_used", False):
            mismatches.append("vector_store_fallback_used")
        if mismatches:
            raise ApplicationError(
                "release_component_mismatch",
                researcher_safe_detail=(
                    "active runtime differs from frozen system configuration: "
                    + ", ".join(sorted(set(mismatches)))
                ),
            )

    def validate_session_binding(
        self,
        *,
        session_release_id: str | None,
        session_release_version: str | None,
        release: dict[str, Any],
    ) -> None:
        if (
            session_release_id != release.get("release_id")
            or session_release_version != release.get("release_version")
        ):
            raise ApplicationError(
                "client_context_mismatch",
                researcher_safe_detail="session is not bound to active release",
            )

    @staticmethod
    def runtime_context(release: dict[str, Any]) -> dict[str, Any]:
        return {
            "study_mode": "pilot",
            "execution_context": release.get("execution_context"),
            "answer_mode": release.get("selected_answer_mode"),
            "app_revision": release.get("app_revision"),
            "ai_provider": release.get("ai_provider"),
            "ai_model": release.get("ai_model"),
            "prompt_template_version": release.get("prompt_template_version"),
            "generation_temperature": release.get("generation_temperature"),
            "generation_max_tokens": release.get("generation_max_tokens"),
            "generation_reasoning_effort": release.get(
                "generation_reasoning_effort"
            ),
            "embedding_provider": release.get("embedding_provider"),
            "embedding_model": release.get("embedding_model"),
            "embedding_dimension": release.get("embedding_dimension"),
            "vector_store_provider_requested": release.get("vector_store_provider"),
            "vector_store_provider_active": release.get("vector_store_provider"),
            "vector_store_collection": release.get("vector_store_collection"),
            "vector_store_fallback_enabled": release.get("fallback_enabled"),
            "retrieval_partial_threshold": release.get(
                "retrieval_partial_threshold"
            ),
            "retrieval_grounded_threshold": release.get(
                "retrieval_grounded_threshold"
            ),
            "retrieval_top_k": release.get("retrieval_top_k"),
            "retrieval_source_mode": release.get("retrieval_source_mode"),
            "corpus_fingerprint": release.get("corpus_fingerprint"),
            "corpus_manifest_version": release.get("corpus_manifest_version"),
            "scope_registry_version": release.get("scope_registry_version"),
            "scope_registry_fingerprint": release.get(
                "scope_registry_fingerprint"
            ),
            "pilot_release_id": release.get("release_id"),
            "pilot_release_version": release.get("release_version"),
            "task_manifest_version": release.get("task_manifest_version"),
        }

    @staticmethod
    def _load_json(path: Path, label: str) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail=f"{label} unavailable",
            ) from exc
        if not isinstance(payload, dict):
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail=f"{label} must be a JSON object",
            )
        return payload


def build_frozen_release_artifacts(
    *,
    condition_manifest: dict[str, Any],
    release_manifest: dict[str, Any],
    approval_record: dict[str, Any],
) -> FrozenPilotReleaseArtifacts:
    reviewer = str(approval_record.get("reviewer") or "").strip()
    reviewed_at = str(approval_record.get("reviewed_at") or "").strip()
    reviewer_notes = str(approval_record.get("reviewer_notes") or "").strip()
    release_id = str(approval_record.get("release_id") or "").strip()
    release_version = str(approval_record.get("release_version") or "").strip()

    if approval_record.get("human_review_confirmed") is not True:
        _approval_error("system configuration review confirmation is required")
    if not reviewer:
        _approval_error("reviewer is required")
    if not reviewer_notes:
        _approval_error("reviewer notes are required")
    if not _is_iso_datetime(reviewed_at):
        _approval_error("reviewed_at must be an ISO 8601 date-time")
    if not release_id or "draft" in release_id.casefold():
        _approval_error("release_id must identify a non-draft release")
    if not re.fullmatch(r"\d+\.\d+\.\d+", release_version):
        _approval_error("release_version must use MAJOR.MINOR.PATCH")

    release = deepcopy(release_manifest)
    missing_fields = sorted(
        field for field in FROZEN_SYSTEM_FIELDS if field not in release
    )
    if missing_fields:
        _approval_error(
            f"release is missing system configuration fields: {', '.join(missing_fields)}"
        )
    if not _is_versioned_model(str(release.get("ai_model") or "")):
        _approval_error("ai_model must pin a dated model snapshot")
    if not is_pinned_app_revision(str(release.get("app_revision") or "")):
        _approval_error("app_revision must be the exact Git commit SHA")
    release.update(
        {
            "release_id": release_id,
            "release_version": release_version,
            "release_status": "frozen",
            "release_created_at": reviewed_at,
            "condition_manifest_checksum": manifest_checksum(condition_manifest),
            "reviewed_by": reviewer,
            "reviewed_at": reviewed_at,
            "reviewer_notes": reviewer_notes,
        }
    )
    release["manifest_checksum"] = manifest_checksum(release)

    pointer = {
        "schema_version": "1.0",
        "active_release_id": release_id,
        "active_release_version": release_version,
        "updated_at": reviewed_at,
        "updated_by": reviewer,
    }
    return FrozenPilotReleaseArtifacts(release, pointer)


def _approval_error(detail: str) -> None:
    raise ApplicationError("configuration_error", researcher_safe_detail=detail)


def _is_iso_datetime(value: str) -> bool:
    if not value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _is_versioned_model(value: str) -> bool:
    return bool(re.search(r"-\d{4}-\d{2}-\d{2}$", value))


def is_pinned_app_revision(value: str) -> bool:
    return bool(re.fullmatch(r"[0-9a-fA-F]{7,40}", value.strip()))
