from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import re
from pathlib import Path
from typing import Any, Iterable

from app.schemas import RetrievalStatus


ScopeDecisionValue = str


@dataclass(frozen=True)
class ScopeDecision:
    decision: ScopeDecisionValue
    matched_topics: list[str] = field(default_factory=list)
    supporting_source_ids: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    rule_signals: list[str] = field(default_factory=list)
    retrieval_signals: dict[str, Any] = field(default_factory=dict)
    confidence_category: str = "low"
    registry_version: str = "unknown"
    escalation_category: str = "insufficient_evidence_or_clarify"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_scope_registry(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to load scope registry at {path}: {exc}") from exc

    if not payload.get("registry_version") or not payload.get("topics"):
        raise ValueError("Scope registry must include registry_version and topics")
    return payload


def decide_corpus_scope(
    question: str,
    retrieved_chunks: Iterable[Any],
    registry: dict[str, Any],
    *,
    partial_threshold: float,
    grounded_threshold: float,
) -> ScopeDecision:
    normalized_question = _normalize(question)
    chunks = list(retrieved_chunks)
    retrieval_signals = _retrieval_signals(chunks, question)
    registry_version = str(registry.get("registry_version", "unknown"))

    topic_matches: list[tuple[dict[str, Any], list[str]]] = []
    for topic in registry.get("topics", []):
        phrases = _topic_phrases(topic)
        matches = [phrase for phrase in phrases if _contains_phrase(normalized_question, phrase)]
        if matches:
            topic_matches.append((topic, matches))

    ambiguous_match = _first_group_phrase_match(
        normalized_question, registry.get("ambiguous_adjacent_scope", [])
    )
    matched_topics = [str(topic.get("topic_id")) for topic, _ in topic_matches]
    expected_sources = {
        str(source_id)
        for topic, _ in topic_matches
        for source_id in topic.get("source_ids", [])
    }
    retrieved_sources = set(retrieval_signals.get("source_ids", []))
    supporting_sources = sorted(expected_sources & retrieved_sources)
    rule_signals = [
        f"topic_phrase:{topic.get('topic_id')}:{phrase}"
        for topic, matches in topic_matches
        for phrase in matches
    ]

    unsupported_match = _first_group_phrase_match(
        normalized_question, registry.get("explicitly_unsupported", [])
    )
    if unsupported_match:
        group, phrase = unsupported_match
        mixed_scope = bool(topic_matches) and group.get("category") != "out_of_domain"
        return ScopeDecision(
            decision="ambiguous" if mixed_scope else "out_of_scope",
            matched_topics=matched_topics,
            supporting_source_ids=supporting_sources,
            reasons=[
                (
                    "The query combines a supported policy topic with an explicitly unsupported adjacent topic."
                    if mixed_scope
                    else f"The query explicitly matches an unsupported {group.get('category', 'topic')}."
                )
            ],
            rule_signals=[*rule_signals, f"unsupported_phrase:{phrase}"],
            retrieval_signals=retrieval_signals,
            confidence_category="high",
            registry_version=registry_version,
            escalation_category=str(
                group.get(
                    "escalation_category", "insufficient_evidence_or_clarify"
                )
            ),
        )

    adjacent_match = _topic_adjacent_match(normalized_question, topic_matches)
    if adjacent_match:
        topic, phrase = adjacent_match
        escalation_category = (
            "international_student_or_visa_support"
            if "visa" in phrase or "migration" in phrase
            else str(
                topic.get(
                    "default_escalation_category",
                    "insufficient_evidence_or_clarify",
                )
            )
        )
        return ScopeDecision(
            decision="ambiguous",
            matched_topics=matched_topics,
            supporting_source_ids=supporting_sources,
            reasons=[
                "The query matches a supported topic but also asks about an adjacent issue explicitly excluded by that topic registry entry."
            ],
            rule_signals=[
                *rule_signals,
                f"unsupported_adjacent:{topic.get('topic_id')}:{phrase}",
            ],
            retrieval_signals=retrieval_signals,
            confidence_category="high",
            registry_version=registry_version,
            escalation_category=escalation_category,
        )

    if ambiguous_match and (
        not topic_matches or ambiguous_match[0].get("always_ambiguous", True)
    ):
        group, phrase = ambiguous_match
        return ScopeDecision(
            decision="ambiguous",
            matched_topics=matched_topics,
            supporting_source_ids=supporting_sources,
            reasons=[str(group.get("reason", "The query needs clarification."))],
            rule_signals=[*rule_signals, f"ambiguous_phrase:{phrase}"],
            retrieval_signals=retrieval_signals,
            confidence_category="medium",
            registry_version=registry_version,
            escalation_category=str(
                group.get(
                    "escalation_category", "insufficient_evidence_or_clarify"
                )
            ),
        )

    top_score = float(retrieval_signals.get("top_score", 0.0))
    if not topic_matches:
        if top_score < partial_threshold:
            return ScopeDecision(
                decision="out_of_scope",
                reasons=[
                    "No supported registry topic matched and retrieval evidence was below the partial threshold."
                ],
                rule_signals=["no_supported_topic_match"],
                retrieval_signals=retrieval_signals,
                confidence_category="medium",
                registry_version=registry_version,
                escalation_category="insufficient_evidence_or_clarify",
            )
        return ScopeDecision(
            decision="ambiguous",
            reasons=[
                "Retrieval found potentially relevant evidence, but the query did not explicitly match a supported registry topic."
            ],
            rule_signals=["no_supported_topic_match"],
            retrieval_signals=retrieval_signals,
            confidence_category="low",
            registry_version=registry_version,
            escalation_category="insufficient_evidence_or_clarify",
        )

    supporting_topic_matches = [
        (topic, matches)
        for topic, matches in topic_matches
        if set(str(item) for item in topic.get("source_ids", []))
        & set(supporting_sources)
    ]
    primary_topic = max(
        supporting_topic_matches or topic_matches,
        key=lambda item: len(item[1]),
    )[0]
    escalation_category = str(
        primary_topic.get(
            "default_escalation_category", "insufficient_evidence_or_clarify"
        )
    )
    concept_overlap = int(retrieval_signals.get("issue_concept_overlap_count", 0))
    if supporting_sources and top_score >= partial_threshold and concept_overlap > 0:
        confidence_category = (
            "high" if top_score >= grounded_threshold else "medium"
        )
        return ScopeDecision(
            decision="in_scope",
            matched_topics=matched_topics,
            supporting_source_ids=supporting_sources,
            reasons=[
                "The query matched a supported topic and retrieval returned usable evidence from its official source."
            ],
            rule_signals=rule_signals,
            retrieval_signals=retrieval_signals,
            confidence_category=confidence_category,
            registry_version=registry_version,
            escalation_category=escalation_category,
        )

    return ScopeDecision(
        decision="possibly_in_scope",
        matched_topics=matched_topics,
        supporting_source_ids=supporting_sources,
        reasons=[
            "The query matched a supported topic, but retrieved evidence was incomplete, weak, or came from a different official source."
        ],
        rule_signals=rule_signals,
        retrieval_signals=retrieval_signals,
        confidence_category="medium" if supporting_sources else "low",
        registry_version=registry_version,
        escalation_category=escalation_category,
    )


def apply_scope_to_retrieval_status(
    retrieval_status: RetrievalStatus, decision: ScopeDecision
) -> RetrievalStatus:
    if decision.decision == "out_of_scope":
        return "insufficient_evidence"
    if retrieval_status == "insufficient_evidence":
        return retrieval_status
    if decision.decision == "ambiguous":
        return "ambiguous"
    if decision.decision == "possibly_in_scope":
        return "partial_evidence"
    return retrieval_status


def _topic_phrases(topic: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in ("supported_intents", "representative_terms", "common_paraphrases"):
        values.extend(str(item) for item in topic.get(key, []))
    return [_normalize(value) for value in values if value]


def _first_group_phrase_match(
    normalized_question: str, groups: Iterable[dict[str, Any]]
) -> tuple[dict[str, Any], str] | None:
    for group in groups:
        for raw_phrase in group.get("phrases", []):
            phrase = _normalize(str(raw_phrase))
            if _contains_phrase(normalized_question, phrase):
                return group, phrase
    return None


def _topic_adjacent_match(
    normalized_question: str,
    topic_matches: list[tuple[dict[str, Any], list[str]]],
) -> tuple[dict[str, Any], str] | None:
    for topic, _ in topic_matches:
        for raw_phrase in topic.get("unsupported_adjacent_topics", []):
            phrase = _normalize(str(raw_phrase))
            if _contains_phrase(normalized_question, phrase):
                return topic, phrase
    return None


def _retrieval_signals(chunks: list[Any], question: str) -> dict[str, Any]:
    scores = [float(_chunk_value(chunk, "score") or 0.0) for chunk in chunks]
    source_ids = [
        str(_chunk_value(chunk, "source_id") or "")
        for chunk in chunks
        if _chunk_value(chunk, "source_id")
    ]
    unique_sources = sorted(set(source_ids))
    top_score = scores[0] if scores else 0.0
    second_score = scores[1] if len(scores) > 1 else 0.0
    question_terms = _content_terms(question)
    passage_terms = _content_terms(
        " ".join(str(_chunk_value(chunk, "chunk_text") or "") for chunk in chunks)
    )
    concept_overlap = sorted(question_terms & passage_terms)
    return {
        "top_score": round(top_score, 6),
        "top_score_margin": round(top_score - second_score, 6),
        "retrieved_chunk_count": len(chunks),
        "source_ids": unique_sources,
        "evidence_diversity": len(unique_sources),
        "top_source_consistency": (
            round(source_ids.count(source_ids[0]) / len(source_ids), 6)
            if source_ids
            else 0.0
        ),
        "issue_concept_overlap_count": len(concept_overlap),
        "issue_concept_overlap": concept_overlap[:12],
    }


def _chunk_value(chunk: Any, key: str) -> Any:
    if isinstance(chunk, dict):
        return chunk.get(key)
    return getattr(chunk, key, None)


def _contains_phrase(normalized_text: str, normalized_phrase: str) -> bool:
    if not normalized_phrase:
        return False
    text_tokens = normalized_text.split()
    phrase_tokens = normalized_phrase.split()
    if len(phrase_tokens) > len(text_tokens):
        return False
    normalized_phrase_tokens = [_singular(token) for token in phrase_tokens]
    for start in range(len(text_tokens) - len(phrase_tokens) + 1):
        window = text_tokens[start : start + len(phrase_tokens)]
        if [_singular(token) for token in window] == normalized_phrase_tokens:
            return True
    return False


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _singular(token: str) -> str:
    if len(token) > 4 and token.endswith("ies"):
        return f"{token[:-3]}y"
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _content_terms(value: str) -> set[str]:
    stop_words = {
        "about",
        "after",
        "and",
        "are",
        "can",
        "could",
        "does",
        "for",
        "from",
        "have",
        "how",
        "into",
        "should",
        "student",
        "that",
        "the",
        "their",
        "this",
        "what",
        "when",
        "where",
        "will",
        "with",
        "would",
    }
    return {
        _singular(token)
        for token in _normalize(value).split()
        if len(token) >= 3 and token not in stop_words
    }
