import hashlib
import logging
import math
import re
import time
from dataclasses import dataclass
from typing import Any, Callable

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)
RETRYABLE_STATUS_CODES = {408, 409, 429, 500, 502, 503, 504}


class EmbeddingError(RuntimeError):
    pass


class EmbeddingConfigurationError(EmbeddingError):
    pass


class EmbeddingInputError(EmbeddingError):
    pass


class EmbeddingProviderError(EmbeddingError):
    pass


@dataclass(frozen=True)
class EmbeddingServiceInfo:
    provider_name: str
    model_name: str
    dimension: int


class BaseEmbeddingProvider:
    provider_name = "mock"

    def __init__(self, model_name: str, timeout_seconds: float) -> None:
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError

    def info(self) -> EmbeddingServiceInfo:
        vectors = self.embed_texts(["dimension probe"])
        dimension = len(vectors[0]) if vectors else 0
        return EmbeddingServiceInfo(
            provider_name=self.provider_name,
            model_name=self.model_name,
            dimension=dimension,
        )


class MockEmbeddingProvider(BaseEmbeddingProvider):
    provider_name = "mock"

    def __init__(
        self,
        model_name: str = "mock-embedding",
        timeout_seconds: float = 30.0,
        dimension: int = 64,
    ) -> None:
        super().__init__(model_name=model_name, timeout_seconds=timeout_seconds)
        self.dimension = dimension

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        validated = _validate_texts(texts)
        return [_mock_embedding(text, self.dimension) for text in validated]

    def info(self) -> EmbeddingServiceInfo:
        return EmbeddingServiceInfo(
            provider_name=self.provider_name,
            model_name=self.model_name,
            dimension=self.dimension,
        )


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    provider_name = "openai"

    def __init__(
        self,
        model_name: str,
        timeout_seconds: float,
        api_key: str,
        batch_size: int = 32,
        batch_delay_seconds: float = 0.0,
        max_retries: int = 3,
        retry_base_seconds: float = 1.0,
        transport: httpx.BaseTransport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(model_name=model_name, timeout_seconds=timeout_seconds)
        if not api_key.strip():
            raise EmbeddingConfigurationError(
                "EMBEDDING_PROVIDER=openai requires OPENAI_API_KEY"
            )
        if batch_size < 1:
            raise EmbeddingConfigurationError("EMBEDDING_BATCH_SIZE must be positive")
        if max_retries < 0:
            raise EmbeddingConfigurationError(
                "EMBEDDING_MAX_RETRIES must not be negative"
            )
        self.api_key = api_key
        self.batch_size = batch_size
        self.batch_delay_seconds = max(0.0, batch_delay_seconds)
        self.max_retries = max_retries
        self.retry_base_seconds = max(0.0, retry_base_seconds)
        self.transport = transport
        self.sleeper = sleeper
        self.dimension = 0

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        validated = _validate_texts(texts)
        if not validated:
            return []

        all_embeddings: list[list[float]] = []
        expected_dimension: int | None = None
        with httpx.Client(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            for start in range(0, len(validated), self.batch_size):
                batch = validated[start : start + self.batch_size]
                response = self._request_batch(client, batch)
                embeddings = _parse_embeddings_response(response, len(batch))
                batch_dimensions = {len(embedding) for embedding in embeddings}
                if len(batch_dimensions) != 1:
                    raise EmbeddingProviderError(
                        "OpenAI embeddings response contained inconsistent dimensions"
                    )
                batch_dimension = next(iter(batch_dimensions))
                if expected_dimension is None:
                    expected_dimension = batch_dimension
                elif batch_dimension != expected_dimension:
                    raise EmbeddingProviderError(
                        "OpenAI embedding dimensions changed between batches"
                    )
                all_embeddings.extend(embeddings)
                if (
                    self.batch_delay_seconds > 0
                    and start + self.batch_size < len(validated)
                ):
                    self.sleeper(self.batch_delay_seconds)

        if len(all_embeddings) != len(validated):
            raise EmbeddingProviderError(
                "OpenAI embeddings response length did not match the request"
            )
        self.dimension = expected_dimension or 0
        return all_embeddings

    def info(self) -> EmbeddingServiceInfo:
        return EmbeddingServiceInfo(
            provider_name=self.provider_name,
            model_name=self.model_name,
            dimension=self.dimension,
        )

    def _request_batch(
        self,
        client: httpx.Client,
        batch: list[str],
    ) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = client.post(
                    "https://api.openai.com/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model_name,
                        "input": batch,
                        "encoding_format": "float",
                    },
                )
                if response.status_code not in RETRYABLE_STATUS_CODES:
                    response.raise_for_status()
                    return response
                last_error = EmbeddingProviderError(
                    "OpenAI embeddings request failed with HTTP "
                    f"{response.status_code}{_safe_error_details(response)}"
                )
            except httpx.HTTPStatusError as exc:
                raise EmbeddingProviderError(
                    "OpenAI embeddings request failed with HTTP "
                    f"{exc.response.status_code}{_safe_error_details(exc.response)}"
                ) from exc
            except httpx.RequestError as exc:
                last_error = exc

            if attempt < self.max_retries:
                delay = min(
                    self.retry_base_seconds * (2**attempt),
                    8.0,
                )
                self.sleeper(delay)

        if isinstance(last_error, httpx.RequestError):
            raise EmbeddingProviderError(
                "OpenAI embeddings request failed due to a network error"
            ) from last_error
        if isinstance(last_error, EmbeddingProviderError):
            raise last_error
        raise EmbeddingProviderError("OpenAI embeddings request failed")


def get_embedding_provider(settings: Settings | None = None) -> BaseEmbeddingProvider:
    settings = settings or get_settings()
    provider = settings.embedding_provider

    if provider == "openai":
        return OpenAIEmbeddingProvider(
            model_name=settings.embedding_model,
            timeout_seconds=settings.embedding_timeout_seconds,
            api_key=settings.openai_api_key,
            batch_size=settings.embedding_batch_size,
            batch_delay_seconds=settings.embedding_batch_delay_seconds,
            max_retries=settings.embedding_max_retries,
            retry_base_seconds=settings.embedding_retry_base_seconds,
        )
    if provider == "mock":
        return MockEmbeddingProvider(model_name=settings.embedding_model)
    raise EmbeddingConfigurationError(
        f"Unsupported EMBEDDING_PROVIDER={provider!r}; expected mock or openai"
    )


def _validate_texts(texts: Any) -> list[str]:
    if not isinstance(texts, list):
        raise EmbeddingInputError("Embedding input must be a list of strings")
    for index, text in enumerate(texts):
        if not isinstance(text, str):
            raise EmbeddingInputError(
                f"Embedding input at index {index} must be a string"
            )
        if not text.strip():
            raise EmbeddingInputError(
                f"Embedding input at index {index} must not be empty"
            )
    return texts


def _parse_embeddings_response(
    response: httpx.Response,
    expected_count: int,
) -> list[list[float]]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise EmbeddingProviderError(
            "OpenAI embeddings response was not valid JSON"
        ) from exc
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list) or len(data) != expected_count:
        raise EmbeddingProviderError(
            "OpenAI embeddings response length did not match the request"
        )

    indexed: dict[int, list[float]] = {}
    for item in data:
        if not isinstance(item, dict):
            raise EmbeddingProviderError(
                "OpenAI embeddings response contained an invalid item"
            )
        index = item.get("index")
        embedding = item.get("embedding")
        if not isinstance(index, int) or index in indexed:
            raise EmbeddingProviderError(
                "OpenAI embeddings response contained invalid indices"
            )
        if not isinstance(embedding, list) or not embedding:
            raise EmbeddingProviderError(
                "OpenAI embeddings response contained an empty vector"
            )
        if any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(float(value))
            for value in embedding
        ):
            raise EmbeddingProviderError(
                "OpenAI embeddings response contained non-numeric values"
            )
        indexed[index] = [float(value) for value in embedding]

    if set(indexed) != set(range(expected_count)):
        raise EmbeddingProviderError(
            "OpenAI embeddings response indices did not match the request"
        )
    return [indexed[index] for index in range(expected_count)]


def _safe_error_details(response: httpx.Response) -> str:
    """Return bounded provider error identifiers without exposing response text."""
    try:
        payload = response.json()
    except ValueError:
        return ""
    error = payload.get("error") if isinstance(payload, dict) else None
    if not isinstance(error, dict):
        return ""

    details: list[str] = []
    for field in ("type", "code"):
        value = error.get(field)
        if not isinstance(value, str):
            continue
        safe_value = re.sub(r"[^a-zA-Z0-9_.-]", "", value)[:80]
        if safe_value:
            details.append(f"{field}={safe_value}")
    return f" ({', '.join(details)})" if details else ""


def _mock_embedding(text: str, dimension: int) -> list[float]:
    vector = [0.0] * dimension
    tokens = re.findall(r"[a-zA-Z0-9]+", text.lower())

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimension
        vector[index] += 1.0

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [round(value / norm, 8) for value in vector]
