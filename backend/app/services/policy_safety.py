from dataclasses import dataclass


HIGH_STAKES_KEYWORDS: dict[str, tuple[str, ...]] = {
    "visa": (
        "visa",
        "international student",
        "overseas student",
        "confirmation of enrolment",
        "coe",
        "cricos",
        "student visa",
    ),
    "enrolment": ("enrolment overload", "overload", "study load", "withdrawal"),
    "progression": (
        "academic progression",
        "progression notice",
        "progression intervention",
        "intervention notice",
        "progression improvement plan",
        "show cause",
        "exclusion",
    ),
    "fees": ("fee", "fees", "refund", "remission", "financial"),
    "appeal": ("appeal", "review", "complaint", "challenge a decision"),
    "special_consideration": (
        "special consideration",
        "special circumstance",
        "special circumstances",
        "illness",
        "medical",
        "missed exam",
    ),
    "deadline": ("deadline", "census date", "late", "academic penalty"),
    "extension": ("extension", "assessment extension"),
    "personal_eligibility": (
        "my eligibility",
        "am i eligible",
        "can i apply",
        "personal circumstance",
        "personal circumstances",
    ),
    "failed_course": ("failed course", "fail a course", "failed a course"),
    "graduation": ("graduation", "graduate", "completion"),
}


@dataclass(frozen=True)
class PolicySafetyAssessment:
    high_stakes_detected: bool
    categories: list[str]


def assess_policy_safety(question: str) -> PolicySafetyAssessment:
    normalized = question.lower()
    categories = [
        category
        for category, keywords in HIGH_STAKES_KEYWORDS.items()
        if any(keyword in normalized for keyword in keywords)
    ]
    return PolicySafetyAssessment(
        high_stakes_detected=bool(categories),
        categories=categories,
    )
