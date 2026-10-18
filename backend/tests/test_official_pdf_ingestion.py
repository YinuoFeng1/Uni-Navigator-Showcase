import json
from pathlib import Path

import pytest
from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

from app.config import get_settings
from app.scripts.ingest_corpus import ingest_corpus
from app.services.rag_evidence_service import citations_from_chunks
from app.services.corpus_loader import (
    CorpusValidationError,
    chunk_policy_documents,
    document_checksum,
    extract_pdf,
    load_corpus,
    load_corpus_with_report,
    validate_official_metadata,
)
from app.services.embedding_service import MockEmbeddingProvider
from app.services.retrieval_service import retrieve_policy_chunks
from app.services.vector_store import ChromaVectorStore, LocalJsonVectorStore


def _write_text_pdf(path: Path, page_lines: list[list[str]]) -> None:
    writer = PdfWriter()
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    font_reference = writer._add_object(font)

    for lines in page_lines:
        page = writer.add_blank_page(width=612, height=792)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {NameObject("/F1"): font_reference}
                )
            }
        )
        commands = ["BT", "/F1 12 Tf", "72 720 Td"]
        for index, line in enumerate(lines):
            if index:
                commands.append("0 -24 Td")
            escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            commands.append(f"({escaped}) Tj")
        commands.append("ET")
        content = StreamObject()
        content.set_data("\n".join(commands).encode("latin-1"))
        page[NameObject("/Contents")] = writer._add_object(content)

    with path.open("wb") as handle:
        writer.write(handle)


def _write_blank_pdf(path: Path, encrypted: bool = False) -> None:
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    if encrypted:
        writer.encrypt("test-password")
    with path.open("wb") as handle:
        writer.write(handle)


def _official_metadata(**overrides) -> dict:
    metadata = {
        "source_id": "official-example-policy",
        "title": "Example Assessment Policy",
        "document_name": "Example Assessment Policy PDF",
        "institution": "Example University",
        "source_url": "https://example.edu/policy/assessment",
        "access_date": "2026-07-10",
        "source_type": "official_policy",
        "prototype_only": False,
        "active": True,
        "version": "1.0",
        "effective_date": "2026-01-01",
    }
    metadata.update(overrides)
    return metadata


def _write_official_fixture(
    corpus_path: Path,
    pages: list[list[str]],
    metadata: dict | None = None,
    filename: str = "assessment-policy.pdf",
) -> tuple[Path, Path]:
    official_path = corpus_path / "official" / filename
    metadata_path = corpus_path / "metadata" / Path(filename).with_suffix(".json")
    official_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    _write_text_pdf(official_path, pages)
    metadata_path.write_text(
        json.dumps(metadata or _official_metadata()),
        encoding="utf-8",
    )
    return official_path, metadata_path


def _write_prepared_fixture(corpus_path: Path) -> None:
    prepared_path = corpus_path / "prepared"
    prepared_path.mkdir(parents=True, exist_ok=True)
    (prepared_path / "prepared-example.md").write_text(
        """---
source_id: prepared-example
title: Prepared Example
document_name: Prepared Example Scenario
source_type: prepared_policy
prototype_only: true
---

# Prepared evidence

This synthetic prepared passage discusses assessment evidence for prototype testing.
""",
        encoding="utf-8",
    )


def _configure_ingestion(monkeypatch, corpus_path: Path, vector_path: Path, provider: str = "local_json") -> None:
    monkeypatch.setenv("CORPUS_PATH", str(corpus_path))
    monkeypatch.setenv("VECTOR_STORE_PATH", str(vector_path))
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", provider)
    monkeypatch.setenv("VECTOR_STORE_ALLOW_FALLBACK", "false")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("RETRIEVAL_SOURCE_MODE", "all")
    get_settings.cache_clear()


def test_text_pdf_preserves_pages_and_detects_headings(tmp_path: Path) -> None:
    pdf_path = tmp_path / "policy.pdf"
    _write_text_pdf(
        pdf_path,
        [
            ["1 Eligibility", "Students may request assessment consideration with evidence."],
            ["2 Deadlines", "Applications should follow the stated submission deadline."],
        ],
    )

    extraction = extract_pdf(pdf_path)

    assert extraction.page_count == 2
    assert extraction.ocr_required is False
    assert extraction.pages[0].page_number == 1
    assert extraction.pages[1].page_number == 2
    assert extraction.pages[0].section == "1 Eligibility"
    assert "submission deadline" in extraction.pages[1].text


def test_empty_pdf_requires_ocr_and_password_pdf_is_rejected(tmp_path: Path) -> None:
    blank_path = tmp_path / "blank.pdf"
    protected_path = tmp_path / "protected.pdf"
    _write_blank_pdf(blank_path)
    _write_blank_pdf(protected_path, encrypted=True)

    extraction = extract_pdf(blank_path)

    assert extraction.ocr_required is True
    assert extraction.empty_pages == (1,)
    assert any("OCR was not run" in warning for warning in extraction.warnings)
    with pytest.raises(ValueError, match="password-protected"):
        extract_pdf(protected_path)


def test_active_ocr_required_pdf_blocks_ingestion(monkeypatch, tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus"
    vector_path = tmp_path / "vectors"
    official_path = corpus_path / "official" / "blank.pdf"
    metadata_path = corpus_path / "metadata" / "blank.json"
    official_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    _write_blank_pdf(official_path)
    metadata_path.write_text(json.dumps(_official_metadata()), encoding="utf-8")
    _configure_ingestion(monkeypatch, corpus_path, vector_path)

    summary = ingest_corpus(source_type="official")

    get_settings.cache_clear()
    assert summary["validation_failed"] is True
    assert summary["active_pdfs_requiring_ocr"] == 1
    assert summary["chunks_stored"] == 0
    assert summary["chunk_count"] == 0


def test_official_metadata_validation_rejects_missing_source_url() -> None:
    metadata = _official_metadata()
    metadata.pop("source_url")

    with pytest.raises(CorpusValidationError, match="source_url"):
        validate_official_metadata(metadata)


def test_official_loader_requires_valid_sidecar_and_unique_source_id(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus"
    _write_official_fixture(
        corpus_path,
        [["1 Policy", "First official policy passage with enough extractable text."]],
        filename="one.pdf",
    )
    _write_official_fixture(
        corpus_path,
        [["1 Policy", "Second official policy passage with enough extractable text."]],
        filename="two.pdf",
    )

    result = load_corpus_with_report(corpus_path, source_type="official")

    assert result.documents == []
    assert result.report.metadata_files_validated == 2
    assert any("duplicate source_id" in item for item in result.report.invalid_files)


def test_pdf_chunks_have_deterministic_ids_checksum_and_page_metadata(tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus"
    pdf_path, _ = _write_official_fixture(
        corpus_path,
        [
            ["1 Eligibility", "Evidence is required for this synthetic assessment scenario."],
            ["2 Review", "A review request should follow the published process and deadline."],
        ],
    )
    documents = load_corpus(corpus_path, source_type="official")

    first = chunk_policy_documents(documents, target_tokens=20, overlap_tokens=0)
    second = chunk_policy_documents(documents, target_tokens=20, overlap_tokens=0)

    assert [item.chunk_id for item in first] == [item.chunk_id for item in second]
    assert first[0].document_checksum == document_checksum(pdf_path)
    assert first[0].page_start == 1
    assert first[-1].page_end == 2
    assert first[0].metadata()["source_type"] == "official_policy"
    assert first[0].metadata()["prototype_only"] is False


def test_repeated_ingestion_skips_unchanged_and_replaces_changed_source(monkeypatch, tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus"
    vector_path = tmp_path / "vectors"
    pdf_path, _ = _write_official_fixture(
        corpus_path,
        [["1 Evidence", "The first synthetic official passage requires supporting evidence."]],
    )
    _configure_ingestion(monkeypatch, corpus_path, vector_path)

    first = ingest_corpus(source_type="official")
    second = ingest_corpus(source_type="official")
    original_checksum = document_checksum(pdf_path)
    _write_text_pdf(
        pdf_path,
        [["1 Evidence", "The changed synthetic official passage requires different evidence and a deadline."]],
    )
    changed = ingest_corpus(source_type="official")
    metadata = LocalJsonVectorStore(vector_path).list_metadata()

    get_settings.cache_clear()
    assert first["chunks_stored"] >= 1
    assert second["unchanged_files_skipped"] == 1
    assert second["chunks_stored"] == 0
    assert changed["changed_files_replaced"] == 1
    assert changed["chunks_deleted"] >= 1
    assert {item["document_checksum"] for item in metadata} == {
        document_checksum(pdf_path)
    }
    assert document_checksum(pdf_path) != original_checksum


def test_scoped_official_chroma_rebuild_preserves_prepared_chunks(monkeypatch, tmp_path: Path) -> None:
    pytest.importorskip("chromadb")
    corpus_path = tmp_path / "corpus"
    vector_path = tmp_path / "chroma"
    _write_prepared_fixture(corpus_path)
    _write_official_fixture(
        corpus_path,
        [["1 Evidence", "Official synthetic assessment evidence for Chroma testing."]],
    )
    _configure_ingestion(monkeypatch, corpus_path, vector_path, provider="chroma")

    ingest_corpus(source_type="all", rebuild=True)
    before = ChromaVectorStore(vector_path).list_metadata()
    summary = ingest_corpus(source_type="official", rebuild=True)
    after = ChromaVectorStore(vector_path).list_metadata()

    get_settings.cache_clear()
    assert {item["source_id"] for item in before} == {
        "prepared-example",
        "official-example-policy",
    }
    assert {item["source_id"] for item in after} == {
        "prepared-example",
        "official-example-policy",
    }
    assert summary["vector_store_provider_active"] == "chroma"
    assert summary["fallback_used"] is False


def test_cross_type_source_id_conflict_fails_without_deleting_prepared(
    monkeypatch,
    tmp_path: Path,
) -> None:
    corpus_path = tmp_path / "corpus"
    vector_path = tmp_path / "vectors"
    _write_prepared_fixture(corpus_path)
    _configure_ingestion(monkeypatch, corpus_path, vector_path)
    ingest_corpus(source_type="prepared", rebuild=True)
    _write_official_fixture(
        corpus_path,
        [["1 Evidence", "Official synthetic text with a conflicting source identifier."]],
        metadata=_official_metadata(source_id="prepared-example"),
    )

    summary = ingest_corpus(source_type="official", rebuild=True)
    metadata = LocalJsonVectorStore(vector_path).list_metadata()

    get_settings.cache_clear()
    assert summary["validation_failed"] is True
    assert summary["chunks_deleted"] == 0
    assert summary["chunks_stored"] == 0
    assert {item["source_id"] for item in metadata} == {"prepared-example"}
    assert {item["source_type"] for item in metadata} == {"prepared_policy"}


def test_inactive_official_source_is_removed_and_excluded(monkeypatch, tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus"
    vector_path = tmp_path / "vectors"
    _, metadata_path = _write_official_fixture(
        corpus_path,
        [["1 Evidence", "Active official synthetic evidence passage for testing."]],
    )
    _configure_ingestion(monkeypatch, corpus_path, vector_path)
    ingest_corpus(source_type="official")
    metadata_path.write_text(
        json.dumps(_official_metadata(active=False)),
        encoding="utf-8",
    )

    summary = ingest_corpus(source_type="official")
    results = retrieve_policy_chunks(
        "official synthetic evidence",
        source_mode="official",
    )

    get_settings.cache_clear()
    assert summary["chunks_deleted"] >= 1
    assert summary["chunk_count"] == 0
    assert results == []


def test_prepared_official_filtering_and_citation_page_fields(monkeypatch, tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus"
    vector_path = tmp_path / "vectors"
    _write_prepared_fixture(corpus_path)
    _write_official_fixture(
        corpus_path,
        [["1 Evidence", "Official synthetic assessment evidence and policy deadline details."]],
    )
    _configure_ingestion(monkeypatch, corpus_path, vector_path)
    ingest_corpus(source_type="all", rebuild=True)

    official_results = retrieve_policy_chunks(
        "assessment evidence deadline",
        source_mode="official",
    )
    prepared_results = retrieve_policy_chunks(
        "assessment evidence",
        source_mode="prepared",
    )
    citations = citations_from_chunks(official_results)
    preferred_results = retrieve_policy_chunks(
        "assessment evidence",
        top_k=1,
        source_mode="prefer_official",
    )

    get_settings.cache_clear()
    assert official_results
    assert {item["source_type"] for item in official_results} == {
        "official_policy"
    }
    assert prepared_results
    assert {item["source_type"] for item in prepared_results} == {
        "prepared_policy"
    }
    assert citations[0].pageStart == 1
    assert citations[0].pageEnd == 1
    assert citations[0].sourceType == "official_policy"
    assert citations[0].sourceUrl == "https://example.edu/policy/assessment"
    assert preferred_results[0]["source_type"] == "official_policy"


def test_validate_only_does_not_modify_vector_store(monkeypatch, tmp_path: Path) -> None:
    corpus_path = tmp_path / "corpus"
    vector_path = tmp_path / "vectors"
    _write_official_fixture(
        corpus_path,
        [["1 Evidence", "Official synthetic text for validation-only testing."]],
    )
    _configure_ingestion(monkeypatch, corpus_path, vector_path)

    summary = ingest_corpus(source_type="official", validate_only=True)

    get_settings.cache_clear()
    assert summary["metadata_files_validated"] == 1
    assert summary["pdfs_extracted"] == 1
    assert summary["chunks_stored"] == 0
    assert summary["chunk_count"] == 0


def test_admin_corpus_status_reports_source_breakdown(
    monkeypatch,
    tmp_path: Path,
    client,
) -> None:
    corpus_path = tmp_path / "corpus"
    vector_path = tmp_path / "vectors"
    _write_prepared_fixture(corpus_path)
    _write_official_fixture(
        corpus_path,
        [["1 Evidence", "Official synthetic assessment evidence for status testing."]],
    )
    _configure_ingestion(monkeypatch, corpus_path, vector_path)
    ingest_corpus(source_type="all", rebuild=True)

    response = client.get("/api/admin/corpus/status")
    data = response.json()

    get_settings.cache_clear()
    assert response.status_code == 200
    assert data["preparedSourceCount"] == 1
    assert data["officialPolicySourceCount"] == 1
    assert data["officialGuidanceSourceCount"] == 0
    assert data["preparedChunkCount"] >= 1
    assert data["officialPolicyChunkCount"] >= 1
    assert data["pdfFilesRequiringOcr"] == 0
    assert data["latestIngestionAt"]
    assert data["embeddingProvider"] == "mock"
    assert data["embeddingModel"] == "text-embedding-3-small"
    assert data["embeddingDimension"] == 64
    assert data["activeCollection"] == "uni_navigator_policy_chunks"
    assert data["collectionSourceCount"] == 2
    assert data["collectionChunkCount"] >= 2
    assert data["indexBuiltAt"]
