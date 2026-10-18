from pathlib import Path

import pytest

from app.config import get_settings
from app.scripts.ingest_corpus import ingest_corpus
from app.services.corpus_loader import chunk_policy_documents, load_corpus
from app.services.embedding_service import MockEmbeddingProvider
from app.services.retrieval_service import retrieve_policy_chunks
from app.services.vector_store import ChromaVectorStore, LocalJsonVectorStore, get_vector_store


def test_corpus_loader_loads_markdown_front_matter(tmp_path: Path) -> None:
    corpus_file = tmp_path / "withdrawal.md"
    corpus_file.write_text(
        """---
source_id: uq-withdrawal-policy
title: Withdrawal Policy
document_name: Withdrawal and Refunds
section: General
url: https://example.edu/policy
source_type: prepared_policy
updated_at: 2026-01-01
---

# Withdrawal before census date

Students should check the official policy and contact authorised staff before making important enrolment decisions.
""",
        encoding="utf-8",
    )

    documents = load_corpus(tmp_path)

    assert len(documents) == 1
    document = documents[0]
    assert document.source_id == "uq-withdrawal-policy"
    assert document.title == "Withdrawal Policy"
    assert document.document_name == "Withdrawal and Refunds"
    assert "census date" in document.text


def test_chunker_creates_stable_chunk_metadata(tmp_path: Path) -> None:
    corpus_file = tmp_path / "extension.txt"
    corpus_file.write_text(
        "# Assessment extension\n\n"
        "Students may need supporting evidence for assessment extension requests. "
        "They should check authorised university sources before relying on general guidance.\n\n"
        "Urgent or personal cases should be escalated to authorised staff.",
        encoding="utf-8",
    )
    documents = load_corpus(tmp_path)

    chunks = chunk_policy_documents(documents, target_chars=180, overlap_chars=20)

    assert chunks
    assert chunks[0].chunk_id == "extension_chunk_0000"
    assert chunks[0].source_id == "extension"
    assert chunks[0].chunk_index == 0
    assert "supporting evidence" in chunks[0].chunk_text


def test_empty_corpus_folder_does_not_crash(tmp_path: Path) -> None:
    assert load_corpus(tmp_path) == []


def test_mock_embedding_provider_is_deterministic() -> None:
    provider = MockEmbeddingProvider(dimension=16)

    first = provider.embed_texts(["assessment extension"])[0]
    second = provider.embed_texts(["assessment extension"])[0]

    assert first == second
    assert len(first) == 16


def test_local_vector_store_upserts_and_retrieves_sample_chunk(tmp_path: Path) -> None:
    corpus_file = tmp_path / "fees.md"
    corpus_file.write_text(
        "# Fees\n\nStudents should contact authorised staff for fee deadline questions.",
        encoding="utf-8",
    )
    chunks = chunk_policy_documents(load_corpus(tmp_path))
    embeddings = MockEmbeddingProvider().embed_texts([chunk.chunk_text for chunk in chunks])
    store = LocalJsonVectorStore(tmp_path / "vector_store")

    stored_count = store.upsert_chunks(chunks, embeddings)
    results = store.query(MockEmbeddingProvider().embed_texts(["fee deadline"])[0], top_k=1)

    assert stored_count == 1
    assert len(results) == 1
    assert results[0].source_id == "fees"
    assert "fee deadline" in results[0].chunk_text
    assert results[0].provider == "local_json"


def test_ingestion_works_with_local_json_provider(monkeypatch, tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus"
    vector_path = tmp_path / "vector_store"
    corpus_path.mkdir()
    (corpus_path / "fees.md").write_text(
        "# Fees\n\nStudents should contact authorised staff for fee deadline questions.",
        encoding="utf-8",
    )
    monkeypatch.setenv("CORPUS_PATH", str(corpus_path))
    monkeypatch.setenv("VECTOR_STORE_PATH", str(vector_path))
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "local_json")
    monkeypatch.setenv("VECTOR_STORE_ALLOW_FALLBACK", "true")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    get_settings.cache_clear()

    summary = ingest_corpus(rebuild=True)

    get_settings.cache_clear()
    assert summary["documents_loaded"] == 1
    assert summary["chunks_created"] == 1
    assert summary["chunks_stored"] == 1
    assert summary["vector_store_provider_requested"] == "local_json"
    assert summary["vector_store_provider_active"] == "local_json"
    assert summary["fallback_used"] is False


def test_auto_provider_falls_back_when_chroma_unavailable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    import app.services.vector_store as vector_store_module

    def raise_import_error(*args, **kwargs):
        raise ImportError("chromadb unavailable for test")

    monkeypatch.setattr(vector_store_module, "ChromaVectorStore", raise_import_error)
    monkeypatch.setattr(vector_store_module, "is_chromadb_available", lambda: False)
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "auto")
    monkeypatch.setenv("VECTOR_STORE_ALLOW_FALLBACK", "true")
    monkeypatch.setenv("VECTOR_STORE_PATH", str(tmp_path / "vector_store"))
    get_settings.cache_clear()

    store = get_vector_store()
    status = store.status()

    get_settings.cache_clear()
    assert status.vector_store_provider == "auto"
    assert status.active_provider == "local_json"
    assert status.fallback_used is True
    assert status.chroma_available is False


def test_retrieval_service_returns_chunk_metadata(monkeypatch, tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus"
    vector_path = tmp_path / "vector_store"
    corpus_path.mkdir()
    (corpus_path / "special-consideration.md").write_text(
        """---
source_id: special-consideration
title: Special Consideration
document_name: Assessment Procedures
section: Evidence
source_type: prepared_policy
---

# Evidence

Students may need supporting evidence when applying for special consideration.
""",
        encoding="utf-8",
    )
    monkeypatch.setenv("CORPUS_PATH", str(corpus_path))
    monkeypatch.setenv("VECTOR_STORE_PATH", str(vector_path))
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "local_json")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    get_settings.cache_clear()
    settings = get_settings()

    chunks = chunk_policy_documents(load_corpus(settings.corpus_path))
    embeddings = MockEmbeddingProvider().embed_texts([chunk.chunk_text for chunk in chunks])
    LocalJsonVectorStore(settings.vector_store_path).upsert_chunks(chunks, embeddings)

    results = retrieve_policy_chunks(
        "special consideration evidence", top_k=1, source_mode="prepared"
    )

    get_settings.cache_clear()
    assert len(results) == 1
    assert results[0]["chunk_id"] == "special_consideration_chunk_0000"
    assert results[0]["source_id"] == "special-consideration"
    assert "supporting evidence" in results[0]["chunk_text"]
    assert results[0]["provider"] == "local_json"


def test_chroma_vector_store_upserts_and_queries_when_installed(
    tmp_path: Path,
) -> None:
    pytest.importorskip("chromadb")
    corpus_file = tmp_path / "fees.md"
    corpus_file.write_text(
        """---
source_id: fees-source
title: Fees Policy
document_name: Fees Procedure
section: Deadlines
source_type: prepared_policy
updated_at: 2026-01-01
prototype_only: true
---

# Fee deadline

Students should contact authorised staff for fee deadline questions.
""",
        encoding="utf-8",
    )
    chunks = chunk_policy_documents(load_corpus(tmp_path))
    embeddings = MockEmbeddingProvider().embed_texts([chunk.chunk_text for chunk in chunks])
    store = ChromaVectorStore(tmp_path / "chroma", requested_provider="chroma")

    store.clear()
    stored_count = store.upsert_chunks(chunks, embeddings)
    results = store.query(MockEmbeddingProvider().embed_texts(["fee deadline"])[0], top_k=1)
    status = store.status()

    assert stored_count == 1
    assert len(results) == 1
    assert results[0].source_id == "fees-source"
    assert results[0].provider == "chroma"
    assert "fee deadline" in results[0].chunk_text.lower()
    assert status.active_provider == "chroma"
    assert status.chunk_count == 1
    assert status.source_count == 1


def test_chroma_atomic_replace_preserves_other_collection(tmp_path: Path) -> None:
    chromadb = pytest.importorskip("chromadb")
    corpus_file = tmp_path / "policy.md"
    corpus_file.write_text(
        "# Policy\n\nStudents should review official assessment requirements.",
        encoding="utf-8",
    )
    chunks = chunk_policy_documents(load_corpus(tmp_path))
    vector_path = tmp_path / "chroma"
    mock_store = ChromaVectorStore(
        vector_path,
        collection_name="uni_navigator_policy_chunks",
        requested_provider="chroma",
    )
    openai_store = ChromaVectorStore(
        vector_path,
        collection_name="uni_navigator_policy_chunks_openai",
        requested_provider="chroma",
    )

    mock_store.replace_all(
        chunks,
        [[0.1] * 64],
        {"embedding_provider": "mock", "embedding_model": "fixture"},
    )
    openai_store.replace_all(
        chunks,
        [[0.2] * 8],
        {
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
        },
    )

    client = chromadb.PersistentClient(path=str(vector_path))
    collections = {item.name for item in client.list_collections()}
    assert collections == {
        "uni_navigator_policy_chunks",
        "uni_navigator_policy_chunks_openai",
    }
    assert ChromaVectorStore(
        vector_path,
        collection_name="uni_navigator_policy_chunks",
    ).status().embedding_dimension == 64
    openai_status = ChromaVectorStore(
        vector_path,
        collection_name="uni_navigator_policy_chunks_openai",
    ).status()
    assert openai_status.embedding_dimension == 8
    assert openai_status.collection_metadata["embedding_provider"] == "openai"


def test_chroma_failed_staging_write_keeps_previous_target(
    monkeypatch,
    tmp_path: Path,
) -> None:
    pytest.importorskip("chromadb")
    corpus_file = tmp_path / "policy.md"
    corpus_file.write_text(
        "# Policy\n\nStudents should review official assessment requirements.",
        encoding="utf-8",
    )
    chunks = chunk_policy_documents(load_corpus(tmp_path))
    store = ChromaVectorStore(
        tmp_path / "chroma",
        collection_name="atomic_target",
        requested_provider="chroma",
    )
    store.replace_all(chunks, [[0.1] * 4], {"embedding_provider": "mock"})

    def fail_upsert(*args, **kwargs):
        raise RuntimeError("simulated staging failure")

    monkeypatch.setattr(store, "_upsert_collection", fail_upsert)
    with pytest.raises(RuntimeError, match="simulated staging failure"):
        store.replace_all(chunks, [[0.2] * 8], {"embedding_provider": "openai"})

    restored = ChromaVectorStore(
        tmp_path / "chroma",
        collection_name="atomic_target",
        requested_provider="chroma",
    )
    assert restored.status().chunk_count == 1
    assert restored.status().embedding_dimension == 4
    names = {item.name for item in restored.client.list_collections()}
    assert names == {"atomic_target"}


def test_admin_corpus_status_endpoint(monkeypatch, tmp_path: Path, client) -> None:
    monkeypatch.setenv("CORPUS_PATH", str(tmp_path / "corpus"))
    monkeypatch.setenv("VECTOR_STORE_PATH", str(tmp_path / "vector_store"))
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "local_json")
    get_settings.cache_clear()

    response = client.get("/api/admin/corpus/status")

    get_settings.cache_clear()
    assert response.status_code == 200
    data = response.json()
    assert data["collectionName"] == "uni_navigator_policy_chunks"
    assert data["vectorStoreProvider"] == "local_json"
    assert data["activeVectorStoreProvider"] == "local_json"
    assert data["vectorStoreProviderRequested"] == "local_json"
    assert data["vectorStoreProviderActive"] == "local_json"
    assert data["vectorStoreCollection"] == "uni_navigator_policy_chunks"
    assert data["fallbackUsed"] is False
    assert "chromaAvailable" in data
    assert data["chunkCount"] == 0
    assert data["activeCollection"] == "uni_navigator_policy_chunks"
    assert data["collectionChunkCount"] == 0
    assert data["collectionSourceCount"] == 0
    assert data["embeddingDimension"] is None
