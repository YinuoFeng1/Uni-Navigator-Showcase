from app.config import Settings
from app.services.retrieval_service import (
    _expand_retrieval_query,
    _has_lexical_overlap,
    _policy_concept_boost,
    _rerank_expanded_results,
    classify_retrieval_status,
)


def test_lexical_guard_accepts_policy_terms_present_in_passage() -> None:
    assert _has_lexical_overlap(
        "Can I request an assessment extension?",
        "A request for an extension to an assessment due date requires evidence.",
    )


def test_lexical_guard_rejects_out_of_corpus_query() -> None:
    assert not _has_lexical_overlap(
        "Xylophone practice room booking",
        "Students must follow the examination supervisor's directions in the room.",
    )


def test_lexical_guard_rejects_question_with_only_generic_terms() -> None:
    assert not _has_lexical_overlap(
        "What should a student do?",
        "A student should review the procedure.",
    )


def test_study_load_query_expansion_uses_policy_vocabulary() -> None:
    expanded = _expand_retrieval_query(
        "Do I need permission to exceed the normal study load?"
    )

    assert "semester enrolment limits" in expanded
    assert "Associate Dean Academic" in expanded


def test_expanded_query_hybrid_rerank_can_promote_policy_role_passage() -> None:
    query = _expand_retrieval_query("Can I enrol in extra courses this semester?")
    rows = [
        {
            "score": 0.63,
            "chunk_text": "Students enrol in courses during each semester.",
        },
        {
            "score": 0.53,
            "chunk_text": (
                "The Associate Dean Academic approves extending the limit for "
                "enrolment in a semester."
            ),
        },
    ]

    reranked = _rerank_expanded_results(query, rows)

    assert "Associate Dean" in reranked[0]["chunk_text"]


def test_overload_policy_role_receives_concept_boost() -> None:
    query = _expand_retrieval_query(
        "Can I overload to graduate before my visa expires?"
    )
    passage = (
        "The Associate Dean Academic has approval of extending the limit for "
        "enrolment in a semester."
    )

    assert _policy_concept_boost(query, passage) > 0


def test_retrieval_status_respects_partial_and_grounded_thresholds(
    monkeypatch,
) -> None:
    monkeypatch.setenv("RETRIEVAL_PARTIAL_SCORE_THRESHOLD", "0.35")
    monkeypatch.setenv("RETRIEVAL_GROUNDED_SCORE_THRESHOLD", "0.55")
    settings = Settings()

    assert classify_retrieval_status([], settings) == "insufficient_evidence"
    assert (
        classify_retrieval_status(
            [{"score": 0.34}, {"score": 0.33}],
            settings,
        )
        == "insufficient_evidence"
    )
    assert (
        classify_retrieval_status(
            [{"score": 0.54}, {"score": 0.53}, {"score": 0.52}],
            settings,
        )
        == "partial_evidence"
    )
    assert (
        classify_retrieval_status(
            [{"score": 0.55}, {"score": 0.40}],
            settings,
        )
        == "grounded"
    )
