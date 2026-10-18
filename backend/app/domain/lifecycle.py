from __future__ import annotations

from enum import Enum

from app.core.errors import ApplicationError


class StudySessionState(str, Enum):
    CREATED = "created"
    ACKNOWLEDGED = "acknowledged"
    ACTIVE = "active"
    COMPLETED = "completed"
    ABORTED = "aborted"


class StudyTaskState(str, Enum):
    NOT_STARTED = "not_started"
    ACTIVE = "active"
    ANSWER_AVAILABLE = "answer_available"
    FINAL_RESPONSE_SUBMITTED = "final_response_submitted"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class InteractionState(str, Enum):
    RECEIVED = "received"
    SCOPE_CHECKED = "scope_checked"
    RETRIEVED = "retrieved"
    ANSWER_MATCHED = "answer_matched"
    SERVED = "served"
    FAILED = "failed"


def guard_session_activation(
    *, notice_acknowledged: bool, release_frozen: bool, preflight_ok: bool
) -> None:
    if not notice_acknowledged:
        raise ApplicationError(
            "invalid_state_transition",
            researcher_safe_detail="prototype notice acknowledgement is required",
        )
    if not release_frozen:
        raise ApplicationError(
            "release_not_frozen",
            researcher_safe_detail="active participant release is not frozen",
        )
    if not preflight_ok:
        raise ApplicationError(
            "configuration_error",
            researcher_safe_detail="participant preflight did not pass",
        )


def guard_task_start(
    *, session_state: StudySessionState, current_task_id: str | None, task_id: str
) -> None:
    if session_state is not StudySessionState.ACTIVE:
        raise ApplicationError(
            "invalid_state_transition",
            researcher_safe_detail="task start requires an active session",
        )
    if current_task_id and current_task_id != task_id:
        raise ApplicationError(
            "invalid_state_transition",
            researcher_safe_detail="only one task may be active per session",
        )


def guard_task_completion(
    *, task_state: StudyTaskState, final_response_exists: bool
) -> None:
    if task_state is StudyTaskState.COMPLETED:
        return
    if task_state in {StudyTaskState.BLOCKED, StudyTaskState.FAILED}:
        raise ApplicationError(
            "invalid_state_transition",
            researcher_safe_detail="blocked or failed task cannot be completed",
        )
    if not final_response_exists:
        raise ApplicationError(
            "invalid_state_transition",
            researcher_safe_detail="final response is required before task completion",
        )


def guard_final_response(
    *, task_state: StudyTaskState, interaction_state: InteractionState
) -> None:
    if task_state not in {
        StudyTaskState.ACTIVE,
        StudyTaskState.ANSWER_AVAILABLE,
        StudyTaskState.FINAL_RESPONSE_SUBMITTED,
    }:
        raise ApplicationError(
            "invalid_state_transition",
            researcher_safe_detail="final response requires an active task",
        )
    if interaction_state is not InteractionState.SERVED:
        raise ApplicationError(
            "invalid_state_transition",
            researcher_safe_detail="final response must reference a served interaction",
        )
