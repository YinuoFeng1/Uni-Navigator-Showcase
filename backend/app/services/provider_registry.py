from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from app.core.errors import ApplicationError
from app.services.ai_provider import get_ai_provider
from app.services.embedding_service import get_embedding_provider
from app.services.vector_store import get_vector_store


@dataclass(frozen=True)
class ProviderInfo:
    ai_provider_requested: str
    ai_provider_active: str
    embedding_provider_requested: str
    embedding_provider_active: str
    vector_provider_requested: str
    vector_provider_active: str
    vector_fallback_used: bool


class ProviderRegistry:
    """Constructs provider adapters once and exposes requested/active identity."""

    def __init__(
        self,
        settings: Any,
        *,
        ai_provider: Any | None = None,
        embedding_provider: Any | None = None,
        vector_store: Any | None = None,
        ai_factory: Callable[[Any], Any] = get_ai_provider,
        embedding_factory: Callable[[Any], Any] = get_embedding_provider,
        vector_factory: Callable[[Any], Any] = get_vector_store,
    ) -> None:
        self.settings = settings
        self._validate_requested_names()
        self.ai_provider = ai_provider or ai_factory(settings)
        self.embedding_provider = embedding_provider or embedding_factory(settings)
        self.vector_store = vector_store or vector_factory(settings)
        self.vector_status = self.vector_store.status()
        self._validate_participant_providers()

    @property
    def info(self) -> ProviderInfo:
        return ProviderInfo(
            ai_provider_requested=self.settings.ai_provider,
            ai_provider_active=str(
                getattr(self.ai_provider, "provider_name", "unknown")
            ),
            embedding_provider_requested=self.settings.embedding_provider,
            embedding_provider_active=str(
                getattr(self.embedding_provider, "provider_name", "unknown")
            ),
            vector_provider_requested=self.settings.vector_store_provider,
            vector_provider_active=self.vector_status.active_provider,
            vector_fallback_used=bool(self.vector_status.fallback_used),
        )

    def replace_for_test(
        self,
        *,
        ai_provider: Any | None = None,
        embedding_provider: Any | None = None,
        vector_store: Any | None = None,
    ) -> "ProviderRegistry":
        return ProviderRegistry(
            self.settings,
            ai_provider=ai_provider or self.ai_provider,
            embedding_provider=embedding_provider or self.embedding_provider,
            vector_store=vector_store or self.vector_store,
        )

    def _validate_requested_names(self) -> None:
        if self.settings.ai_provider != "openai":
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail="unsupported AI provider",
            )
        if self.settings.embedding_provider not in {"mock", "openai"}:
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail="unsupported embedding provider",
            )
        if self.settings.vector_store_provider not in {
            "auto",
            "chroma",
            "local_json",
        }:
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail="unsupported vector provider",
            )

    def _validate_participant_providers(self) -> None:
        if getattr(self.ai_provider, "provider_name", None) != "openai":
            raise ApplicationError(
                "provider_unavailable",
                researcher_safe_detail="chat requires the OpenAI answer provider",
            )
        participant_context = (
            getattr(self.settings, "execution_context", "development")
            == "participant_study"
        )
        if participant_context and self.vector_status.fallback_used:
            raise ApplicationError(
                "vector_store_unavailable",
                researcher_safe_detail="vector fallback activated in participant context",
            )
