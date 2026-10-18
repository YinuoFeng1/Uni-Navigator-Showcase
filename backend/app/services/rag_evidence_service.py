from __future__ import annotations

import re
from typing import Any

from app.core.errors import ApplicationError
from app.schemas import Citation, ScopeDecisionResponse
from app.services.corpus_scope_service import ScopeDecision


OFFICIAL_SOURCE_TYPES = {"official_policy", "official_student_guidance"}
NO_CITATION_STATUSES = {"insufficient_evidence"}
INSUFFICIENT_EVIDENCE_MARKERS = (
    "not enough matching official policy evidence",
    "not enough official policy evidence",
    "insufficient official policy evidence",
    "could not find enough official policy evidence",
    "do not have enough official policy evidence",
    "do not have enough matching official policy evidence",
)
UNCITED_META_PREFIXES = (
    "ask authorised university staff",
    "check the cited",
    "confirm this with authorised university staff",
    "contact authorised university staff",
    "review the cited",
    "the available evidence does not establish",
    "the official evidence does not establish",
    "the retrieved evidence does not establish",
    "the retrieved official policy evidence does not establish",
    "your individual outcome needs",
    "your personal outcome needs",
)
DISALLOWED_ANSWER_PHRASES = (
    "as an ai",
    "not official university advice",
    "research prototype",
)
DISALLOWED_SOURCE_BACKED_OPENINGS = (
    "according to the retrieved",
    "based on the evidence",
    "based on the retrieved",
    "i found",
    "the retrieved evidence",
)
MAX_ANSWER_WORDS = 180


def select_official_policy_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only active, traceable passages from the official policy corpus."""

    return [
        chunk
        for chunk in chunks
        if chunk.get("active", True) is not False
        and chunk.get("source_type") in OFFICIAL_SOURCE_TYPES
        and _text(chunk.get("source_id"))
        and _text(chunk.get("chunk_id"))
        and (_text(chunk.get("chunk_text")) or _text(chunk.get("passage")))
    ]


def citations_from_chunks(chunks: list[dict[str, Any]]) -> list[Citation]:
    citations: list[Citation] = []
    for index, chunk in enumerate(chunks, start=1):
        label = f"[{index}]"
        citation_id = f"c{index}"
        passage = _text(chunk.get("chunk_text")) or _text(chunk.get("passage"))
        document_name = _text(chunk.get("document_name"))
        title = _text(chunk.get("title")) or document_name or "Retrieved policy source"
        section = _text(chunk.get("section")) or None
        url = _text(chunk.get("url")) or None
        score = _score(chunk.get("score"))

        citations.append(
            Citation(
                id=citation_id,
                citationId=citation_id,
                label=label,
                sourceId=_text(chunk.get("source_id")),
                chunkId=_text(chunk.get("chunk_id")),
                title=title,
                documentName=document_name or title,
                documentTitle=title,
                section=section,
                sectionHeading=section,
                pageNumber=_page_number(chunk),
                pageStart=_optional_int(chunk.get("page_start")),
                pageEnd=_optional_int(chunk.get("page_end")),
                passage=passage,
                quotedText=passage,
                surroundingText=passage,
                url=url,
                sourceUrl=url,
                score=score,
                relevanceScore=score,
                sourceType=_text(chunk.get("source_type")) or None,
                version=_text(chunk.get("version")) or None,
                effectiveDate=_text(chunk.get("effective_date")) or None,
            )
        )

    return citations


def build_retrieved_context(citations: list[Citation]) -> str:
    blocks: list[str] = []
    for citation in citations:
        lines = [
            f"{citation.label} {citation.citationId}",
            f"source_id: {citation.sourceId or ''}",
            f"chunk_id: {citation.chunkId}",
            f"title: {citation.title or citation.documentTitle}",
            f"document_name: {citation.documentName or citation.documentTitle}",
            f"section: {citation.section or citation.sectionHeading or ''}",
            f"source_type: {citation.sourceType or ''}",
            f"page_start: {citation.pageStart or ''}",
            f"page_end: {citation.pageEnd or ''}",
            f"version: {citation.version or ''}",
            f"effective_date: {citation.effectiveDate or ''}",
            f"url: {citation.url or citation.sourceUrl or ''}",
            f"passage: {citation.passage or citation.quotedText}",
        ]
        blocks.append("\n".join(lines))
    return "\n\n---\n\n".join(blocks)


def retrieval_trace_from_chunks(
    chunks: list[dict[str, Any]], citations: list[Citation]
) -> list[dict[str, Any]]:
    citation_labels = {
        item.chunkId: item.label for item in citations if item.chunkId and item.label
    }
    return [
        {
            "rank": rank,
            "chunk_id": _text(chunk.get("chunk_id")),
            "source_id": _text(chunk.get("source_id")),
            "source_type": _text(chunk.get("source_type")),
            "score": _score(chunk.get("score")),
            "distance": _score(chunk.get("distance")),
            "page_start": _optional_int(chunk.get("page_start")),
            "page_end": _optional_int(chunk.get("page_end")),
            "citation_label": citation_labels.get(_text(chunk.get("chunk_id"))),
        }
        for rank, chunk in enumerate(chunks, start=1)
    ]


def validate_answer_citations(
    answer: str,
    citations: list[Citation],
    *,
    retrieval_status: str,
) -> None:
    """Fail closed when a live answer breaks the grounded answer contract."""

    normalized_answer = answer.strip()
    if not normalized_answer:
        _citation_failure("LLM answer was empty")

    lowered_answer = _normalize_validation_text(normalized_answer)
    if any(phrase in lowered_answer for phrase in DISALLOWED_ANSWER_PHRASES):
        _citation_failure("LLM answer repeated a disallowed general disclaimer")
    if len(re.findall(r"\b[\w'-]+\b", normalized_answer)) > MAX_ANSWER_WORDS:
        _citation_failure("LLM answer exceeded the concise answer limit")

    allowed = {item.label for item in citations if item.label}
    used = set(re.findall(r"\[\d+\]", normalized_answer))
    unavailable = used - allowed
    if unavailable:
        _citation_failure("LLM answer referenced an unavailable citation label")
    if allowed and not used:
        _citation_failure("source-backed LLM answer omitted citation labels")
    if not allowed and used:
        _citation_failure("answer cited evidence when no evidence was selected")

    if not allowed:
        if retrieval_status != "insufficient_evidence":
            _citation_failure("answer had no evidence outside insufficient-evidence mode")
        if not any(marker in lowered_answer for marker in INSUFFICIENT_EVIDENCE_MARKERS):
            _citation_failure("unsupported answer did not acknowledge insufficient evidence")
        return

    if lowered_answer.startswith(DISALLOWED_SOURCE_BACKED_OPENINGS):
        _citation_failure("source-backed answer did not begin with a direct answer")

    for sentence in _sentences(normalized_answer):
        if re.search(r"\[\d+\]", sentence):
            continue
        lowered_sentence = _normalize_validation_text(sentence).lstrip("-*• ")
        if _is_uncited_meta_sentence(lowered_sentence):
            continue
        preview = sentence[:160]
        _citation_failure(
            "a source-backed answer sentence omitted its citation label: "
            f"{preview}"
        )


def _sentences(answer: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+(?!\[\d+\])|\n+", answer)
        if sentence.strip()
    ]


def _normalize_validation_text(value: str) -> str:
    normalized = value.casefold().replace("’", "'")
    for contraction, expanded in (
        ("isn't", "is not"),
        ("don't", "do not"),
        ("doesn't", "does not"),
        ("couldn't", "could not"),
    ):
        normalized = normalized.replace(contraction, expanded)
    return normalized


def _is_uncited_meta_sentence(sentence: str) -> bool:
    if sentence.startswith(UNCITED_META_PREFIXES):
        return True
    if re.fullmatch(
        r"your (?:personal|individual) .{1,80} needs confirmation by "
        r"authorised university staff\.?",
        sentence,
    ):
        return True
    if re.fullmatch(
        r"for your (?:personal|individual) .{1,80}, authorised university "
        r"staff (?:would )?need to confirm .{1,120}\.?",
        sentence,
    ):
        return True
    if sentence.startswith(("if ", "whether ")) and any(
        marker in sentence
        for marker in (
            "retrieved official policy evidence does not establish",
            "not established by the retrieved policy evidence",
        )
    ):
        return True
    return False


def _citation_failure(detail: str) -> None:
    raise ApplicationError(
        "citation_validation_failed",
        researcher_safe_detail=detail,
    )


def scope_response(decision: ScopeDecision) -> ScopeDecisionResponse:
    return ScopeDecisionResponse(
        decision=decision.decision,
        matchedTopics=decision.matched_topics,
        supportingSourceIds=decision.supporting_source_ids,
        reasons=decision.reasons,
        ruleSignals=decision.rule_signals,
        retrievalSignals=decision.retrieval_signals,
        confidenceCategory=decision.confidence_category,
        registryVersion=decision.registry_version,
        escalationCategory=decision.escalation_category,
    )


def is_explicitly_out_of_scope(decision: ScopeDecision) -> bool:
    return decision.decision == "out_of_scope" and any(
        signal.startswith("unsupported_phrase:") for signal in decision.rule_signals
    )


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _score(value: Any) -> float | None:
    return float(value) if isinstance(value, int | float) else None


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


def _page_number(chunk: dict[str, Any]) -> int | None:
    page_start = _optional_int(chunk.get("page_start"))
    page_end = _optional_int(chunk.get("page_end"))
    return page_start if page_start == page_end else None
