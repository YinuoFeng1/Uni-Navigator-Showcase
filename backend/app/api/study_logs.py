import json
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select
from sqlalchemy.exc import IntegrityError

from app.database import DB_PATH, get_session
from app.config import get_settings
from app.models import (
    EvidenceUse,
    FeedbackLog,
    FinalTaskResponse,
    StudyEventLog,
    StudySession,
    InteractionLog,
    TrustChecklistSnapshot,
)
from app.schemas import (
    EvidenceUseRequest,
    EvidenceUseResponse,
    FeedbackRequest,
    FeedbackResponse,
    FinalTaskResponseRequest,
    FinalTaskResponseResponse,
    StudySessionCompleteRequest,
    StudySessionResponse,
    StudySessionStartRequest,
    StudySessionTaskRequest,
    StudySessionTaskResponse,
    StudyEventRequest,
    StudyEventResponse,
    StudyTaskResponse,
    StudyTasksResponse,
    TrustChecklistSnapshotRequest,
    TrustChecklistSnapshotResponse,
)
from app.services.study_tasks import active_study_tasks, get_study_task
from app.core.errors import ApplicationError, PARTICIPANT_PAUSE_MESSAGE
from app.domain.lifecycle import StudySessionState, guard_session_activation
from app.services.pilot_preflight_service import run_pilot_preflight
from app.utils.ids import make_id
from app.utils.time import parse_iso_timestamp, to_iso, utc_now
from app.services.chat_session_service import (
    bind_write, commit_write, is_chat_session, retry_result, session_metadata,
)

router = APIRouter()
PILOT_UNAVAILABLE_MESSAGE = PARTICIPANT_PAUSE_MESSAGE


def _json_or_none(value: dict | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def _iso_or_none(value) -> str | None:
    return to_iso(value) if value is not None else None


def _task_response(task: dict) -> StudyTaskResponse:
    return StudyTaskResponse(
        taskId=str(task.get("task_id")),
        title=str(task.get("title") or ""),
        scenario=str(task.get("scenario") or ""),
        taskType=str(task.get("task_type") or ""),
        difficulty=str(task.get("difficulty") or ""),
        expectedSafeBehaviour=str(task.get("expected_safe_behaviour") or ""),
        escalationExpected=bool(task.get("escalation_expected")),
        active=bool(task.get("active")),
        notesForResearcher=task.get("notes_for_researcher"),
    )


def _session_response(
    study_session: StudySession,
    session: Session,
) -> StudySessionResponse:
    task_events = session.exec(
        select(StudyEventLog).where(StudyEventLog.session_id == study_session.session_id)
    ).all()
    completed_task_ids = {
        event.task_id
        for event in task_events
        if event.event_type == "task_completed" and event.task_id
    }
    started_task_ids = {
        event.task_id
        for event in task_events
        if event.event_type == "task_started" and event.task_id
    }
    return StudySessionResponse(
        roundId=session_metadata(study_session).get("roundId"),
        executionContext=session_metadata(study_session).get("executionContext"),
        sessionId=study_session.session_id,
        participantLabel=study_session.participant_label,
        studyCondition=study_session.study_condition,
        startedAt=to_iso(study_session.started_at),
        completedAt=_iso_or_none(study_session.completed_at),
        currentTaskId=study_session.current_task_id,
        prototypeNoticeAcknowledged=study_session.prototype_notice_acknowledged,
        prototypeNoticeAcknowledgedAt=_iso_or_none(
            study_session.prototype_notice_acknowledged_at
        ),
        state=study_session.state,
        releaseId=study_session.release_id,
        releaseVersion=study_session.release_version,
        conditionVersion=study_session.condition_version,
        taskProgress={
            "startedTaskIds": sorted(started_task_ids),
            "completedTaskIds": sorted(completed_task_ids),
            "eventCount": len(task_events),
        },
    )


def _log_session_event(
    session: Session,
    study_session: StudySession,
    task_id: str,
    event_type: str,
    metadata: dict | None = None,
) -> str:
    event_id = make_id("event")
    event = StudyEventLog(
        id=event_id,
        session_id=study_session.session_id,
        participant_label=study_session.participant_label,
        participant_id=study_session.participant_label,
        task_id=task_id,
        condition=study_session.study_condition,
        event_type=event_type,
        metadata_json=_json_or_none(metadata),
        created_at=utc_now(),
    )
    session.add(event)
    return event_id


def _study_session_or_none(
    session: Session,
    session_id: str | None,
) -> StudySession | None:
    if not session_id:
        return None
    study_session = session.get(StudySession, session_id)
    if not study_session:
        raise HTTPException(status_code=404, detail="Study session not found")
    return study_session


def _add_study_event(
    session: Session,
    *,
    session_id: str | None,
    participant_label: str | None,
    participant_id: str | None = None,
    interaction_id: str | None = None,
    task_id: str | None = None,
    condition: str | None = None,
    event_type: str,
    metadata: dict | None = None,
    created_at=None,
) -> str:
    event_id = make_id("event")
    event = StudyEventLog(
        id=event_id,
        session_id=session_id,
        participant_label=participant_label,
        participant_id=participant_id,
        interaction_id=interaction_id,
        task_id=task_id,
        condition=condition,
        event_type=event_type,
        metadata_json=_json_or_none(metadata),
        created_at=created_at or utc_now(),
    )
    session.add(event)
    return event_id


def _event_type_for_evidence_action(evidence_action: str) -> str:
    event_type_by_action = {
        "evidence_panel_opened": "evidence_opened",
        "citation_clicked": "citation_clicked",
        "source_checked": "source_checked",
        "passage_viewed": "passage_viewed",
        "evidence_rating_submitted": "evidence_rating_submitted",
        "source_marked_helpful": "source_marked_helpful",
        "source_marked_confusing": "source_marked_confusing",
    }
    return event_type_by_action.get(evidence_action, evidence_action)


def _is_pilot_session(study_session: StudySession | None) -> bool:
    if _is_formal_participant_runtime(get_settings()):
        return True
    return bool(study_session and study_session.release_id)


def _assert_no_failed_task_interaction(
    session: Session,
    study_session: StudySession | None,
    *,
    task_id: str | None,
    interaction_id: str | None = None,
) -> None:
    if not study_session:
        return
    events = session.exec(
        select(StudyEventLog).where(
            StudyEventLog.session_id == study_session.session_id
        )
    ).all()
    pilot_session = _is_pilot_session(study_session)
    blocking_event_types = {
        "system_failure",
        "release_not_frozen",
        "release_retired",
        "release_component_mismatch",
        "invalid_state_transition",
        "client_context_mismatch",
        "provenance_write_failed",
    }
    matching_failures = [
        event
        for event in events
        if event.event_type in blocking_event_types
        and (not task_id or event.task_id == task_id)
        and (
            pilot_session
            or not interaction_id
            or event.interaction_id == interaction_id
        )
    ]
    if not matching_failures:
        return
    if not pilot_session and not interaction_id:
        return
    latest_start = max(
        (
            event.created_at
            for event in events
            if event.event_type == "task_started" and event.task_id == task_id
        ),
        default=None,
    )
    failed_current_run = any(
        latest_start is None or event.created_at >= latest_start
        for event in matching_failures
    )
    if failed_current_run:
        raise HTTPException(
            status_code=409,
            detail={
                "message": PILOT_UNAVAILABLE_MESSAGE,
                "reason": "failed_interaction_requires_researcher_review",
            },
        )


@router.post("/session/start", response_model=StudySessionResponse)
def start_study_session(
    request: StudySessionStartRequest,
    http_request: Request,
    session: Session = Depends(get_session),
) -> StudySessionResponse:
    participant_label = request.participantLabel.strip()
    if not participant_label:
        raise HTTPException(status_code=422, detail="participantLabel is required")

    if request.roundId:
        if not re.fullmatch(r"P[0-9]{2,6}", participant_label):
            raise HTTPException(422, "Use a participant code such as P01, not a name")
        if not request.sessionId or request.prototypeNoticeAcknowledged is not True:
            raise HTTPException(422, "Session identifier and consent confirmation are required")
        existing = session.get(StudySession, request.sessionId)
        if existing:
            if not is_chat_session(existing) or (
                existing.participant_label != participant_label
                or session_metadata(existing).get("roundId") != request.roundId
            ):
                raise HTTPException(409, "Session identifier already used")
            return _session_response(existing, session)
        request.studyCondition = "C_HIGHLIGHT"

    settings = get_settings()
    formal_participant = _is_formal_participant_runtime(settings)
    release = None
    condition_version = None
    container = getattr(http_request.app.state, "container", None)
    runtime_fingerprint = (
        container.runtime.runtime_config_fingerprint if container else None
    )
    if request.roundId:
        if container is None:
            raise HTTPException(503, "Chat system is unavailable; do not start the test")
        for previous_session in session.exec(select(StudySession)).all():
            if is_chat_session(previous_session) and session_metadata(previous_session).get("roundId") == request.roundId:
                if previous_session.runtime_config_fingerprint != runtime_fingerprint:
                    raise HTTPException(409, "Configuration changed. Use a new test round")
    if formal_participant:
        container = _container_or_error(http_request)
        report = run_pilot_preflight(
            settings,
            vector_store=container.providers.vector_store,
            database_path=DB_PATH,
            session_labels=[],
            condition_service=container.conditions,
            release_service=container.releases,
        )
        release_check = next(
            (item for item in report.checks if item.check_id == "release_frozen"),
            None,
        )
        guard_session_activation(
            notice_acknowledged=request.prototypeNoticeAcknowledged is True,
            release_frozen=bool(release_check and release_check.status == "PASS"),
            preflight_ok=report.ok,
        )
        release = container.releases.resolve_active_release(require_frozen=True)
        condition = container.conditions.get_condition(request.studyCondition or "")
        if condition.get("active") is not True:
            raise _application_http_error(
                ApplicationError(
                    "client_context_mismatch",
                    researcher_safe_detail="selected study condition is inactive",
                )
            )
        condition_version = str(condition.get("condition_version") or "")
        runtime_fingerprint = container.runtime.runtime_config_fingerprint

    study_session = StudySession(
        session_id=request.sessionId if request.roundId else make_id("session"),
        participant_label=participant_label,
        study_condition=request.studyCondition,
        metadata_json=_json_or_none({
            "workflow": "chat", "roundId": request.roundId,
            "executionContext": settings.execution_context,
        } if request.roundId else request.metadata),
        prototype_notice_acknowledged=request.prototypeNoticeAcknowledged,
        prototype_notice_acknowledged_at=(
            utc_now() if request.prototypeNoticeAcknowledged else None
        ),
        state=StudySessionState.ACTIVE.value,
        release_id=release.get("release_id") if release else None,
        release_version=release.get("release_version") if release else None,
        condition_version=condition_version,
        runtime_config_fingerprint=runtime_fingerprint,
        app_revision=settings.app_revision,
    )
    session.add(study_session)
    if request.roundId:
        _add_study_event(
            session, session_id=study_session.session_id,
            participant_label=participant_label, event_type="session_started",
            metadata={"roundId": request.roundId},
        )
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.get(StudySession, request.sessionId) if request.roundId else None
        if not existing or existing.participant_label != participant_label or session_metadata(existing).get("roundId") != request.roundId:
            raise
        return _session_response(existing, session)
    session.refresh(study_session)
    return _session_response(study_session, session)


@router.post("/session/complete", response_model=StudySessionResponse)
def complete_study_session(
    request: StudySessionCompleteRequest,
    session: Session = Depends(get_session),
) -> StudySessionResponse:
    study_session = session.get(StudySession, request.sessionId)
    if not study_session:
        raise HTTPException(status_code=404, detail="Study session not found")

    if study_session.completed_at:
        return _session_response(study_session, session)
    if is_chat_session(study_session):
        _add_study_event(
            session, session_id=study_session.session_id,
            participant_label=study_session.participant_label, event_type="session_completed",
        )
    study_session.completed_at = utc_now()
    study_session.current_task_id = None
    study_session.state = StudySessionState.COMPLETED.value
    session.add(study_session)
    session.commit()
    session.refresh(study_session)
    return _session_response(study_session, session)


@router.get("/session/{session_id}", response_model=StudySessionResponse)
def get_study_session(
    session_id: str,
    session: Session = Depends(get_session),
) -> StudySessionResponse:
    study_session = session.get(StudySession, session_id)
    if not study_session:
        raise HTTPException(status_code=404, detail="Study session not found")
    return _session_response(study_session, session)


@router.get("/tasks", response_model=StudyTasksResponse)
def list_study_tasks() -> StudyTasksResponse:
    return StudyTasksResponse(items=[_task_response(task) for task in active_study_tasks()])


@router.get("/tasks/{task_id}", response_model=StudyTaskResponse)
def get_task(task_id: str) -> StudyTaskResponse:
    task = get_study_task(task_id)
    if not task or task.get("active") is not True:
        raise HTTPException(status_code=404, detail="Study task not found")
    return _task_response(task)


@router.post("/session/task/start", response_model=StudySessionTaskResponse)
def start_session_task(
    request: StudySessionTaskRequest,
    http_request: Request,
    session: Session = Depends(get_session),
) -> StudySessionTaskResponse:
    study_session = session.get(StudySession, request.sessionId)
    if not study_session:
        raise HTTPException(status_code=404, detail="Study session not found")
    task = get_study_task(request.taskId)
    if not task or task.get("active") is not True:
        raise HTTPException(status_code=404, detail="Study task not found")
    if study_session.completed_at or study_session.state in {"completed", "aborted"}:
        raise _application_http_error(
            ApplicationError(
                "invalid_state_transition",
                researcher_safe_detail="completed or aborted session cannot start a task",
            )
        )
    if (
        study_session.current_task_id
        and study_session.current_task_id != request.taskId
    ):
        raise _application_http_error(
            ApplicationError(
                "invalid_state_transition",
                researcher_safe_detail="another task is already active",
            )
        )
    if _is_formal_participant_runtime(get_settings()):
        if study_session.state != StudySessionState.ACTIVE.value:
            raise _application_http_error(
                ApplicationError(
                    "invalid_state_transition",
                    researcher_safe_detail="formal task requires an active session",
                )
            )
        container = _container_or_error(http_request)
        container.conditions.package_binding(
            study_session.study_condition or "", request.taskId
        )

    study_session.current_task_id = request.taskId
    session.add(study_session)
    event_id = _log_session_event(
        session,
        study_session,
        request.taskId,
        "task_started",
        {
            "taskTitle": task.get("title"),
            "preConfidence": request.preConfidence,
        },
    )
    session.commit()
    return StudySessionTaskResponse(
        sessionId=study_session.session_id,
        taskId=request.taskId,
        status="started",
        eventId=event_id,
        currentTaskId=study_session.current_task_id,
    )


@router.post("/session/task/complete", response_model=StudySessionTaskResponse)
def complete_session_task(
    request: StudySessionTaskRequest,
    session: Session = Depends(get_session),
) -> StudySessionTaskResponse:
    study_session = session.get(StudySession, request.sessionId)
    if not study_session:
        raise HTTPException(status_code=404, detail="Study session not found")
    task = get_study_task(request.taskId)
    if not task:
        raise HTTPException(status_code=404, detail="Study task not found")
    _assert_no_failed_task_interaction(
        session, study_session, task_id=request.taskId
    )

    existing_completion = session.exec(
        select(StudyEventLog).where(
            StudyEventLog.session_id == request.sessionId,
            StudyEventLog.task_id == request.taskId,
            StudyEventLog.event_type == "task_completed",
        )
    ).first()
    if existing_completion:
        return StudySessionTaskResponse(
            sessionId=study_session.session_id,
            taskId=request.taskId,
            status="completed",
            eventId=existing_completion.id,
            currentTaskId=study_session.current_task_id,
        )
    if _is_formal_participant_runtime(get_settings()):
        final_response = session.exec(
            select(FinalTaskResponse).where(
                FinalTaskResponse.session_id == request.sessionId,
                FinalTaskResponse.task_id == request.taskId,
            )
        ).first()
        if not final_response:
            raise _application_http_error(
                ApplicationError(
                    "invalid_state_transition",
                    researcher_safe_detail="final response is required before completion",
                )
            )

    if study_session.current_task_id == request.taskId:
        study_session.current_task_id = None
    session.add(study_session)
    event_id = _log_session_event(
        session,
        study_session,
        request.taskId,
        "task_completed",
        {"taskTitle": task.get("title")},
    )
    session.commit()
    return StudySessionTaskResponse(
        sessionId=study_session.session_id,
        taskId=request.taskId,
        status="completed",
        eventId=event_id,
        currentTaskId=study_session.current_task_id,
    )


@router.post("/log-event", response_model=StudyEventResponse)
def log_study_event(
    request: StudyEventRequest,
    session: Session = Depends(get_session),
) -> StudyEventResponse:
    previous = retry_result(session, request)
    if previous:
        return StudyEventResponse(**previous)
    bind_write(session, request)
    event_id = f"event_write_{request.requestId}" if request.requestId else make_id("event")
    event = StudyEventLog(
        id=event_id,
        session_id=request.sessionId,
        participant_label=request.participantLabel,
        interaction_id=request.interactionId,
        participant_id=request.participantId,
        task_id=request.taskId,
        condition=request.condition,
        event_type=request.eventType,
        metadata_json=_json_or_none(request.metadata),
        created_at=parse_iso_timestamp(request.timestamp) or utc_now(),
    )
    response = commit_write(session, request, event, {"status": "ok", "eventId": event_id})
    return StudyEventResponse(**response)


@router.post("/evidence-use", response_model=EvidenceUseResponse)
def submit_evidence_use(
    request: EvidenceUseRequest,
    session: Session = Depends(get_session),
) -> EvidenceUseResponse:
    previous = retry_result(session, request)
    if previous:
        return EvidenceUseResponse(**previous)
    study_session = bind_write(session, request)
    participant_label = (
        request.participantLabel
        or (study_session.participant_label if study_session else None)
    )
    created_at = parse_iso_timestamp(request.timestamp) or utc_now()
    evidence_use_id = make_id("evidence_use")
    evidence_use = EvidenceUse(
        evidence_use_id=evidence_use_id,
        session_id=request.sessionId,
        participant_label=participant_label,
        task_id=request.taskId,
        interaction_id=request.interactionId,
        citation_id=request.citationId,
        source_id=request.sourceId,
        chunk_id=request.chunkId,
        evidence_action=request.evidenceAction,
        evidence_relevance_rating=request.evidenceRelevanceRating,
        evidence_support_rating=request.evidenceSupportRating,
        user_marked_helpful=request.userMarkedHelpful,
        user_marked_confusing=request.userMarkedConfusing,
        notes=request.notes,
        created_at=created_at,
    )
    session.add(evidence_use)
    event_id = _add_study_event(
        session,
        session_id=request.sessionId,
        participant_label=participant_label,
        participant_id=participant_label,
        interaction_id=request.interactionId,
        task_id=request.taskId,
        condition=study_session.study_condition if study_session else None,
        event_type=_event_type_for_evidence_action(request.evidenceAction),
        created_at=created_at,
        metadata={
            "evidenceUseId": evidence_use_id,
            "evidenceAction": request.evidenceAction,
            "citationId": request.citationId,
            "sourceId": request.sourceId,
            "chunkId": request.chunkId,
            "evidenceRelevanceRating": request.evidenceRelevanceRating,
            "evidenceSupportRating": request.evidenceSupportRating,
            "userMarkedHelpful": request.userMarkedHelpful,
            "userMarkedConfusing": request.userMarkedConfusing,
        },
    )
    event = session.get(StudyEventLog, event_id)
    response = commit_write(session, request, event, {
        "evidenceUseId": evidence_use_id, "createdAt": to_iso(created_at),
    })
    return EvidenceUseResponse(**response)


@router.post("/trust-checklist", response_model=TrustChecklistSnapshotResponse)
def submit_trust_checklist_snapshot(
    request: TrustChecklistSnapshotRequest,
    session: Session = Depends(get_session),
) -> TrustChecklistSnapshotResponse:
    study_session = _study_session_or_none(session, request.sessionId)
    _assert_no_failed_task_interaction(
        session,
        study_session,
        task_id=request.taskId,
        interaction_id=request.interactionId,
    )
    formal_participant = _is_formal_participant_runtime(get_settings())
    if formal_participant:
        _assert_served_interaction(
            session,
            study_session,
            task_id=request.taskId,
            interaction_id=request.interactionId,
        )
    participant_label = (
        request.participantLabel
        or (study_session.participant_label if study_session else None)
    )
    created_at = utc_now()
    trust_snapshot_id = make_id("trust_snapshot")
    snapshot = TrustChecklistSnapshot(
        trust_snapshot_id=trust_snapshot_id,
        session_id=request.sessionId,
        participant_label=participant_label,
        task_id=request.taskId,
        interaction_id=request.interactionId,
        answer_clear=request.answerClear,
        evidence_checked=request.evidenceChecked,
        source_supports_answer=request.sourceSupportsAnswer,
        uncertainty_noticed=request.uncertaintyNoticed,
        would_contact_staff_if_needed=request.wouldContactStaffIfNeeded,
        created_at=created_at,
    )
    session.add(snapshot)
    _add_study_event(
        session,
        session_id=request.sessionId,
        participant_label=participant_label,
        participant_id=participant_label,
        interaction_id=request.interactionId,
        task_id=request.taskId,
        condition=study_session.study_condition if study_session else None,
        event_type="trust_check_updated",
        created_at=created_at,
        metadata={
            "trustSnapshotId": trust_snapshot_id,
            "answerClear": request.answerClear,
            "evidenceChecked": request.evidenceChecked,
            "sourceSupportsAnswer": request.sourceSupportsAnswer,
            "uncertaintyNoticed": request.uncertaintyNoticed,
            "wouldContactStaffIfNeeded": request.wouldContactStaffIfNeeded,
        },
    )
    session.commit()
    return TrustChecklistSnapshotResponse(
        trustSnapshotId=trust_snapshot_id,
        createdAt=to_iso(created_at),
    )


@router.post("/feedback", response_model=FeedbackResponse)
def submit_feedback(
    request: FeedbackRequest,
    session: Session = Depends(get_session),
) -> FeedbackResponse:
    previous = retry_result(session, request)
    if previous:
        return FeedbackResponse(**previous)
    study_session = bind_write(session, request)
    participant_label = (
        request.participantLabel
        or (study_session.participant_label if study_session else None)
    )
    created_at = parse_iso_timestamp(request.timestamp) or utc_now()
    feedback_id = make_id("feedback")
    feedback = FeedbackLog(
        id=feedback_id,
        session_id=request.sessionId,
        participant_label=participant_label,
        task_id=request.taskId,
        interaction_id=request.interactionId,
        answer_id=request.answerId,
        rating=request.rating,
        comment=request.comment,
        created_at=created_at,
    )
    session.add(feedback)
    event_id = _add_study_event(
        session,
        session_id=request.sessionId,
        participant_label=participant_label,
        participant_id=request.participantId or participant_label,
        interaction_id=request.interactionId,
        task_id=request.taskId,
        condition=study_session.study_condition if study_session else None,
        event_type="feedback_submitted",
        created_at=created_at,
        metadata={
            "feedbackId": feedback_id,
            "answerId": request.answerId,
            "rating": request.rating,
            "commentLength": len(request.comment or ""),
        },
    )
    response = commit_write(session, request, session.get(StudyEventLog, event_id), {
        "status": "ok", "feedbackId": feedback_id,
    })
    return FeedbackResponse(**response)


@router.post("/task/final-response", response_model=FinalTaskResponseResponse)
def submit_final_task_response(
    request: FinalTaskResponseRequest,
    session: Session = Depends(get_session),
) -> FinalTaskResponseResponse:
    study_session = session.get(StudySession, request.sessionId)
    if not study_session:
        raise HTTPException(status_code=404, detail="Study session not found")
    task = get_study_task(request.taskId)
    if not task:
        raise HTTPException(status_code=404, detail="Study task not found")
    _assert_no_failed_task_interaction(
        session,
        study_session,
        task_id=request.taskId,
        interaction_id=request.interactionId,
    )
    if _is_formal_participant_runtime(get_settings()):
        _assert_served_interaction(
            session,
            study_session,
            task_id=request.taskId,
            interaction_id=request.interactionId,
        )
        if study_session.current_task_id != request.taskId:
            raise _application_http_error(
                ApplicationError(
                    "invalid_state_transition",
                    researcher_safe_detail="final response task is not active",
                )
            )
        existing_response = session.exec(
            select(FinalTaskResponse).where(
                FinalTaskResponse.session_id == request.sessionId,
                FinalTaskResponse.task_id == request.taskId,
            )
        ).first()
        if existing_response:
            return FinalTaskResponseResponse(
                responseId=existing_response.response_id,
                sessionId=existing_response.session_id,
                taskId=existing_response.task_id,
                createdAt=to_iso(existing_response.created_at),
            )

    response_id = make_id("final_response")
    created_at = utc_now()
    final_response = FinalTaskResponse(
        response_id=response_id,
        session_id=study_session.session_id,
        participant_label=study_session.participant_label,
        task_id=request.taskId,
        interaction_id=request.interactionId,
        final_decision_text=request.finalDecisionText,
        confidence_rating=request.confidenceRating,
        would_contact_staff=request.wouldContactStaff,
        perceived_answer_supported=request.perceivedAnswerSupported,
        perceived_task_difficulty=request.perceivedTaskDifficulty,
        notes=request.notes,
        created_at=created_at,
    )
    session.add(final_response)
    _log_session_event(
        session,
        study_session,
        request.taskId,
        "final_response_submitted",
        {
            "responseId": response_id,
            "confidenceRating": request.confidenceRating,
            "wouldContactStaff": request.wouldContactStaff,
            "perceivedAnswerSupported": request.perceivedAnswerSupported,
            "perceivedTaskDifficulty": request.perceivedTaskDifficulty,
            "finalDecisionLength": len(request.finalDecisionText),
        },
    )
    session.commit()

    return FinalTaskResponseResponse(
        responseId=response_id,
        sessionId=study_session.session_id,
        taskId=request.taskId,
        createdAt=to_iso(created_at),
    )


def _is_formal_participant_runtime(settings: object) -> bool:
    return (
        getattr(settings, "study_mode", "development") == "pilot"
        and getattr(settings, "execution_context", "development")
        == "participant_study"
    )


def _container_or_error(http_request: Request):
    container = getattr(http_request.app.state, "container", None)
    if container is None:
        startup_error = getattr(http_request.app.state, "container_error", None)
        raise _application_http_error(
            ApplicationError(
                "configuration_error",
                researcher_safe_detail=(
                    "application container failed startup validation: "
                    f"{type(startup_error).__name__ if startup_error else 'unknown'}"
                ),
            )
        )
    return container


def _application_http_error(error: ApplicationError) -> HTTPException:
    return HTTPException(
        status_code=error.definition.http_status,
        detail=error.safe_payload(),
    )


def _assert_served_interaction(
    session: Session,
    study_session: StudySession | None,
    *,
    task_id: str | None,
    interaction_id: str | None,
) -> None:
    if not study_session or not interaction_id:
        raise _application_http_error(
            ApplicationError(
                "invalid_state_transition",
                researcher_safe_detail="served interaction reference is required",
            )
        )
    interaction = session.get(InteractionLog, interaction_id)
    if (
        not interaction
        or interaction.session_id != study_session.session_id
        or interaction.task_id != task_id
        or interaction.execution_context != "participant_study"
        or interaction.answer_mode != "live_llm"
    ):
        raise _application_http_error(
            ApplicationError(
                "invalid_state_transition",
                researcher_safe_detail="interaction was not served for active participant task",
            )
        )
