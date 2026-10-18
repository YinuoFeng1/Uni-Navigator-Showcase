"""Session attribution and retry receipts for the single-presentation Chat study."""

import hashlib
import json

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.models import InteractionLog, StudyEventLog, StudySession
from app.utils.time import utc_now


def session_metadata(study_session: StudySession) -> dict:
    return json.loads(study_session.metadata_json or "{}")


def is_chat_session(study_session: StudySession | None) -> bool:
    return bool(study_session and session_metadata(study_session).get("workflow") == "chat")


def bind_write(session: Session, request) -> StudySession | None:
    """Derive identity from the server; never trust a submitted participant label."""
    interaction_id = getattr(request, "interactionId", None)
    interaction = session.get(InteractionLog, interaction_id) if interaction_id else None
    session_id = request.sessionId
    if interaction and interaction.session_id:
        if session_id != interaction.session_id:
            raise HTTPException(409, "Interaction belongs to another session")
    study_session = session.get(StudySession, session_id) if session_id else None
    if session_id and not study_session:
        raise HTTPException(404, "Study session not found")
    if not is_chat_session(study_session):
        return study_session
    if study_session.completed_at or study_session.state != "active":
        raise HTTPException(409, "Session has ended")
    if interaction_id and (not interaction or interaction.session_id != session_id):
        # A failed provenance commit may leave neither an interaction nor an event.
        # Allow recording that failure later, but never attach another session's ID.
        failure = session.exec(select(StudyEventLog).where(
            StudyEventLog.interaction_id == interaction_id,
        )).first()
        if getattr(request, "eventType", None) != "system_failure" or (
            failure and failure.session_id != session_id
        ):
            raise HTTPException(409, "Interaction does not belong to this session")
    if getattr(request, "answerId", None) and (
        not interaction or request.answerId != interaction.answer_id
    ):
        raise HTTPException(409, "Answer does not belong to this interaction")
    if getattr(request, "evidenceAction", None):
        if not interaction:
            raise HTTPException(409, "Evidence requires an interaction")
        citations = json.loads(interaction.citations_json or "[]")
        if not any(
            request.citationId in {c.get("id"), c.get("citationId")}
            and request.sourceId == c.get("sourceId")
            and request.chunkId == c.get("chunkId") for c in citations
        ):
            raise HTTPException(409, "Evidence does not belong to this answer")
    request.participantLabel = study_session.participant_label
    if hasattr(request, "participantId"):
        request.participantId = study_session.participant_label
    if hasattr(request, "condition"):
        request.condition = study_session.study_condition
    request.taskId = None
    return study_session


def request_hash(request) -> str:
    data = request.model_dump(exclude={"participantLabel", "participantId", "condition", "taskId"})
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()


def retry_result(session: Session, request) -> dict | None:
    if not request.requestId:
        return None
    event = session.get(StudyEventLog, f"event_write_{request.requestId}")
    if not event:
        return None
    receipt = json.loads(event.payload_json or "{}")
    if receipt.get("requestHash") != request_hash(request):
        raise HTTPException(409, "Retry identifier was already used for another write")
    return receipt["response"]


def commit_write(session: Session, request, event: StudyEventLog, response: dict) -> dict:
    event.occurred_at = event.created_at
    event.recorded_at = utc_now()
    if request.requestId:
        event.id = f"event_write_{request.requestId}"
        event.idempotency_key = request.requestId
        event.payload_json = json.dumps({"requestHash": request_hash(request), "response": response})
    session.add(event)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = retry_result(session, request)
        if existing is None:
            raise
        return existing
    return response
