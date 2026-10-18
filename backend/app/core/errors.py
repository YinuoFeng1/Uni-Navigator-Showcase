from __future__ import annotations

from dataclasses import dataclass
from typing import Any


PARTICIPANT_PAUSE_MESSAGE = (
    "The study system is temporarily unavailable. Please pause this task and "
    "notify the researcher."
)


@dataclass(frozen=True)
class ErrorDefinition:
    code: str
    category: str
    http_status: int
    participant_message: str
    retryable: bool
    task_blocked: bool
    event_type: str


ERRORS: dict[str, ErrorDefinition] = {
    code: ErrorDefinition(
        code=code,
        category=category,
        http_status=status,
        participant_message=message,
        retryable=retryable,
        task_blocked=blocked,
        event_type=event_type,
    )
    for code, category, status, message, retryable, blocked, event_type in [
        ("configuration_error", "configuration_error", 503, PARTICIPANT_PAUSE_MESSAGE, False, True, "system_failure"),
        ("provider_unavailable", "provider_unavailable", 503, PARTICIPANT_PAUSE_MESSAGE, True, True, "system_failure"),
        ("citation_validation_failed", "citation_validation_failed", 503, PARTICIPANT_PAUSE_MESSAGE, True, True, "system_failure"),
        ("vector_store_unavailable", "vector_store_unavailable", 503, PARTICIPANT_PAUSE_MESSAGE, True, True, "system_failure"),
        ("corpus_mismatch", "corpus_mismatch", 503, PARTICIPANT_PAUSE_MESSAGE, False, True, "system_failure"),
        ("scope_out_of_corpus", "scope_out_of_corpus", 409, PARTICIPANT_PAUSE_MESSAGE, False, True, "scope_out_of_corpus"),
        ("scope_ambiguous", "scope_ambiguous", 409, PARTICIPANT_PAUSE_MESSAGE, False, True, "scope_ambiguous"),
        ("retrieval_insufficient", "retrieval_insufficient", 409, PARTICIPANT_PAUSE_MESSAGE, False, True, "retrieval_insufficient"),
        ("release_not_frozen", "release_not_frozen", 409, PARTICIPANT_PAUSE_MESSAGE, False, True, "release_not_frozen"),
        ("release_retired", "release_retired", 409, PARTICIPANT_PAUSE_MESSAGE, False, True, "release_retired"),
        ("release_component_mismatch", "release_component_mismatch", 409, PARTICIPANT_PAUSE_MESSAGE, False, True, "release_component_mismatch"),
        ("invalid_state_transition", "invalid_state_transition", 409, PARTICIPANT_PAUSE_MESSAGE, False, True, "invalid_state_transition"),
        ("client_context_mismatch", "client_context_mismatch", 409, PARTICIPANT_PAUSE_MESSAGE, False, True, "client_context_mismatch"),
        ("provenance_write_failed", "provenance_write_failed", 503, PARTICIPANT_PAUSE_MESSAGE, True, True, "provenance_write_failed"),
        ("participant_input_invalid", "participant_input_invalid", 422, "The request could not be accepted. Please ask the researcher for help.", False, False, "participant_input_invalid"),
        ("system_failure", "system_failure", 503, PARTICIPANT_PAUSE_MESSAGE, True, True, "system_failure"),
    ]
}


class ApplicationError(RuntimeError):
    def __init__(
        self,
        code: str,
        *,
        researcher_safe_detail: str = "",
        correlation_id: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> None:
        if code not in ERRORS:
            raise ValueError(f"Unknown application error code: {code}")
        self.definition = ERRORS[code]
        self.researcher_safe_detail = researcher_safe_detail
        self.correlation_id = correlation_id
        self.context = dict(context or {})
        super().__init__(self.definition.participant_message)

    @property
    def code(self) -> str:
        return self.definition.code

    def safe_payload(self) -> dict[str, Any]:
        return {
            "message": self.definition.participant_message,
            "errorCode": self.definition.code,
            "errorCategory": self.definition.category,
            "retryable": self.definition.retryable,
            "taskBlocked": self.definition.task_blocked,
            "correlationId": self.correlation_id,
        }
