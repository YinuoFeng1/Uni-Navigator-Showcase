from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from typing import Any

from app.application.chat_orchestrator import ChatOrchestrator
from app.config import get_settings
from app.core.runtime_config import (
    RuntimeConfigSnapshot,
    build_runtime_config_snapshot,
)
from app.services.answer_strategies import LiveLlmAnswerStrategy
from app.services.corpus_scope_service import load_scope_registry
from app.services.event_repository import EventRepository
from app.services.experimental_condition_service import ExperimentalConditionService
from app.services.interaction_provenance import (
    corpus_manifest_fingerprint,
    scope_registry_fingerprint,
)
from app.services.pilot_release_service import PilotReleaseService
from app.services.provider_registry import ProviderRegistry


@dataclass(frozen=True)
class ApplicationContainer:
    settings: Any
    runtime: RuntimeConfigSnapshot
    providers: ProviderRegistry
    conditions: ExperimentalConditionService
    releases: PilotReleaseService
    events: EventRepository
    chat_orchestrator: ChatOrchestrator


def build_application_container(settings: Any | None = None) -> ApplicationContainer:
    settings = settings or get_settings()
    providers = ProviderRegistry(settings)
    conditions = ExperimentalConditionService(settings.condition_manifest_path)
    releases = PilotReleaseService(
        settings.pilot_release_manifest_path,
        settings.active_pilot_release_path,
    )
    participant = (
        settings.study_mode == "pilot"
        and settings.execution_context == "participant_study"
    )
    release_context: dict[str, Any] = {}
    if participant:
        release = releases.load_manifest()
        if release.get("release_status") == "frozen":
            release = releases.resolve_active_release(require_frozen=True)
            releases.validate_runtime_binding(
                release=release,
                settings=settings,
                vector_status=providers.vector_status,
            )
        release_context = releases.runtime_context(release)
    else:
        release_context = {
            "corpus_fingerprint": corpus_manifest_fingerprint(settings),
            "scope_registry_version": load_scope_registry(
                settings.scope_registry_path
            ).get("registry_version"),
            "scope_registry_fingerprint": scope_registry_fingerprint(
                settings.scope_registry_path
            ),
        }
        try:
            manifest = json.loads(
                (
                    settings.vector_store_path
                    / f"ingestion_manifest.{settings.vector_collection_name}.json"
                ).read_text(encoding="utf-8")
            )
            release_context["corpus_manifest_version"] = manifest.get(
                "latest_ingestion_at"
            )
        except (OSError, json.JSONDecodeError):
            pass
    runtime = build_runtime_config_snapshot(
        settings,
        environment={},
        vector_status=providers.vector_status,
        release_context=release_context,
    )
    orchestrator = ChatOrchestrator(
        settings=settings,
        runtime=runtime,
        answer_strategy=LiveLlmAnswerStrategy(providers.ai_provider),
        embedding_provider=providers.embedding_provider,
        vector_store=providers.vector_store,
    )
    return ApplicationContainer(
        settings=settings,
        runtime=runtime,
        providers=providers,
        conditions=conditions,
        releases=releases,
        events=EventRepository(),
        chat_orchestrator=orchestrator,
    )


@lru_cache
def get_application_container() -> ApplicationContainer:
    return build_application_container()
