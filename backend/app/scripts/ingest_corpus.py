import argparse
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.services.corpus_loader import (
    OFFICIAL_SOURCE_TYPES,
    PREPARED_SOURCE_TYPE,
    PolicyChunk,
    PolicyDocument,
    SourceSelection,
    chunk_policy_documents,
    load_corpus_with_report,
)
from app.services.corpus_manifest import update_ingestion_manifest
from app.services.embedding_service import get_embedding_provider
from app.services.vector_store import BaseVectorStore, get_vector_store


def ingest_corpus(
    rebuild: bool = False,
    source_type: SourceSelection = "all",
    validate_only: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    settings = get_settings()
    load_result = load_corpus_with_report(
        settings.corpus_path,
        source_type=source_type,
    )
    documents = load_result.documents
    report = load_result.report
    chunks = chunk_policy_documents(documents)
    vector_store = get_vector_store(settings)
    status_before = vector_store.status()
    existing_metadata = vector_store.list_metadata()
    existing_by_source = _metadata_by_source(existing_metadata)
    chunks_by_source = _chunks_by_source(chunks)

    unchanged_sources: set[str] = set()
    changed_sources: set[str] = set()
    new_sources: set[str] = set()
    removable_sources: set[str] = set()
    chunks_to_store: list[PolicyChunk] = []

    for document in documents:
        existing = existing_by_source.get(document.source_id, [])
        existing_types = {
            str(item.get("source_type") or "") for item in existing
        }
        if existing_types and any(
            _source_group(item) != _source_group(document.source_type)
            for item in existing_types
        ):
            report.invalid_files.append(
                f"source_id {document.source_id!r} conflicts with existing vector "
                f"source type(s): {', '.join(sorted(existing_types))}"
            )
            continue
        document_chunks = chunks_by_source.get(document.source_id, [])
        if not document.active or document.ocr_required:
            if existing:
                removable_sources.add(document.source_id)
                changed_sources.add(document.source_id)
            continue
        if not existing:
            new_sources.add(document.source_id)
            chunks_to_store.extend(document_chunks)
            continue
        if _source_is_unchanged(document, document_chunks, existing) and not rebuild:
            unchanged_sources.add(document.source_id)
            continue
        removable_sources.add(document.source_id)
        changed_sources.add(document.source_id)
        chunks_to_store.extend(document_chunks)

    active_ocr_sources = sum(
        1 for document in documents if document.active and document.ocr_required
    )
    validation_failed = bool(report.invalid_files) or active_ocr_sources > 0
    should_write = not validate_only and not dry_run and not validation_failed
    deleted_chunks = 0
    stored_count = 0
    embeddings: list[list[float]] = []
    embedding_dimension: int | None = status_before.embedding_dimension
    index_built_at: str | None = None

    if should_write and (chunks_to_store or removable_sources or rebuild):
        index_built_at = datetime.now(timezone.utc).isoformat()

    if should_write and chunks_to_store:
        embedding_provider = get_embedding_provider(settings)
        embeddings = embedding_provider.embed_texts(
            [chunk.chunk_text for chunk in chunks_to_store]
        )
        dimensions = {len(embedding) for embedding in embeddings}
        if len(dimensions) != 1:
            raise RuntimeError("Embedding provider returned inconsistent dimensions")
        embedding_dimension = next(iter(dimensions))

    index_metadata = {
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "embedding_dimension": embedding_dimension or 0,
        "index_built_at": index_built_at or "",
    }

    if should_write:
        if rebuild and source_type == "all":
            deleted_chunks = status_before.chunk_count
            stored_count = vector_store.replace_all(
                chunks_to_store,
                embeddings,
                collection_metadata=index_metadata,
            )
        elif rebuild:
            deleted_chunks += _scoped_rebuild(vector_store, source_type)
        elif removable_sources:
            deleted_chunks += vector_store.delete_by_source_ids(removable_sources)

        if chunks_to_store and not (rebuild and source_type == "all"):
            stored_count = vector_store.upsert_chunks(chunks_to_store, embeddings)
        if stored_count or deleted_chunks:
            current_status = vector_store.status()
            index_metadata.update(
                {
                    "embedding_dimension": current_status.embedding_dimension or 0,
                    "source_count": current_status.source_count,
                    "chunk_count": current_status.chunk_count,
                }
            )
            vector_store.set_index_metadata(index_metadata)

        current_status = vector_store.status()
        collection_metadata = current_status.collection_metadata
        update_ingestion_manifest(
            settings.vector_store_path,
            documents,
            source_selection=source_type,
            rebuild=rebuild,
            collection_name=current_status.collection_name,
            embedding_provider=settings.embedding_provider,
            embedding_model=settings.embedding_model,
            embedding_dimension=current_status.embedding_dimension,
            source_count=current_status.source_count,
            chunk_count=current_status.chunk_count,
            index_built_at=(
                str(collection_metadata.get("index_built_at") or "") or None
            ),
        )

    status = vector_store.status()
    embedding_warning = (
        "Mock embeddings are deterministic development fixtures and are not suitable "
        "for final retrieval-quality evaluation."
        if settings.embedding_provider == "mock"
        else ""
    )
    summary = {
        "files_discovered": report.files_discovered,
        "metadata_files_validated": report.metadata_files_validated,
        "pdfs_extracted": report.pdfs_extracted,
        "pages_extracted": report.pages_extracted,
        "pdfs_requiring_ocr": report.pdfs_requiring_ocr,
        "active_pdfs_requiring_ocr": active_ocr_sources,
        "invalid_files": len(report.invalid_files),
        "invalid_file_details": report.invalid_files,
        "warnings": report.warnings,
        "documents_loaded": len(documents),
        "unchanged_files_skipped": len(unchanged_sources),
        "changed_files_replaced": len(changed_sources),
        "new_files": len(new_sources),
        "chunks_created": len(chunks),
        "chunks_would_store": len(chunks_to_store),
        "chunks_stored": stored_count,
        "chunks_deleted": deleted_chunks,
        "corpus_path": str(settings.corpus_path),
        "vector_store_path": status.vector_store_path,
        "vector_store_provider": status.vector_store_provider,
        "active_vector_store_provider": status.active_provider,
        "vector_store_provider_requested": status.vector_store_provider,
        "vector_store_provider_active": status.active_provider,
        "collection_name": status.collection_name,
        "active_collection": status.collection_name,
        "fallback_used": status.fallback_used,
        "chroma_available": status.chroma_available,
        "source_count": status.source_count,
        "chunk_count": status.chunk_count,
        "source_type": source_type,
        "validate_only": validate_only,
        "dry_run": dry_run,
        "rebuild": rebuild,
        "validation_failed": validation_failed,
        "embedding_provider": settings.embedding_provider,
        "embedding_model": settings.embedding_model,
        "embedding_dimension": status.embedding_dimension,
        "index_built_at": status.collection_metadata.get("index_built_at"),
        "embedding_provider_warning": embedding_warning,
        "collection_unchanged": (
            status_before.chunk_count == status.chunk_count
            and stored_count == 0
            and deleted_chunks == 0
        ),
    }
    return summary


def _source_is_unchanged(
    document: PolicyDocument,
    chunks: list[PolicyChunk],
    existing: list[dict[str, Any]],
) -> bool:
    if not existing:
        return False
    expected_ids = {chunk.chunk_id for chunk in chunks}
    existing_ids = {str(item.get("chunk_id") or "") for item in existing}
    if expected_ids != existing_ids:
        return False
    return all(
        str(item.get("document_checksum") or "") == document.document_checksum
        and str(item.get("version") or "") == document.version
        and str(item.get("effective_date") or "") == document.effective_date
        and str(item.get("source_url") or item.get("url") or "") == document.url
        and str(item.get("title") or "") == document.title
        and _metadata_bool(item.get("active"), default=True) == document.active
        for item in existing
    )


def _metadata_by_source(
    metadata_items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for metadata in metadata_items:
        source_id = str(metadata.get("source_id") or "")
        if source_id:
            grouped[source_id].append(metadata)
    return grouped


def _chunks_by_source(chunks: list[PolicyChunk]) -> dict[str, list[PolicyChunk]]:
    grouped: dict[str, list[PolicyChunk]] = defaultdict(list)
    for chunk in chunks:
        grouped[chunk.source_id].append(chunk)
    return grouped


def _scoped_rebuild(
    vector_store: BaseVectorStore,
    source_type: SourceSelection,
) -> int:
    if source_type == "all":
        count = vector_store.status().chunk_count
        vector_store.clear()
        return count
    if source_type == "prepared":
        return vector_store.delete_by_source_types({PREPARED_SOURCE_TYPE})
    if source_type == "official":
        return vector_store.delete_by_source_types(set(OFFICIAL_SOURCE_TYPES))
    raise ValueError(f"Unsupported scoped rebuild selection: {source_type}")


def _metadata_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in {"true", "1", "yes"}:
            return True
        if value.lower() in {"false", "0", "no"}:
            return False
    return default


def _source_group(source_type: str) -> str:
    if source_type == PREPARED_SOURCE_TYPE:
        return "prepared"
    if source_type in OFFICIAL_SOURCE_TYPES:
        return "official"
    return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest Uni-Navigator policy corpus")
    parser.add_argument(
        "--source-type",
        choices=["prepared", "official", "all"],
        default="all",
        help="Select prepared sources, official PDF sources, or both.",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate and extract the selected corpus without changing the vector store.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan deduplication and replacement without changing the vector store.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild only the selected corpus source type(s).",
    )
    args = parser.parse_args()

    summary = ingest_corpus(
        rebuild=args.rebuild,
        source_type=args.source_type,
        validate_only=args.validate_only,
        dry_run=args.dry_run,
    )
    print("Uni-Navigator corpus ingestion report")
    for key, value in summary.items():
        print(f"{key.replace('_', ' ')}: {value}")
    if summary["validation_failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
