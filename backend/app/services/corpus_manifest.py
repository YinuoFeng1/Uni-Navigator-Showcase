import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.corpus_loader import PolicyDocument, SourceSelection


MANIFEST_FILENAME = "ingestion_manifest.json"
DEFAULT_COLLECTION_NAME = "uni_navigator_policy_chunks"


def manifest_path(
    vector_store_path: str | Path,
    collection_name: str | None = None,
) -> Path:
    if not collection_name or collection_name == DEFAULT_COLLECTION_NAME:
        return Path(vector_store_path) / MANIFEST_FILENAME
    safe_name = "".join(
        character if character.isalnum() or character in {"-", "_"} else "_"
        for character in collection_name
    )
    return Path(vector_store_path) / f"ingestion_manifest.{safe_name}.json"


def load_ingestion_manifest(
    vector_store_path: str | Path,
    collection_name: str | None = None,
) -> dict[str, Any]:
    path = manifest_path(vector_store_path, collection_name)
    if not path.exists():
        return {"latest_ingestion_at": None, "sources": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"latest_ingestion_at": None, "sources": {}}
    if not isinstance(payload, dict):
        return {"latest_ingestion_at": None, "sources": {}}
    sources = payload.get("sources")
    if not isinstance(sources, dict):
        payload["sources"] = {}
    return payload


def update_ingestion_manifest(
    vector_store_path: str | Path,
    documents: list[PolicyDocument],
    source_selection: SourceSelection,
    rebuild: bool,
    collection_name: str = DEFAULT_COLLECTION_NAME,
    embedding_provider: str = "",
    embedding_model: str = "",
    embedding_dimension: int | None = None,
    source_count: int | None = None,
    chunk_count: int | None = None,
    index_built_at: str | None = None,
) -> dict[str, Any]:
    payload = load_ingestion_manifest(vector_store_path, collection_name)
    sources = dict(payload.get("sources") or {})
    selected_types = _source_types(source_selection)
    if rebuild:
        sources = {
            source_id: value
            for source_id, value in sources.items()
            if not isinstance(value, dict)
            or value.get("source_type") not in selected_types
        }

    for document in documents:
        sources[document.source_id] = {
            "source_id": document.source_id,
            "source_type": document.source_type,
            "active": document.active,
            "prototype_only": document.prototype_only,
            "ocr_required": document.ocr_required,
            "document_checksum": document.document_checksum,
            "version": document.version,
            "effective_date": document.effective_date,
            "superseded_date": document.superseded_date,
            "path": document.path,
        }

    payload = {
        "latest_ingestion_at": datetime.now(timezone.utc).isoformat(),
        "index_built_at": index_built_at or payload.get("index_built_at"),
        "collection_name": collection_name,
        "embedding_provider": embedding_provider,
        "embedding_model": embedding_model,
        "embedding_dimension": embedding_dimension,
        "source_count": source_count,
        "chunk_count": chunk_count,
        "source_selection": source_selection,
        "sources": sources,
    }
    path = manifest_path(vector_store_path, collection_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    temporary.replace(path)
    return payload


def _source_types(source_selection: SourceSelection) -> set[str]:
    if source_selection == "prepared":
        return {"prepared_policy"}
    if source_selection == "official":
        return {"official_policy", "official_student_guidance"}
    return {"prepared_policy", "official_policy", "official_student_guidance"}
