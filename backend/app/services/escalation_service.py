from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class EscalationDecision:
    recommended: bool
    category: str
    reasons: list[str] = field(default_factory=list)
    requires_individual_assessment: bool = False


PERSONAL_DECISION_PATTERNS: tuple[tuple[str, str], ...] = (
    (
        "personal_eligibility_or_permission",
        r"\b(?:am i eligible|can i "
        r"(?:apply|sit|defer|drop|withdraw|take|enrol|enroll|get|appeal|"
        r"remove|overload|request))\b",
    ),
    (
        "personal_approval_requirement",
        r"\bdo i need\b.{0,60}\b"
        r"(?:permission|approval|evidence|document|form|submit)\b",
    ),
    (
        "personal_outcome",
        r"\b(?:will|would)\b.{0,80}\bmy\b|\bwhat happens to my\b|\bwhat if my\b",
    ),
    (
        "existing_personal_case",
        r"\bi (?:have )?(?:failed|received)\b",
    ),
    (
        "personal_response_or_review",
        r"\bhow should i\b|\bwhat should i do before\b|"
        r"\bhow long do i have to "
        r"(?:appeal|challenge|seek a review|request a review)\b|"
        r"\bask for\b.{0,60}\bdecision\b.{0,40}\breviewed\b",
    ),
    (
        "special_circumstances_assessment",
        r"\bcan special circumstances help\b",
    ),
)


def _personal_decision_signals(question: str) -> list[str]:
    normalized = " ".join(question.lower().split())
    return [
        category
        for category, pattern in PERSONAL_DECISION_PATTERNS
        if re.search(pattern, normalized)
    ]


def _contact_category(
    scope_category: Any | None,
    safety_categories: list[str] | None,
) -> str:
    categories = set(safety_categories or [])
    if {"visa", "international_student"} & categories:
        return "international_student_or_visa_support"
    if scope_category and scope_category != "out_of_domain_no_university_escalation":
        return str(scope_category)
    return "authorised_university_staff"


def decide_escalation_category(
    *,
    question: str = "",
    retrieval_status: str,
    scope_decision: Any | None,
    high_stakes_detected: bool,
    safety_categories: list[str] | None = None,
) -> EscalationDecision:
    scope_category = getattr(scope_decision, "escalation_category", None)
    scope_status = getattr(scope_decision, "decision", None)
    contact_category = _contact_category(scope_category, safety_categories)

    if (
        scope_status == "out_of_scope"
        and scope_category == "out_of_domain_no_university_escalation"
    ):
        return EscalationDecision(
            recommended=False,
            category="out_of_domain_no_university_escalation",
            reasons=[
                "The question is outside the university administrative domain."
            ],
        )

    if retrieval_status == "insufficient_evidence":
        return EscalationDecision(
            recommended=True,
            category=contact_category,
            reasons=[
                "The retrieved official evidence is insufficient for a safe answer."
            ],
        )

    if retrieval_status == "ambiguous" or scope_status in {
        "ambiguous",
        "possibly_in_scope",
    }:
        return EscalationDecision(
            recommended=True,
            category=contact_category,
            reasons=["The question or retrieved evidence leaves an unresolved issue."],
        )

    categories = set(safety_categories or [])
    if {"visa", "international_student"} & categories:
        return EscalationDecision(
            recommended=True,
            category="international_student_or_visa_support",
            reasons=[
                "Visa and international student outcomes require authorised advice."
            ],
            requires_individual_assessment=True,
        )

    if retrieval_status == "individual_assessment":
        return EscalationDecision(
            recommended=True,
            category=contact_category,
            reasons=[
                "The policy is available, but the personal outcome requires confirmation."
            ],
            requires_individual_assessment=True,
        )

    personal_signals = _personal_decision_signals(question)
    if personal_signals:
        return EscalationDecision(
            recommended=True,
            category=contact_category,
            reasons=[
                "The question asks for a personal eligibility, approval, or case outcome.",
                *[f"decision_signal:{signal}" for signal in personal_signals],
            ],
            requires_individual_assessment=True,
        )

    return EscalationDecision(
        recommended=False,
        category="none",
        reasons=[
            "The answer concerns a grounded general rule, step, or deadline."
        ],
    )


def escalation_guidance(decision: EscalationDecision) -> str | None:
    if not decision.recommended:
        return None
    if decision.category == "international_student_or_visa_support":
        return "Contact authorised UQ international student support before acting."
    if decision.requires_individual_assessment:
        return (
            "Contact authorised university staff to confirm how the policy applies "
            "to your case."
        )
    return (
        "Contact the appropriate authorised university staff for clarification "
        "before acting."
    )
