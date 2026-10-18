import json

import httpx
import pytest

from app.services.embedding_service import (
    EmbeddingConfigurationError,
    EmbeddingInputError,
    EmbeddingProviderError,
    OpenAIEmbeddingProvider,
)


def _provider(
    handler,
    *,
    batch_size: int = 2,
    batch_delay_seconds: float = 0.0,
    max_retries: int = 0,
    sleeper=lambda _: None,
) -> OpenAIEmbeddingProvider:
    return OpenAIEmbeddingProvider(
        model_name="text-embedding-3-small",
        timeout_seconds=5,
        api_key="test-key-not-real",
        batch_size=batch_size,
        batch_delay_seconds=batch_delay_seconds,
        max_retries=max_retries,
        retry_base_seconds=0.1,
        transport=httpx.MockTransport(handler),
        sleeper=sleeper,
    )


def _embedding_response(request: httpx.Request, dimension: int = 3) -> httpx.Response:
    payload = json.loads(request.content)
    return httpx.Response(
        200,
        json={
            "data": [
                {
                    "index": index,
                    "embedding": [float(index + 1)] * dimension,
                }
                for index, _ in enumerate(payload["input"])
            ]
        },
    )


def test_openai_provider_batches_and_preserves_input_order() -> None:
    batch_sizes: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        batch_sizes.append(len(payload["input"]))
        assert payload["model"] == "text-embedding-3-small"
        assert payload["encoding_format"] == "float"
        return _embedding_response(request)

    provider = _provider(handler, batch_size=2)

    vectors = provider.embed_texts(["one", "two", "three"])

    assert batch_sizes == [2, 1]
    assert len(vectors) == 3
    assert all(len(vector) == 3 for vector in vectors)
    assert provider.info().dimension == 3


def test_openai_provider_can_throttle_between_batches() -> None:
    delays: list[float] = []
    provider = _provider(
        _embedding_response,
        batch_size=1,
        batch_delay_seconds=0.25,
        sleeper=delays.append,
    )

    provider.embed_texts(["one", "two", "three"])

    assert delays == [0.25, 0.25]


def test_openai_provider_requires_key_and_rejects_empty_text() -> None:
    with pytest.raises(EmbeddingConfigurationError, match="OPENAI_API_KEY"):
        OpenAIEmbeddingProvider(
            model_name="text-embedding-3-small",
            timeout_seconds=5,
            api_key="",
        )

    provider = _provider(_embedding_response)
    with pytest.raises(EmbeddingInputError, match="must not be empty"):
        provider.embed_texts(["valid", "  "])


def test_openai_provider_rejects_wrong_response_count() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]},
        )

    with pytest.raises(EmbeddingProviderError, match="length"):
        _provider(handler).embed_texts(["one", "two"])


def test_openai_provider_rejects_inconsistent_dimensions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 0, "embedding": [0.1, 0.2]},
                    {"index": 1, "embedding": [0.1, 0.2, 0.3]},
                ]
            },
        )

    with pytest.raises(EmbeddingProviderError, match="inconsistent dimensions"):
        _provider(handler).embed_texts(["one", "two"])


def test_openai_provider_retries_retryable_status_with_bounded_backoff() -> None:
    calls = 0
    delays: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"error": {"message": "rate limited"}})
        return _embedding_response(request)

    vectors = _provider(
        handler,
        max_retries=1,
        sleeper=delays.append,
    ).embed_texts(["one"])

    assert len(vectors) == 1
    assert calls == 2
    assert delays == [0.1]


def test_openai_provider_reports_safe_error_identifiers() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "error": {
                    "message": "sensitive provider message",
                    "type": "insufficient_quota",
                    "code": "billing_hard_limit",
                }
            },
        )

    with pytest.raises(
        EmbeddingProviderError,
        match=(
            r"HTTP 429 \(type=insufficient_quota, "
            r"code=billing_hard_limit\)"
        ),
    ) as exc_info:
        _provider(handler).embed_texts(["one"])

    assert "sensitive provider message" not in str(exc_info.value)


def test_failed_later_batch_does_not_fall_back_to_mock() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return _embedding_response(request)
        return httpx.Response(500, json={"error": {"message": "temporary"}})

    provider = _provider(handler, batch_size=1)

    with pytest.raises(EmbeddingProviderError, match="HTTP 500"):
        provider.embed_texts(["first", "second"])
    assert provider.info().dimension == 0
