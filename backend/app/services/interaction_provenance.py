from __future__ import annotations

import hashlib
import json
from typing import Any

from app.services.corpus_manifest import load_ingestion_manifest
from app.services.corpus_scope_service import load_scope_registry
from app.services.study_tasks import get_study_task


def corpus_manifest_fingerprint(settings: Any) -> str | None:
    manifest = load_ingestion_manifest(
        settings.vector_store_path, settings.vector_collection_name
    )
    if not manifest.get("sources"):
        return None
    frozen_payload = {
        "collection_name": manifest.get("collection_name"),
        "embedding_provider": manifest.get("embedding_provider"),
        "embedding_model": manifest.get("embedding_model"),
        "embedding_dimension": manifest.get("embedding_dimension"),
        "source_count": manifest.get("source_count"),
        "chunk_count": manifest.get("chunk_count"),
        "sources": manifest.get("sources"),
    }
    serialized = json.dumps(
        frozen_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def scope_registry_fingerprint(path: Any) -> str:
    registry = load_scope_registry(path)
    serialized = json.dumps(
        registry,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    )
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()}"


def task_version(task_id: str | None) -> str | None:
    if not task_id:
        return None
    try:
        task = get_study_task(task_id)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    if not task:
        return None
    explicit_version = task.get("version")
    if explicit_version:
        return str(explicit_version)
    serialized = json.dumps(task, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(serialized.encode('utf-8')).hexdigest()[:16]}"


def build_interaction_provenance(
    *,
    settings: Any,
    task_id: str | None,
    scope_decision: Any | None,
    escalation_decision: Any | None,
    provider_name: str,
    provider_model: str,
    vector_status: Any | None = None,
    runtime_snapshot: Any | None = None,
    strategy_version: str | None = None,
    strategy_provenance: dict[str, Any] | None = None,
    retrieval_trace: list[dict[str, Any]] | None = None,
    server_context: Any | None = None,
) -> dict[str, Any]:
    status = vector_status
    if status is None:
        try:
            from app.services.vector_store import get_vector_store

            status = get_vector_store(settings).status()
        except Exception:
            status = None
    strategy_provenance = dict(strategy_provenance or {})
    token_usage = strategy_provenance.get("token_usage")
    if not isinstance(token_usage, dict):
        token_usage = {}
    runtime_config = (
        runtime_snapshot.canonical_dict()
        if runtime_snapshot is not None
        and hasattr(runtime_snapshot, "canonical_dict")
        else {}
    )
    return {
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "embedding_dimension": getattr(status, "embedding_dimension", None),
        "vector_collection": settings.vector_collection_name,
        "retrieval_partial_threshold": settings.retrieval_partial_score_threshold,
        "retrieval_grounded_threshold": settings.retrieval_grounded_score_threshold,
        "retrieval_top_k": settings.retrieval_top_k,
        "retrieval_mode": getattr(
            runtime_snapshot, "retrieval_source_mode", "official"
        ),
        "scope_decision": getattr(scope_decision, "decision", None),
        "scope_registry_version": getattr(
            scope_decision, "registry_version", None
        ),
        "scope_registry_fingerprint": scope_registry_fingerprint(
            settings.scope_registry_path
        ),
        "scope_matched_topics": getattr(scope_decision, "matched_topics", []),
        "escalation_recommended": getattr(
            escalation_decision, "recommended", False
        ),
        "escalation_category": getattr(escalation_decision, "category", "none"),
        "escalation_reasons": list(
            getattr(escalation_decision, "reasons", []) or []
        ),
        "corpus_manifest_fingerprint": corpus_manifest_fingerprint(settings),
        "ai_provider": provider_name or settings.ai_provider,
        "ai_model": provider_model or settings.ai_model,
        "ai_model_requested": strategy_provenance.get("model_requested")
        or settings.ai_model,
        "provider_response_model": strategy_provenance.get("model_active"),
        "provider_response_id": strategy_provenance.get("provider_response_id"),
        "provider_response_ids": strategy_provenance.get("provider_response_ids")
        or [],
        "citation_validation_retry_count": strategy_provenance.get(
            "citation_validation_retry_count", 0
        ),
        "generation_attempts": strategy_provenance.get("generation_attempts")
        or [],
        "input_tokens": _usage_int(token_usage, "input_tokens"),
        "output_tokens": _usage_int(token_usage, "output_tokens"),
        "total_tokens": _usage_int(token_usage, "total_tokens"),
        "token_usage": token_usage,
        "answer_mode": getattr(runtime_snapshot, "answer_mode", settings.answer_mode),
        "task_version": task_version(task_id),
        "app_version": getattr(settings, "app_version", settings.app_revision),
        "app_revision": settings.app_revision,
        "execution_context": getattr(
            runtime_snapshot, "execution_context", "development"
        ),
        "answer_strategy_version": strategy_version,
        "release_id": getattr(server_context, "release_id", None)
        or getattr(runtime_snapshot, "pilot_release_id", None),
        "release_version": getattr(server_context, "release_version", None)
        or getattr(runtime_snapshot, "pilot_release_version", None),
        "condition_id": getattr(server_context, "condition_id", None)
        or getattr(runtime_snapshot, "condition_id", None),
        "condition_version": getattr(server_context, "condition_version", None)
        or getattr(runtime_snapshot, "condition_version", None),
        "task_manifest_version": getattr(
            runtime_snapshot, "task_manifest_version", None
        ),
        "runtime_config_fingerprint": getattr(
            runtime_snapshot, "runtime_config_fingerprint", None
        ),
        "runtime_config": runtime_config,
        "prompt_template_version": getattr(
            runtime_snapshot, "prompt_template_version", None
        ),
        "generation_temperature": getattr(
            runtime_snapshot, "generation_temperature", None
        ),
        "generation_max_tokens": getattr(
            runtime_snapshot, "generation_max_tokens", None
        ),
        "technical_run_id": strategy_provenance.get("technical_run_id"),
        "retrieval_trace": list(retrieval_trace or []),
    }


def _usage_int(usage: dict[str, Any], key: str) -> int | None:
    value = usage.get(key)
    if isinstance(value, bool):
        return None
    return int(value) if isinstance(value, int | float) else None
