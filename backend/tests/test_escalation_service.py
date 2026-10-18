from types import SimpleNamespace

import pytest

from app.services.escalation_service import (
    decide_escalation_category,
    escalation_guidance,
)
from app.services.policy_safety import assess_policy_safety


def _scope(
    decision: str = "in_scope",
    category: str = "contact_faculty_or_student_centre",
):
    return SimpleNamespace(decision=decision, escalation_category=category)


@pytest.mark.parametrize(
    "question",
    [
        "What evidence is needed for an assessment extension?",
        "What is the deadline to request a deferred exam?",
        "How do students request a course overload?",
        "Are fees refundable before or after the census date?",
        "What parts of the refund process are described in the available policy?",
    ],
)
def test_grounded_general_rules_do_not_escalate(question: str) -> None:
    safety = assess_policy_safety(question)

    decision = decide_escalation_category(
        question=question,
        retrieval_status=(
            "partial_evidence" if question.startswith("What parts") else "grounded"
        ),
        scope_decision=_scope(),
        high_stakes_detected=safety.high_stakes_detected,
        safety_categories=safety.categories,
    )

    assert safety.high_stakes_detected is True
    assert decision.recommended is False
    assert decision.category == "none"
    assert escalation_guidance(decision) is None


@pytest.mark.parametrize(
    ("question", "status", "scope", "expected_category"),
    [
        (
            "Can I get a refund after withdrawing from a course?",
            "grounded",
            _scope(),
            "contact_faculty_or_student_centre",
        ),
        (
            "Will withdrawing affect my student visa?",
            "grounded",
            _scope(),
            "international_student_or_visa_support",
        ),
        (
            "The question mixes two unresolved policy issues.",
            "ambiguous",
            _scope(decision="ambiguous"),
            "contact_faculty_or_student_centre",
        ),
        (
            "How do I book a university music practice room?",
            "insufficient_evidence",
            _scope(
                decision="out_of_scope",
                category="contact_faculty_or_student_centre",
            ),
            "contact_faculty_or_student_centre",
        ),
    ],
)
def test_personal_visa_ambiguous_and_insufficient_questions_escalate(
    question: str,
    status: str,
    scope,
    expected_category: str,
) -> None:
    safety = assess_policy_safety(question)

    decision = decide_escalation_category(
        question=question,
        retrieval_status=status,
        scope_decision=scope,
        high_stakes_detected=safety.high_stakes_detected,
        safety_categories=safety.categories,
    )

    assert decision.recommended is True
    assert decision.category == expected_category
    assert decision.reasons
    assert escalation_guidance(decision)


def test_non_university_out_of_domain_question_does_not_escalate_to_uq_staff() -> None:
    question = "What is the weather forecast for Brisbane tomorrow?"
    safety = assess_policy_safety(question)

    decision = decide_escalation_category(
        question=question,
        retrieval_status="insufficient_evidence",
        scope_decision=_scope(
            decision="out_of_scope",
            category="out_of_domain_no_university_escalation",
        ),
        high_stakes_detected=safety.high_stakes_detected,
        safety_categories=safety.categories,
    )

    assert decision.recommended is False
    assert decision.category == "out_of_domain_no_university_escalation"
    assert escalation_guidance(decision) is None
