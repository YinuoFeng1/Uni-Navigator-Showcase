from dataclasses import asdict
import re
from typing import Any

from app.config import Settings, get_settings
from app.services.embedding_service import get_embedding_provider
from app.services.corpus_manifest import load_ingestion_manifest
from app.services.vector_store import get_vector_store

LEXICAL_STOP_WORDS = {
    "a",
    "about",
    "after",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "been",
    "before",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "due",
    "for",
    "from",
    "had",
    "has",
    "have",
    "how",
    "if",
    "in",
    "into",
    "is",
    "it",
    "may",
    "must",
    "of",
    "on",
    "or",
    "say",
    "says",
    "should",
    "student",
    "students",
    "that",
    "the",
    "their",
    "them",
    "they",
    "this",
    "to",
    "under",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "will",
    "with",
    "without",
    "would",
}

RETRIEVAL_QUERY_EXPANSION_VERSION = "uq-policy-query-v2"
HYBRID_VECTOR_WEIGHT = 0.70
HYBRID_LEXICAL_WEIGHT = 0.30
POLICY_CONCEPT_BOOST = 0.20


def retrieve_policy_chunks(
    query: str,
    top_k: int = 5,
    settings: Settings | None = None,
    source_types: set[str] | None = None,
    include_inactive: bool = False,
    prototype_only: bool | None = None,
    source_mode: str | None = None,
    embedding_provider: Any | None = None,
    vector_store: Any | None = None,
) -> list[dict]:
    settings = settings or get_settings()
    embedding_provider = embedding_provider or get_embedding_provider(settings)
    vector_store = vector_store or get_vector_store(settings)
    retrieval_query = _expand_retrieval_query(query)
    query_embedding = embedding_provider.embed_texts([retrieval_query])[0]
    mode = source_mode or settings.retrieval_source_mode
    filters: dict[str, Any] = {}
    if not include_inactive:
        filters["active"] = True
    if source_types:
        filters["source_type"] = source_types
    elif mode == "prepared":
        filters["source_type"] = {"prepared_policy"}
    elif mode == "official":
        filters["source_type"] = {
            "official_policy",
            "official_student_guidance",
        }
    if prototype_only is not None:
        filters["prototype_only"] = prototype_only
    candidate_count = (
        max(top_k * 4, 50)
        if retrieval_query != query
        else max(top_k * 4, top_k)
    )
    results = vector_store.query(
        query_embedding,
        top_k=candidate_count,
        filters=filters,
        prefer_official=mode == "prefer_official",
    )
    rows = [asdict(result) for result in results]
    if retrieval_query != query:
        rows = _rerank_expanded_results(retrieval_query, rows)
    if settings.embedding_provider == "mock":
        rows = [
            row
            for row in rows
            if _has_lexical_overlap(query, str(row.get("chunk_text") or ""))
        ]
    return rows[:top_k]


def _expand_retrieval_query(query: str) -> str:
    normalized = " ".join(query.casefold().split())
    concepts: list[str] = []
    if any(
        phrase in normalized
        for phrase in (
            "course overload",
            "extra courses",
            "normal study load",
            "exceed the study load",
            "overload",
        )
    ):
        concepts.append(
            "semester enrolment limits approval extending the limit for enrolment "
            "Associate Dean Academic"
        )
    if "special circumstance" in normalized and any(
        phrase in normalized
        for phrase in ("fee", "financial liability", "refund")
    ):
        concepts.append(
            "student refund after census removal of financial liability refund review"
        )
    if not concepts:
        return query
    return f"{query} Retrieval concepts: {' '.join(concepts)}"


def _rerank_expanded_results(
    query: str, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    query_terms = _content_terms(query)
    if not query_terms:
        return rows

    def hybrid_score(row: dict[str, Any]) -> float:
        vector_score = float(row.get("score") or 0.0)
        passage = str(row.get("chunk_text") or "")
        passage_terms = _content_terms(passage)
        lexical_score = len(query_terms & passage_terms) / len(query_terms)
        return (
            HYBRID_VECTOR_WEIGHT * vector_score
            + HYBRID_LEXICAL_WEIGHT * lexical_score
            + _policy_concept_boost(query, passage)
        )

    return sorted(rows, key=hybrid_score, reverse=True)


def _policy_concept_boost(query: str, passage: str) -> float:
    query_terms = _content_terms(query)
    passage_terms = _content_terms(passage)
    asks_about_overload = bool(
        query_terms
        & {"overload", "extra", "exceed", "limit", "limits", "load"}
    ) and bool(
        query_terms & {"course", "courses", "enrolment", "semester", "study"}
    )
    describes_overload_approval = {
        "approval",
        "extending",
        "limit",
        "enrolment",
        "semester",
    }.issubset(passage_terms)
    if asks_about_overload and describes_overload_approval:
        return POLICY_CONCEPT_BOOST
    return 0.0


def classify_retrieval_status(
    chunks: list[dict],
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    if not chunks:
        return "insufficient_evidence"

    scores = [
        float(chunk["score"])
        for chunk in chunks
        if isinstance(chunk.get("score"), int | float)
    ]
    if not scores:
        return "grounded" if len(chunks) >= 2 else "partial_evidence"

    top_score = max(scores)
    partial_threshold = settings.retrieval_partial_score_threshold
    grounded_threshold = settings.retrieval_grounded_score_threshold
    if top_score < partial_threshold:
        return "insufficient_evidence"
    if top_score >= grounded_threshold:
        return "grounded"
    return "partial_evidence"


def _has_lexical_overlap(query: str, passage: str) -> bool:
    query_terms = _content_terms(query)
    if not query_terms:
        return False
    overlap_count = len(query_terms.intersection(_content_terms(passage)))
    minimum_matches = 2 if len(query_terms) >= 4 else 1
    return overlap_count >= minimum_matches


def _content_terms(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) >= 3 and token not in LEXICAL_STOP_WORDS
    }


def get_corpus_status(settings: Settings | None = None) -> dict:
    settings = settings or get_settings()
    vector_store = get_vector_store(settings)
    status = vector_store.status()
    metadata = vector_store.list_metadata()
    manifest = load_ingestion_manifest(
        settings.vector_store_path,
        status.collection_name,
    )
    source_ids_by_type: dict[str, set[str]] = {
        "prepared_policy": set(),
        "official_policy": set(),
        "official_student_guidance": set(),
    }
    chunk_counts: dict[str, int] = {
        "prepared_policy": 0,
        "official_policy": 0,
        "official_student_guidance": 0,
    }
    for item in metadata:
        source_type = str(item.get("source_type") or "")
        source_id = str(item.get("source_id") or "")
        if source_type in source_ids_by_type and source_id:
            source_ids_by_type[source_type].add(source_id)
            chunk_counts[source_type] += 1
    manifest_sources = [
        item
        for item in (manifest.get("sources") or {}).values()
        if isinstance(item, dict)
    ]
    return {
        "corpusPath": str(settings.corpus_path),
        "vectorStorePath": status.vector_store_path,
        "collectionName": status.collection_name,
        "activeCollection": status.collection_name,
        "collectionChunkCount": status.chunk_count,
        "collectionSourceCount": status.source_count,
        "sourceCount": status.source_count,
        "chunkCount": status.chunk_count,
        "vectorStoreProvider": status.vector_store_provider,
        "activeVectorStoreProvider": status.active_provider,
        "vectorStoreProviderRequested": status.vector_store_provider,
        "vectorStoreProviderActive": status.active_provider,
        "vectorStoreCollection": status.collection_name,
        "fallbackUsed": status.fallback_used,
        "chromaAvailable": status.chroma_available,
        "embeddingProvider": str(
            status.collection_metadata.get("embedding_provider")
            or manifest.get("embedding_provider")
            or settings.embedding_provider
        ),
        "embeddingModel": str(
            status.collection_metadata.get("embedding_model")
            or manifest.get("embedding_model")
            or settings.embedding_model
        ),
        "embeddingDimension": (
            status.embedding_dimension or manifest.get("embedding_dimension")
        ),
        "indexBuiltAt": (
            status.collection_metadata.get("index_built_at")
            or manifest.get("index_built_at")
        ),
        "retrievalSourceMode": settings.retrieval_source_mode,
        "retrievalPartialScoreThreshold": settings.retrieval_partial_score_threshold,
        "retrievalGroundedScoreThreshold": settings.retrieval_grounded_score_threshold,
        "preparedSourceCount": len(source_ids_by_type["prepared_policy"]),
        "officialPolicySourceCount": len(source_ids_by_type["official_policy"]),
        "officialGuidanceSourceCount": len(
            source_ids_by_type["official_student_guidance"]
        ),
        "preparedChunkCount": chunk_counts["prepared_policy"],
        "officialPolicyChunkCount": chunk_counts["official_policy"],
        "officialGuidanceChunkCount": chunk_counts[
            "official_student_guidance"
        ],
        "inactiveSourceCount": sum(
            1 for item in manifest_sources if item.get("active") is False
        ),
        "pdfFilesRequiringOcr": sum(
            1 for item in manifest_sources if item.get("ocr_required") is True
        ),
        "latestIngestionAt": manifest.get("latest_ingestion_at"),
    }
