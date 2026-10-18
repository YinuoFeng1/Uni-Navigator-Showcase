from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import hashlib
import json
import os
from typing import Any, Mapping


VALID_STUDY_MODES = {"development", "pilot"}
VALID_EXECUTION_CONTEXTS = {
    "development",
    "participant_study",
    "technical_evaluation",
}
VALID_ANSWER_MODES = {"live_llm"}
VALID_AI_PROVIDERS = {"openai"}
VALID_EMBEDDING_PROVIDERS = {"mock", "openai"}
VALID_VECTOR_PROVIDERS = {"auto", "chroma", "local_json"}
VALID_REASONING_EFFORTS = {"none", "low", "medium", "high", "xhigh"}


class RuntimeConfigError(ValueError):
    pass


@dataclass(frozen=True)
class RuntimeConfigSnapshot:
    study_mode: str
    execution_context: str
    answer_mode: str
    app_revision: str
    ai_provider: str
    ai_model: str
    prompt_template_version: str
    generation_temperature: float
    generation_max_tokens: int | None
    generation_reasoning_effort: str
    embedding_provider: str
    embedding_model: str
    embedding_dimension: int | None
    vector_store_provider_requested: str
    vector_store_provider_active: str
    vector_store_collection: str
    vector_store_fallback_enabled: bool
    retrieval_partial_threshold: float
    retrieval_grounded_threshold: float
    retrieval_top_k: int
    retrieval_source_mode: str
    corpus_fingerprint: str | None
    corpus_manifest_version: str | None
    scope_registry_version: str | None
    scope_registry_fingerprint: str | None
    pilot_release_id: str | None
    pilot_release_version: str | None
    condition_id: str | None
    condition_version: str | None
    task_manifest_version: str | None

    def canonical_dict(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def runtime_config_fingerprint(self) -> str:
        encoded = json.dumps(
            self.canonical_dict(),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return f"sha256:{hashlib.sha256(encoded).hexdigest()}"


_ENV_KEYS = {
    "study_mode": "STUDY_MODE",
    "execution_context": "EXECUTION_CONTEXT",
    "app_revision": "APP_REVISION",
    "ai_provider": "AI_PROVIDER",
    "ai_model": "AI_MODEL",
    "prompt_template_version": "PROMPT_TEMPLATE_VERSION",
    "generation_temperature": "GENERATION_TEMPERATURE",
    "generation_max_tokens": "GENERATION_MAX_TOKENS",
    "generation_reasoning_effort": "GENERATION_REASONING_EFFORT",
    "embedding_provider": "EMBEDDING_PROVIDER",
    "embedding_model": "EMBEDDING_MODEL",
    "vector_store_provider_requested": "VECTOR_STORE_PROVIDER",
    "vector_store_collection": "VECTOR_STORE_COLLECTION",
    "vector_store_fallback_enabled": "VECTOR_STORE_ALLOW_FALLBACK",
    "retrieval_partial_threshold": "RETRIEVAL_PARTIAL_SCORE_THRESHOLD",
    "retrieval_grounded_threshold": "RETRIEVAL_GROUNDED_SCORE_THRESHOLD",
    "retrieval_top_k": "RETRIEVAL_TOP_K",
    "retrieval_source_mode": "RETRIEVAL_SOURCE_MODE",
    "task_manifest_version": "TASK_MANIFEST_VERSION",
}

_SETTINGS_ATTRS = {
    "vector_store_provider_requested": "vector_store_provider",
    "vector_store_collection": "vector_collection_name",
    "vector_store_fallback_enabled": "vector_store_allow_fallback",
    "retrieval_partial_threshold": "retrieval_partial_score_threshold",
    "retrieval_grounded_threshold": "retrieval_grounded_score_threshold",
}

_SAFE_DEFAULTS: dict[str, Any] = {
    "study_mode": "development",
    "execution_context": "development",
    "answer_mode": "live_llm",
    "app_revision": "unknown",
    "ai_provider": "openai",
    "ai_model": "gpt-5.4-mini-2026-03-17",
    "prompt_template_version": "grounded-v9",
    "generation_temperature": 0.0,
    "generation_max_tokens": 400,
    "generation_reasoning_effort": "none",
    "embedding_provider": "mock",
    "embedding_model": "mock-embedding",
    "embedding_dimension": None,
    "vector_store_provider_requested": "local_json",
    "vector_store_provider_active": "local_json",
    "vector_store_collection": "uni_navigator_policy_chunks",
    "vector_store_fallback_enabled": True,
    "retrieval_partial_threshold": 0.15,
    "retrieval_grounded_threshold": 0.35,
    "retrieval_top_k": 5,
    "retrieval_source_mode": "official",
    "corpus_fingerprint": None,
    "corpus_manifest_version": None,
    "scope_registry_version": None,
    "scope_registry_fingerprint": None,
    "pilot_release_id": None,
    "pilot_release_version": None,
    "condition_id": None,
    "condition_version": None,
    "task_manifest_version": None,
}


def build_runtime_config_snapshot(
    settings: Any,
    *,
    overrides: Mapping[str, Any] | None = None,
    environment: Mapping[str, str] | None = None,
    local_config: Mapping[str, Any] | None = None,
    vector_status: Any | None = None,
    release_context: Mapping[str, Any] | None = None,
) -> RuntimeConfigSnapshot:
    """Build a non-secret snapshot with override > env > local > Settings/default."""

    overrides = dict(overrides or {})
    environment = os.environ if environment is None else environment
    local_config = dict(local_config or {})
    release_context = dict(release_context or {})
    values: dict[str, Any] = {}

    for config_field in fields(RuntimeConfigSnapshot):
        name = config_field.name
        if name in overrides:
            value = overrides[name]
        elif name in release_context:
            value = release_context[name]
        elif _ENV_KEYS.get(name) in environment:
            value = environment[_ENV_KEYS[name]]
        elif name in local_config:
            value = local_config[name]
        else:
            attr = _SETTINGS_ATTRS.get(name, name)
            value = getattr(settings, attr, _SAFE_DEFAULTS[name])
        values[name] = _coerce(name, value)

    if vector_status is not None:
        if "vector_store_provider_active" not in overrides:
            values["vector_store_provider_active"] = str(
                getattr(vector_status, "active_provider", "") or ""
            ).lower()
        if "embedding_dimension" not in overrides:
            values["embedding_dimension"] = getattr(
                vector_status, "embedding_dimension", None
            )

    snapshot = RuntimeConfigSnapshot(**values)
    validate_runtime_config(snapshot)
    return snapshot


def validate_runtime_config(snapshot: RuntimeConfigSnapshot) -> None:
    _require_choice("study_mode", snapshot.study_mode, VALID_STUDY_MODES)
    _require_choice(
        "execution_context", snapshot.execution_context, VALID_EXECUTION_CONTEXTS
    )
    _require_choice("answer_mode", snapshot.answer_mode, VALID_ANSWER_MODES)
    _require_choice("ai_provider", snapshot.ai_provider, VALID_AI_PROVIDERS)
    _require_choice(
        "generation_reasoning_effort",
        snapshot.generation_reasoning_effort,
        VALID_REASONING_EFFORTS,
    )
    _require_choice(
        "embedding_provider",
        snapshot.embedding_provider,
        VALID_EMBEDDING_PROVIDERS,
    )
    _require_choice(
        "vector_store_provider_requested",
        snapshot.vector_store_provider_requested,
        VALID_VECTOR_PROVIDERS,
    )
    if snapshot.vector_store_provider_active not in {"chroma", "local_json"}:
        raise RuntimeConfigError(
            "vector_store_provider_active must be chroma or local_json"
        )
    if not snapshot.vector_store_collection.strip():
        raise RuntimeConfigError("vector_store_collection must not be empty")
    if snapshot.retrieval_top_k < 1:
        raise RuntimeConfigError("retrieval_top_k must be positive")
    if not (
        0 <= snapshot.retrieval_partial_threshold
        < snapshot.retrieval_grounded_threshold
        <= 1
    ):
        raise RuntimeConfigError("retrieval thresholds are invalid")

    if snapshot.retrieval_source_mode != "official":
        raise RuntimeConfigError("retrieval_source_mode must be official")

    if snapshot.execution_context == "participant_study":
        if snapshot.study_mode != "pilot":
            raise RuntimeConfigError(
                "participant_study requires study_mode=pilot"
            )
        if snapshot.vector_store_fallback_enabled:
            raise RuntimeConfigError(
                "vector-store fallback is prohibited in participant study"
            )
        if not snapshot.pilot_release_id or not snapshot.pilot_release_version:
            raise RuntimeConfigError(
                "participant_study requires an explicit pilot release ID and version"
            )


def _coerce(name: str, value: Any) -> Any:
    if name in {
        "vector_store_fallback_enabled",
    }:
        if isinstance(value, str):
            return value.lower() in {"1", "true", "yes"}
        return bool(value)
    if name in {
        "generation_temperature",
        "retrieval_partial_threshold",
        "retrieval_grounded_threshold",
    }:
        return float(value)
    if name in {"generation_max_tokens", "embedding_dimension", "retrieval_top_k"}:
        if value is None or value == "":
            return None if name != "retrieval_top_k" else 5
        return int(value)
    if value is None:
        return None
    if isinstance(value, str):
        if name in {
            "study_mode",
            "execution_context",
            "answer_mode",
            "ai_provider",
            "embedding_provider",
            "vector_store_provider_requested",
            "vector_store_provider_active",
            "retrieval_source_mode",
            "generation_reasoning_effort",
        }:
            return value.strip().lower()
        return value.strip()
    return value


def _require_choice(name: str, value: str, choices: set[str]) -> None:
    if value not in choices:
        expected = ", ".join(sorted(choices))
        raise RuntimeConfigError(f"{name}={value!r} is invalid; expected {expected}")
