from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from sqlmodel import Session, select

from app.models import StudyEventLog
from app.utils.ids import make_id
from app.utils.time import utc_now


EVENT_SCHEMA_VERSION = "1.0"
FAILURE_REPRODUCIBILITY_FIELDS = {
    "response_time_ms",
    "retrieval_status",
    "retrieval_trace",
    "provider_response_id",
    "provider_response_model",
    "token_usage",
    "runtime_config",
}

EVENT_PAYLOAD_ALLOWLISTS: dict[str, set[str]] = {
    "release_not_frozen": {
        "error_code",
        "release_status",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
    "invalid_state_transition": {
        "error_code",
        "transition",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
    "client_context_mismatch": {
        "error_code",
        "context_field",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
    "system_failure": {
        "error_code",
        "failure_stage",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
    "interaction_served": {
        "answer_mode",
        "citation_count",
        "retrieval_status",
        "escalation_recommended",
        "escalation_category",
        "escalation_reasons",
    },
    "provider_unavailable": {
        "error_code",
        "failure_stage",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
    "vector_store_unavailable": {
        "error_code",
        "failure_stage",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
    "corpus_mismatch": {
        "error_code",
        "failure_stage",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
    "scope_out_of_corpus": {
        "error_code",
        "task_id",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
    "scope_ambiguous": {
        "error_code",
        "task_id",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
    "retrieval_insufficient": {
        "error_code",
        "task_id",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
    "release_retired": {
        "error_code",
        "release_status",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
    "release_component_mismatch": {
        "error_code",
        "context_field",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
    "provenance_write_failed": {
        "error_code",
        "failure_stage",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
    "participant_input_invalid": {
        "error_code",
        "context_field",
        "researcher_action",
    }
    | FAILURE_REPRODUCIBILITY_FIELDS,
}

FORBIDDEN_PAYLOAD_KEYS = {
    "question",
    "participant_question",
    "final_decision",
    "final_decision_text",
    "api_key",
    "provider_response",
    "provider_error_body",
}


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    event_type: str
    schema_version: str
    occurred_at: Any
    recorded_at: Any
    session_id: str | None
    task_id: str | None
    interaction_id: str | None
    release_id: str | None
    condition_id: str | None
    app_revision: str | None
    runtime_config_fingerprint: str | None
    idempotency_key: str | None
    payload: dict[str, Any]


class EventRepository:
    """Append-only adapter for new pilot-critical events."""

    def append(
        self,
        session: Session,
        *,
        event_type: str,
        payload: Mapping[str, Any],
        session_id: str | None = None,
        participant_label: str | None = None,
        task_id: str | None = None,
        interaction_id: str | None = None,
        release_id: str | None = None,
        condition_id: str | None = None,
        app_revision: str | None = None,
        runtime_config_fingerprint: str | None = None,
        idempotency_key: str | None = None,
        occurred_at: Any | None = None,
    ) -> EventEnvelope:
        if idempotency_key:
            existing = session.exec(
                select(StudyEventLog).where(
                    StudyEventLog.idempotency_key == idempotency_key
                )
            ).first()
            if existing:
                return self._envelope(existing)

        safe_payload = self._validate_payload(event_type, payload)
        occurred = occurred_at or utc_now()
        recorded = utc_now()
        event = StudyEventLog(
            id=make_id("event"),
            session_id=session_id,
            participant_label=participant_label,
            participant_id=participant_label,
            task_id=task_id,
            interaction_id=interaction_id,
            condition=condition_id,
            condition_id=condition_id,
            event_type=event_type,
            metadata_json=json.dumps(safe_payload, ensure_ascii=True, sort_keys=True),
            payload_json=json.dumps(safe_payload, ensure_ascii=True, sort_keys=True),
            created_at=occurred,
            occurred_at=occurred,
            recorded_at=recorded,
            schema_version=EVENT_SCHEMA_VERSION,
            release_id=release_id,
            app_revision=app_revision,
            runtime_config_fingerprint=runtime_config_fingerprint,
            idempotency_key=idempotency_key,
        )
        session.add(event)
        session.flush()
        return self._envelope(event)

    @staticmethod
    def _validate_payload(
        event_type: str, payload: Mapping[str, Any]
    ) -> dict[str, Any]:
        keys = set(payload)
        if keys & FORBIDDEN_PAYLOAD_KEYS:
            raise ValueError("event payload contains prohibited sensitive fields")
        allowed = EVENT_PAYLOAD_ALLOWLISTS.get(event_type)
        if allowed is None:
            raise ValueError(f"event type {event_type!r} has no payload schema")
        unknown = keys - allowed
        if unknown:
            raise ValueError(
                f"event payload contains unsupported fields: {', '.join(sorted(unknown))}"
            )
        return dict(payload)

    @staticmethod
    def _envelope(event: StudyEventLog) -> EventEnvelope:
        payload = json.loads(event.payload_json or event.metadata_json or "{}")
        return EventEnvelope(
            event_id=event.id,
            event_type=event.event_type,
            schema_version=event.schema_version or EVENT_SCHEMA_VERSION,
            occurred_at=event.occurred_at or event.created_at,
            recorded_at=event.recorded_at or event.created_at,
            session_id=event.session_id,
            task_id=event.task_id,
            interaction_id=event.interaction_id,
            release_id=event.release_id,
            condition_id=event.condition_id or event.condition,
            app_revision=event.app_revision,
            runtime_config_fingerprint=event.runtime_config_fingerprint,
            idempotency_key=event.idempotency_key,
            payload=payload,
        )
