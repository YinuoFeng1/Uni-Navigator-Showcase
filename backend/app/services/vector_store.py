import json
import logging
import math
from dataclasses import dataclass, field
from importlib.util import find_spec
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.config import Settings, get_settings
from app.services.corpus_loader import PolicyChunk

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION_NAME = "uni_navigator_policy_chunks"


@dataclass(frozen=True)
class VectorSearchResult:
    chunk_id: str
    source_id: str
    title: str
    document_name: str
    section: str
    url: str
    source_type: str
    chunk_text: str
    page_start: int | None = None
    page_end: int | None = None
    source_url: str = ""
    version: str = ""
    effective_date: str = ""
    document_checksum: str = ""
    active: bool = True
    prototype_only: bool = True
    score: float | None = None
    distance: float | None = None
    provider: str | None = None


@dataclass(frozen=True)
class VectorStoreStatus:
    vector_store_provider: str
    active_provider: str
    vector_store_path: str
    collection_name: str
    source_count: int
    chunk_count: int
    fallback_used: bool = False
    chroma_available: bool = False
    embedding_dimension: int | None = None
    collection_metadata: dict[str, Any] = field(default_factory=dict)


class BaseVectorStore:
    active_provider = "local_json"

    def upsert_chunks(
        self,
        chunks: list[PolicyChunk],
        embeddings: list[list[float]],
    ) -> int:
        raise NotImplementedError

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        prefer_official: bool = False,
    ) -> list[VectorSearchResult]:
        raise NotImplementedError

    def status(self) -> VectorStoreStatus:
        raise NotImplementedError

    def clear(self) -> None:
        raise NotImplementedError

    def replace_all(
        self,
        chunks: list[PolicyChunk],
        embeddings: list[list[float]],
        collection_metadata: dict[str, Any] | None = None,
    ) -> int:
        _validate_embedding_matrix(chunks, embeddings)
        self.clear()
        stored = self.upsert_chunks(chunks, embeddings)
        self.set_index_metadata(collection_metadata or {})
        return stored

    def set_index_metadata(self, metadata: dict[str, Any]) -> None:
        return None

    def list_metadata(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    def delete_by_source_ids(self, source_ids: set[str]) -> int:
        raise NotImplementedError

    def delete_by_source_types(self, source_types: set[str]) -> int:
        raise NotImplementedError


class LocalJsonVectorStore(BaseVectorStore):
    active_provider = "local_json"

    def __init__(
        self,
        vector_store_path: str | Path,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        requested_provider: str = "local_json",
        fallback_used: bool = False,
        chroma_available: bool = False,
    ) -> None:
        self.vector_store_path = Path(vector_store_path)
        self.collection_name = collection_name
        self.requested_provider = requested_provider
        self.fallback_used = fallback_used
        self.chroma_available = chroma_available
        self.vector_store_path.mkdir(parents=True, exist_ok=True)
        self.store_file = self.vector_store_path / f"{collection_name}.json"

    def upsert_chunks(
        self,
        chunks: list[PolicyChunk],
        embeddings: list[list[float]],
    ) -> int:
        _validate_embedding_matrix(chunks, embeddings)

        records = {record["chunk_id"]: record for record in self._load_records()}
        for chunk, embedding in zip(chunks, embeddings):
            records[chunk.chunk_id] = {
                "chunk_id": chunk.chunk_id,
                "embedding": embedding,
                "metadata": chunk.metadata(),
            }

        self._write_records(list(records.values()))
        return len(chunks)

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        prefer_official: bool = False,
    ) -> list[VectorSearchResult]:
        scored: list[tuple[float, dict[str, Any]]] = []
        for record in self._load_records():
            metadata = dict(record.get("metadata") or {})
            if not _metadata_matches(metadata, filters):
                continue
            embedding = record.get("embedding")
            if not isinstance(embedding, list):
                continue
            score = _cosine_similarity(query_embedding, embedding)
            scored.append((score, record))

        scored.sort(
            key=lambda item: _result_sort_key(
                item[0], dict(item[1].get("metadata") or {}), prefer_official
            )
        )
        return [
            _result_from_record(record, score=score, distance=1 - score)
            for score, record in scored[:top_k]
        ]

    def status(self) -> VectorStoreStatus:
        records = self._load_records()
        payload = self._load_payload()
        source_ids = {
            str(record.get("metadata", {}).get("source_id"))
            for record in records
            if record.get("metadata", {}).get("source_id")
        }
        return VectorStoreStatus(
            vector_store_provider=self.requested_provider,
            active_provider=self.active_provider,
            vector_store_path=str(self.vector_store_path),
            collection_name=self.collection_name,
            source_count=len(source_ids),
            chunk_count=len(records),
            fallback_used=self.fallback_used,
            chroma_available=self.chroma_available,
            embedding_dimension=_records_embedding_dimension(records),
            collection_metadata=dict(payload.get("index_metadata") or {}),
        )

    def replace_all(
        self,
        chunks: list[PolicyChunk],
        embeddings: list[list[float]],
        collection_metadata: dict[str, Any] | None = None,
    ) -> int:
        _validate_embedding_matrix(chunks, embeddings)
        records = [
            {
                "chunk_id": chunk.chunk_id,
                "embedding": embedding,
                "metadata": chunk.metadata(),
            }
            for chunk, embedding in zip(chunks, embeddings)
        ]
        self._write_records(records, index_metadata=collection_metadata or {})
        return len(chunks)

    def set_index_metadata(self, metadata: dict[str, Any]) -> None:
        self._write_records(self._load_records(), index_metadata=metadata)

    def clear(self) -> None:
        self._write_records([])

    def list_metadata(self) -> list[dict[str, Any]]:
        return [dict(record.get("metadata") or {}) for record in self._load_records()]

    def delete_by_source_ids(self, source_ids: set[str]) -> int:
        return self._delete_matching(
            lambda metadata: str(metadata.get("source_id") or "") in source_ids
        )

    def delete_by_source_types(self, source_types: set[str]) -> int:
        return self._delete_matching(
            lambda metadata: str(metadata.get("source_type") or "") in source_types
        )

    def _delete_matching(self, predicate: Any) -> int:
        records = self._load_records()
        kept = [
            record
            for record in records
            if not predicate(dict(record.get("metadata") or {}))
        ]
        deleted = len(records) - len(kept)
        if deleted:
            self._write_records(kept)
        return deleted

    def _load_records(self) -> list[dict[str, Any]]:
        payload = self._load_payload()
        records = payload.get("records", [])
        return records if isinstance(records, list) else []

    def _load_payload(self) -> dict[str, Any]:
        if not self.store_file.exists():
            return {}
        try:
            payload = json.loads(self.store_file.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    def _write_records(
        self,
        records: list[dict[str, Any]],
        index_metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = self._load_payload()
        temporary = self.store_file.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "collection_name": self.collection_name,
                    "index_metadata": (
                        index_metadata
                        if index_metadata is not None
                        else dict(payload.get("index_metadata") or {})
                    ),
                    "records": records,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        temporary.replace(self.store_file)


class ChromaVectorStore(BaseVectorStore):
    active_provider = "chroma"

    def __init__(
        self,
        vector_store_path: str | Path,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        requested_provider: str = "chroma",
    ) -> None:
        import chromadb

        self.vector_store_path = Path(vector_store_path)
        self.collection_name = collection_name
        self.requested_provider = requested_provider
        self.client = chromadb.PersistentClient(path=str(self.vector_store_path))
        self.collection = self.client.get_or_create_collection(
            collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def upsert_chunks(
        self,
        chunks: list[PolicyChunk],
        embeddings: list[list[float]],
    ) -> int:
        _validate_embedding_matrix(chunks, embeddings)
        if not chunks:
            return 0
        self._upsert_collection(self.collection, chunks, embeddings)
        return len(chunks)

    def _upsert_collection(
        self,
        collection: Any,
        chunks: list[PolicyChunk],
        embeddings: list[list[float]],
    ) -> None:
        collection.upsert(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=embeddings,
            documents=[chunk.chunk_text for chunk in chunks],
            metadatas=[_chroma_metadata(chunk.metadata()) for chunk in chunks],
        )

    def query(
        self,
        query_embedding: list[float],
        top_k: int = 5,
        filters: dict[str, Any] | None = None,
        prefer_official: bool = False,
    ) -> list[VectorSearchResult]:
        count = self.collection.count()
        if count == 0:
            return []
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=count,
            include=["documents", "metadatas", "distances"],
        )
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        ids = result.get("ids", [[]])[0]

        rows: list[VectorSearchResult] = []
        for chunk_id, document, metadata, distance in zip(
            ids, documents, metadatas, distances
        ):
            row = dict(metadata or {})
            row["chunk_id"] = row.get("chunk_id") or chunk_id
            row["chunk_text"] = document
            if not _metadata_matches(row, filters):
                continue
            rows.append(
                _result_from_metadata(
                    row,
                    score=None if distance is None else 1 - float(distance),
                    distance=None if distance is None else float(distance),
                )
            )
        rows.sort(
            key=lambda item: _result_sort_key(
                item.score or 0.0,
                {"source_type": item.source_type},
                prefer_official,
            )
        )
        return rows[:top_k]

    def status(self) -> VectorStoreStatus:
        count = self.collection.count()
        source_count = 0
        if count:
            existing = self.collection.get(include=["metadatas"])
            source_ids = {
                metadata.get("source_id")
                for metadata in existing.get("metadatas", [])
                if metadata and metadata.get("source_id")
            }
            source_count = len(source_ids)

        return VectorStoreStatus(
            vector_store_provider=self.requested_provider,
            active_provider=self.active_provider,
            vector_store_path=str(self.vector_store_path),
            collection_name=self.collection_name,
            source_count=source_count,
            chunk_count=count,
            fallback_used=False,
            chroma_available=True,
            embedding_dimension=self._embedding_dimension(),
            collection_metadata=dict(self.collection.metadata or {}),
        )

    def replace_all(
        self,
        chunks: list[PolicyChunk],
        embeddings: list[list[float]],
        collection_metadata: dict[str, Any] | None = None,
    ) -> int:
        dimension = _validate_embedding_matrix(chunks, embeddings)
        suffix = uuid4().hex[:10]
        staging_name = f"{self.collection_name}__staging__{suffix}"
        backup_name = f"{self.collection_name}__backup__{suffix}"
        metadata = {
            "hnsw:space": "cosine",
            **_chroma_metadata(collection_metadata or {}),
        }
        staging = self.client.create_collection(staging_name, metadata=metadata)
        old_collection = self.collection
        old_renamed = False
        staging_promoted = False
        try:
            if chunks:
                self._upsert_collection(staging, chunks, embeddings)
            if staging.count() != len(chunks):
                raise RuntimeError(
                    "Staging collection count did not match the expected chunk count"
                )
            if dimension is not None and self._collection_dimension(staging) != dimension:
                raise RuntimeError(
                    "Staging collection embedding dimension verification failed"
                )

            old_collection.modify(name=backup_name)
            old_renamed = True
            staging.modify(name=self.collection_name)
            staging_promoted = True
            self.collection = self.client.get_collection(self.collection_name)
        except Exception:
            if old_renamed and not staging_promoted:
                try:
                    old_collection.modify(name=self.collection_name)
                    self.collection = old_collection
                except Exception:
                    logger.exception("Failed to restore the previous Chroma collection")
            if not staging_promoted:
                try:
                    self.client.delete_collection(staging_name)
                except Exception:
                    pass
            raise

        try:
            self.client.delete_collection(backup_name)
        except Exception:
            logger.warning("Completed Chroma promotion but could not delete backup %s", backup_name)
        return len(chunks)

    def set_index_metadata(self, metadata: dict[str, Any]) -> None:
        merged = {
            key: value
            for key, value in dict(self.collection.metadata or {}).items()
            if key != "hnsw:space"
        }
        merged.update(
            {
            **_chroma_metadata(metadata),
            }
        )
        self.collection.modify(metadata=merged)

    def _embedding_dimension(self) -> int | None:
        return self._collection_dimension(self.collection)

    @staticmethod
    def _collection_dimension(collection: Any) -> int | None:
        if not collection.count():
            return None
        embeddings = collection.peek(limit=1).get("embeddings")
        if embeddings is None or len(embeddings) == 0:
            return None
        return len(embeddings[0])

    def clear(self) -> None:
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
        self.collection = self.client.get_or_create_collection(
            self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def list_metadata(self) -> list[dict[str, Any]]:
        if not self.collection.count():
            return []
        existing = self.collection.get(include=["documents", "metadatas"])
        documents = existing.get("documents") or []
        metadatas = existing.get("metadatas") or []
        rows: list[dict[str, Any]] = []
        for index, metadata in enumerate(metadatas):
            row = dict(metadata or {})
            row["chunk_text"] = documents[index] if index < len(documents) else ""
            rows.append(row)
        return rows

    def delete_by_source_ids(self, source_ids: set[str]) -> int:
        return self._delete_where("source_id", source_ids)

    def delete_by_source_types(self, source_types: set[str]) -> int:
        return self._delete_where("source_type", source_types)

    def _delete_where(self, field: str, values: set[str]) -> int:
        if not values or not self.collection.count():
            return 0
        where: dict[str, Any]
        ordered = sorted(values)
        if len(ordered) == 1:
            where = {field: ordered[0]}
        else:
            where = {field: {"$in": ordered}}
        matching = self.collection.get(where=where, include=[])
        ids = matching.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)
        return len(ids)


def get_vector_store(settings: Settings | None = None) -> BaseVectorStore:
    settings = settings or get_settings()
    provider = settings.vector_store_provider
    chroma_available = is_chromadb_available()

    if provider in {"chroma", "auto"}:
        try:
            return ChromaVectorStore(
                vector_store_path=settings.vector_store_path,
                collection_name=settings.vector_collection_name,
                requested_provider=provider,
            )
        except ImportError as exc:
            reason = f"chromadb is not installed: {exc}"
        except Exception as exc:
            reason = f"Chroma vector store unavailable: {exc}"

        if settings.vector_store_allow_fallback:
            logger.warning("%s; using local JSON vector store", reason)
            return LocalJsonVectorStore(
                vector_store_path=settings.vector_store_path,
                collection_name=settings.vector_collection_name,
                requested_provider=provider,
                fallback_used=True,
                chroma_available=chroma_available,
            )
        raise RuntimeError(
            f"{reason}. Set VECTOR_STORE_ALLOW_FALLBACK=true to use local_json."
        )

    if provider != "local_json":
        logger.warning("Unsupported VECTOR_STORE_PROVIDER=%s; using local JSON", provider)

    return LocalJsonVectorStore(
        vector_store_path=settings.vector_store_path,
        collection_name=settings.vector_collection_name,
        requested_provider=provider,
        fallback_used=False,
        chroma_available=chroma_available,
    )


def is_chromadb_available() -> bool:
    return find_spec("chromadb") is not None


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)


def _result_from_record(
    record: dict[str, Any],
    score: float | None,
    distance: float | None,
) -> VectorSearchResult:
    metadata = dict(record.get("metadata") or {})
    metadata["provider"] = "local_json"
    return _result_from_metadata(metadata, score=score, distance=distance)


def _result_from_metadata(
    metadata: dict[str, Any],
    score: float | None,
    distance: float | None,
) -> VectorSearchResult:
    return VectorSearchResult(
        chunk_id=str(metadata.get("chunk_id") or ""),
        source_id=str(metadata.get("source_id") or ""),
        title=str(metadata.get("title") or ""),
        document_name=str(metadata.get("document_name") or ""),
        section=str(metadata.get("section") or ""),
        url=str(metadata.get("url") or ""),
        source_type=str(metadata.get("source_type") or ""),
        chunk_text=str(metadata.get("chunk_text") or ""),
        page_start=_optional_int(metadata.get("page_start")),
        page_end=_optional_int(metadata.get("page_end")),
        source_url=str(metadata.get("source_url") or metadata.get("url") or ""),
        version=str(metadata.get("version") or ""),
        effective_date=str(metadata.get("effective_date") or ""),
        document_checksum=str(metadata.get("document_checksum") or ""),
        active=_metadata_bool(metadata.get("active"), default=True),
        prototype_only=_metadata_bool(
            metadata.get("prototype_only"),
            default=str(metadata.get("source_type") or "") == "prepared_policy",
        ),
        score=score,
        distance=distance,
        provider=str(metadata.get("provider") or ""),
    )


def _chroma_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    cleaned: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            continue
        if isinstance(value, str | int | float | bool):
            cleaned[key] = value
            continue
        cleaned[key] = json.dumps(value, ensure_ascii=False, sort_keys=True)
    cleaned["provider"] = "chroma"
    return cleaned


def _metadata_matches(
    metadata: dict[str, Any], filters: dict[str, Any] | None
) -> bool:
    if not filters:
        return _metadata_bool(metadata.get("active"), default=True)
    for key, expected in filters.items():
        actual = metadata.get(key)
        if key == "active":
            actual = _metadata_bool(actual, default=True)
        elif key == "prototype_only":
            actual = _metadata_bool(
                actual,
                default=str(metadata.get("source_type") or "") == "prepared_policy",
            )
        if isinstance(expected, set | list | tuple):
            if actual not in expected:
                return False
        elif actual != expected:
            return False
    return True


def _result_sort_key(
    score: float,
    metadata: dict[str, Any],
    prefer_official: bool,
) -> tuple[int, float]:
    source_type = str(metadata.get("source_type") or "")
    official_rank = (
        0
        if source_type in {"official_policy", "official_student_guidance"}
        else 1
    )
    return (official_rank if prefer_official else 0, -score)


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None


def _metadata_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() in {"true", "1", "yes"}:
            return True
        if value.lower() in {"false", "0", "no"}:
            return False
    return default


def _records_embedding_dimension(records: list[dict[str, Any]]) -> int | None:
    for record in records:
        embedding = record.get("embedding")
        if isinstance(embedding, list) and embedding:
            return len(embedding)
    return None


def _validate_embedding_matrix(
    chunks: list[PolicyChunk],
    embeddings: list[list[float]],
) -> int | None:
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must have the same length")
    if not embeddings:
        return None
    dimensions: set[int] = set()
    for embedding in embeddings:
        if not isinstance(embedding, list) or not embedding:
            raise ValueError("embedding vectors must be non-empty lists")
        if any(
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not math.isfinite(float(value))
            for value in embedding
        ):
            raise ValueError("embedding vectors must contain finite numeric values")
        dimensions.add(len(embedding))
    if len(dimensions) != 1:
        raise ValueError("embedding vectors must have a consistent dimension")
    return next(iter(dimensions))
