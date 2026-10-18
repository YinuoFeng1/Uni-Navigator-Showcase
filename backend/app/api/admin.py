import csv
import json
from collections import Counter
from datetime import datetime
from io import StringIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    EvidenceUse,
    FeedbackLog,
    FinalTaskResponse,
    InteractionLog,
    StudyEventLog,
    StudySession,
    TrustChecklistSnapshot,
)
from app.schemas import (
    AdminEventTimelineItem,
    AdminEvidenceUseSummary,
    AdminFeedbackSummary,
    AdminFinalResponseSummary,
    AdminInteractionSummary,
    AdminLogItem,
    AdminLogsResponse,
    AdminSessionDetail,
    AdminSessionSummary,
    AdminSessionsResponse,
    AdminTaskSummary,
    AdminTasksResponse,
    AdminTrustChecklistSummary,
)
from app.services.retrieval_service import get_corpus_status
from app.services.study_tasks import study_tasks_by_id
from app.utils.time import to_iso

router = APIRouter()

CSV_COLUMNS = [
    "row_type",
    "interaction_id",
    "session_id",
    "participant_label",
    "study_condition",
    "participant_id",
    "task_id",
    "task_title",
    "task_type",
    "task_difficulty",
    "escalation_expected",
    "session_started_at",
    "session_completed_at",
    "current_task_id",
    "prototype_notice_acknowledged",
    "prototype_notice_acknowledged_at",
    "condition",
    "event_id",
    "event_type",
    "feedback_id",
    "final_response_id",
    "answer_id",
    "question",
    "answer",
    "full_answer",
    "based_on",
    "limitations",
    "uncertainty",
    "escalation_guidance",
    "high_stakes_detected",
    "escalation_category",
    "escalation_reasons_json",
    "uncertainty_level",
    "escalation_recommended",
    "citation_count",
    "retrieval_status",
    "embedding_provider",
    "embedding_model",
    "embedding_dimension",
    "vector_collection",
    "retrieval_partial_threshold",
    "retrieval_grounded_threshold",
    "retrieval_top_k",
    "retrieval_mode",
    "scope_decision",
    "scope_registry_version",
    "scope_registry_fingerprint",
    "scope_matched_topics",
    "corpus_manifest_fingerprint",
    "ai_provider",
    "ai_model",
    "ai_model_requested",
    "provider_response_model",
    "provider_response_id",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "token_usage_json",
    "answer_mode",
    "task_version",
    "app_version",
    "app_revision",
    "citation_ids",
    "source_ids",
    "chunk_ids",
    "retrieved_chunk_ids",
    "retrieval_trace_json",
    "citations_json",
    "retrieved_context_count",
    "escalation_guidance_present",
    "sensitive_warning_shown",
    "created_at",
    "time_to_first_answer_ms",
    "response_time_ms",
    "error_type",
    "execution_context",
    "answer_strategy_version",
    "release_id",
    "release_version",
    "condition_id",
    "condition_version",
    "task_manifest_version",
    "runtime_config_fingerprint",
    "runtime_config_json",
    "prompt_template_version",
    "generation_temperature",
    "generation_max_tokens",
    "citation_id",
    "source_id",
    "chunk_id",
    "evidence_use_id",
    "evidence_action",
    "evidence_relevance_rating",
    "evidence_support_rating",
    "user_marked_helpful",
    "user_marked_confusing",
    "evidence_use_notes",
    "evidence_use_created_at",
    "trust_snapshot_id",
    "answer_clear",
    "evidence_checked",
    "source_supports_answer",
    "uncertainty_noticed",
    "would_contact_staff_if_needed",
    "trust_snapshot_created_at",
    "feedback_rating",
    "feedback_text",
    "checked_source",
    "evidence_supports_answer",
    "understands_limitation",
    "knows_when_to_contact_staff",
    "pre_confidence",
    "post_confidence",
    "confidence_rating",
    "would_contact_staff",
    "perceived_answer_supported",
    "perceived_task_difficulty",
    "final_decision_text",
    "final_decision_length",
    "final_response_notes",
    "final_response_created_at",
    "decision_appropriateness",
    "researcher_code",
    "metadata_json",
]

SESSION_SUMMARY_COLUMNS = [
    "session_id",
    "participant_label",
    "study_condition",
    "session_started_at",
    "session_completed_at",
    "session_duration_seconds",
    "current_task_id",
    "prototype_notice_acknowledged",
    "prototype_notice_acknowledged_at",
    "total_tasks_started",
    "total_tasks_completed",
    "total_interactions",
    "total_questions",
    "total_answers",
    "total_feedback_submitted",
    "total_evidence_actions",
    "total_evidence_panel_opened",
    "total_source_checked",
    "total_evidence_ratings",
    "average_evidence_support_rating",
    "latest_answer_clear",
    "latest_evidence_checked",
    "latest_source_supports_answer",
    "latest_uncertainty_noticed",
    "latest_would_contact_staff_if_needed",
    "total_final_responses",
    "average_confidence_rating",
    "average_perceived_answer_supported",
    "would_contact_staff_yes_count",
    "would_contact_staff_no_count",
    "would_contact_staff_unsure_count",
    "high_stakes_interaction_count",
    "ambiguous_or_partial_retrieval_count",
    "insufficient_evidence_count",
    "sensitive_warning_shown_count",
    "last_activity_at",
]

TASK_SUMMARY_COLUMNS = [
    "session_id",
    "participant_label",
    "study_condition",
    "task_id",
    "task_title",
    "task_type",
    "task_difficulty",
    "escalation_expected",
    "expected_safe_behaviour",
    "prototype_notice_acknowledged",
    "task_started_at",
    "task_completed_at",
    "task_duration_seconds",
    "interaction_count",
    "question_count",
    "answer_count",
    "retrieval_statuses",
    "high_stakes_detected_count",
    "sensitive_warning_shown_count",
    "citation_count_total",
    "distinct_source_count",
    "distinct_chunk_count",
    "evidence_action_count",
    "evidence_panel_opened_count",
    "source_checked_count",
    "evidence_rating_count",
    "average_evidence_support_rating",
    "user_marked_helpful_count",
    "user_marked_confusing_count",
    "latest_answer_clear",
    "latest_evidence_checked",
    "latest_source_supports_answer",
    "latest_uncertainty_noticed",
    "latest_would_contact_staff_if_needed",
    "final_response_submitted",
    "final_decision_length",
    "confidence_rating",
    "would_contact_staff",
    "perceived_answer_supported",
    "perceived_task_difficulty",
    "decision_appropriateness",
    "researcher_code",
    "notes_present",
]


def _chunk_ids(value: str | None) -> list[str]:
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []

    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, str)]
    return []


def _json_object_list(value: str | None) -> list[dict]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, dict)]


def _json_object(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_csv_id_list(value: str | None) -> list[str]:
    if not value:
        return []

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        delimiter = "|" if "|" in value else "," if "," in value else None
        if delimiter:
            return [item.strip() for item in value.split(delimiter) if item.strip()]
        return [value.strip()]

    if isinstance(parsed, list):
        return [str(item) for item in parsed if item is not None and str(item)]
    return []


def _json_text(value: str | None) -> str:
    if not value:
        return ""

    try:
        return json.dumps(json.loads(value), ensure_ascii=False, sort_keys=True)
    except json.JSONDecodeError:
        return value


def _metadata(value: str | None) -> dict:
    if not value:
        return {}

    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _empty_csv_row() -> dict[str, str]:
    return {column: "" for column in CSV_COLUMNS}


def _iso_or_empty(value) -> str:
    return to_iso(value) if value is not None else ""


def bool_to_csv(value: bool | None) -> str:
    if value is None:
        return ""
    return str(value).lower()


def _number_to_csv(value: float | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def safe_average(values: list[int | float | None]) -> float | None:
    present = [value for value in values if value is not None]
    if not present:
        return None
    return round(sum(present) / len(present), 2)


def seconds_between(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None:
        return None
    return max(0, int((end - start).total_seconds()))


def latest_by_created_at(items):
    return max(items, key=lambda item: item.created_at) if items else None


def _apply_study_context(
    row: dict[str, str],
    session_id: str | None,
    task_id: str | None,
    sessions_by_id: dict[str, StudySession],
    tasks_by_id: dict[str, dict],
) -> None:
    if session_id:
        row["session_id"] = session_id
        study_session = sessions_by_id.get(session_id)
        if study_session:
            row["participant_label"] = study_session.participant_label
            row["study_condition"] = study_session.study_condition or ""
            row["session_started_at"] = to_iso(study_session.started_at)
            row["session_completed_at"] = _iso_or_empty(study_session.completed_at)
            row["current_task_id"] = study_session.current_task_id or ""
            row["prototype_notice_acknowledged"] = bool_to_csv(
                study_session.prototype_notice_acknowledged
            )
            row["prototype_notice_acknowledged_at"] = _iso_or_empty(
                study_session.prototype_notice_acknowledged_at
            )

    if task_id:
        row["task_id"] = task_id
        task = tasks_by_id.get(task_id)
        if task:
            row["task_title"] = str(task.get("title") or "")
            row["task_type"] = str(task.get("task_type") or "")
            row["task_difficulty"] = str(task.get("difficulty") or "")
            row["escalation_expected"] = str(
                bool(task.get("escalation_expected"))
            ).lower()


def _base_interaction_fields(
    log: InteractionLog | None,
    sessions_by_id: dict[str, StudySession] | None = None,
    tasks_by_id: dict[str, dict] | None = None,
) -> dict[str, str]:
    row = _empty_csv_row()
    if not log:
        return row

    sessions_by_id = sessions_by_id or {}
    tasks_by_id = tasks_by_id or {}
    row.update(
        {
            "interaction_id": log.id,
            "session_id": log.session_id or "",
            "participant_label": log.participant_label or "",
            "participant_id": log.participant_id or "",
            "task_id": log.task_id or "",
            "condition": log.condition,
            "answer_id": log.answer_id,
            "question": log.question,
            "answer": log.short_answer,
            "full_answer": log.full_answer or log.short_answer,
            "based_on": log.based_on or "",
            "limitations": log.limitations or "",
            "uncertainty": log.uncertainty or "",
            "escalation_guidance": log.escalation_guidance or "",
            "high_stakes_detected": (
                str(log.high_stakes_detected).lower()
                if log.high_stakes_detected is not None
                else ""
            ),
            "escalation_category": log.escalation_category or "",
            "escalation_reasons_json": _json_text(
                log.escalation_reasons_json
            ),
            "uncertainty_level": log.uncertainty_level,
            "escalation_recommended": str(log.escalation_recommended).lower(),
            "citation_count": str(log.citation_count),
            "retrieval_status": log.retrieval_status or "",
            "embedding_provider": log.embedding_provider or "",
            "embedding_model": log.embedding_model or "",
            "embedding_dimension": (
                str(log.embedding_dimension)
                if log.embedding_dimension is not None
                else ""
            ),
            "vector_collection": log.vector_collection or "",
            "retrieval_partial_threshold": (
                str(log.retrieval_partial_threshold)
                if log.retrieval_partial_threshold is not None
                else ""
            ),
            "retrieval_grounded_threshold": (
                str(log.retrieval_grounded_threshold)
                if log.retrieval_grounded_threshold is not None
                else ""
            ),
            "retrieval_top_k": (
                str(log.retrieval_top_k)
                if log.retrieval_top_k is not None
                else ""
            ),
            "retrieval_mode": log.retrieval_mode or "",
            "scope_decision": log.scope_decision or "",
            "scope_registry_version": log.scope_registry_version or "",
            "scope_registry_fingerprint": log.scope_registry_fingerprint or "",
            "scope_matched_topics": _json_text(log.scope_matched_topics),
            "corpus_manifest_fingerprint": (
                log.corpus_manifest_fingerprint or ""
            ),
            "ai_provider": log.ai_provider or "",
            "ai_model": log.ai_model or "",
            "ai_model_requested": log.ai_model_requested or "",
            "provider_response_model": log.provider_response_model or "",
            "provider_response_id": log.provider_response_id or "",
            "input_tokens": _number_to_csv(log.input_tokens),
            "output_tokens": _number_to_csv(log.output_tokens),
            "total_tokens": _number_to_csv(log.total_tokens),
            "token_usage_json": _json_text(log.token_usage_json),
            "answer_mode": log.answer_mode or "",
            "task_version": log.task_version or "",
            "app_version": log.app_version or "",
            "app_revision": log.app_revision or log.app_version or "",
            "citation_ids": _json_text(log.citation_ids),
            "source_ids": _json_text(log.source_ids),
            "chunk_ids": _json_text(log.retrieved_chunk_ids),
            "retrieved_chunk_ids": _json_text(log.retrieved_chunk_ids),
            "retrieval_trace_json": _json_text(log.retrieval_trace_json),
            "citations_json": _json_text(log.citations_json),
            "retrieved_context_count": (
                str(log.retrieved_context_count)
                if log.retrieved_context_count is not None
                else ""
            ),
            "escalation_guidance_present": (
                str(log.escalation_guidance_present).lower()
                if log.escalation_guidance_present is not None
                else ""
            ),
            "sensitive_warning_shown": (
                str(log.sensitive_warning_shown).lower()
                if log.sensitive_warning_shown is not None
                else ""
            ),
            "time_to_first_answer_ms": (
                str(log.time_to_first_answer_ms)
                if log.time_to_first_answer_ms is not None
                else ""
            ),
            "response_time_ms": _number_to_csv(log.response_time_ms),
            "error_type": log.error_type or "",
            "execution_context": log.execution_context or "",
            "answer_strategy_version": log.answer_strategy_version or "",
            "release_id": log.release_id or "",
            "release_version": log.release_version or "",
            "condition_id": log.condition_id or "",
            "condition_version": log.condition_version or "",
            "task_manifest_version": log.task_manifest_version or "",
            "runtime_config_fingerprint": log.runtime_config_fingerprint or "",
            "runtime_config_json": _json_text(log.runtime_config_json),
            "prompt_template_version": log.prompt_template_version or "",
            "generation_temperature": _number_to_csv(
                log.generation_temperature
            ),
            "generation_max_tokens": _number_to_csv(log.generation_max_tokens),
        }
    )
    _apply_study_context(row, log.session_id, log.task_id, sessions_by_id, tasks_by_id)
    return row


def _metadata_value(metadata: dict, key: str) -> str:
    value = metadata.get(key)
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


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


def _preview_text(value: str | None, limit: int = 120) -> str:
    if not value:
        return ""
    collapsed = " ".join(value.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[: max(0, limit - 3)]}..."


def _latest_datetime(values: list[datetime | None]) -> datetime | None:
    present = [value for value in values if value is not None]
    return max(present) if present else None


def _earliest_datetime(values: list[datetime | None]) -> datetime | None:
    present = [value for value in values if value is not None]
    return min(present) if present else None


def _metadata_keys(value: str | None) -> list[str]:
    return sorted(_metadata(value).keys())


def _trust_summary(
    snapshot: TrustChecklistSnapshot | None,
) -> AdminTrustChecklistSummary | None:
    if not snapshot:
        return None
    return AdminTrustChecklistSummary(
        trustSnapshotId=snapshot.trust_snapshot_id,
        answerClear=snapshot.answer_clear,
        evidenceChecked=snapshot.evidence_checked,
        sourceSupportsAnswer=snapshot.source_supports_answer,
        uncertaintyNoticed=snapshot.uncertainty_noticed,
        wouldContactStaffIfNeeded=snapshot.would_contact_staff_if_needed,
        createdAt=to_iso(snapshot.created_at),
    )


def _build_session_summary(
    study_session: StudySession,
    interactions: list[InteractionLog],
    events: list[StudyEventLog],
    feedback_logs: list[FeedbackLog],
    final_responses: list[FinalTaskResponse],
    evidence_uses: list[EvidenceUse],
    trust_snapshots: list[TrustChecklistSnapshot],
) -> AdminSessionSummary:
    started_task_ids = {
        event.task_id
        for event in events
        if event.event_type == "task_started" and event.task_id
    }
    completed_task_ids = {
        event.task_id
        for event in events
        if event.event_type == "task_completed" and event.task_id
    }
    latest_trust_snapshot = (
        max(trust_snapshots, key=lambda item: item.created_at)
        if trust_snapshots
        else None
    )
    last_activity = _latest_datetime(
        [
            study_session.started_at,
            study_session.completed_at,
            *[item.created_at for item in interactions],
            *[item.created_at for item in events],
            *[item.created_at for item in feedback_logs],
            *[item.created_at for item in final_responses],
            *[item.created_at for item in evidence_uses],
            *[item.created_at for item in trust_snapshots],
        ]
    )

    return AdminSessionSummary(
        sessionId=study_session.session_id,
        participantLabel=study_session.participant_label,
        studyCondition=study_session.study_condition,
        startedAt=to_iso(study_session.started_at),
        completedAt=_iso_or_empty(study_session.completed_at) or None,
        currentTaskId=study_session.current_task_id,
        prototypeNoticeAcknowledged=study_session.prototype_notice_acknowledged,
        tasksStartedCount=len(started_task_ids),
        tasksCompletedCount=len(completed_task_ids),
        interactionCount=len(interactions),
        evidenceUseCount=len(evidence_uses),
        sourceCheckedCount=sum(
            1 for item in evidence_uses if item.evidence_action == "source_checked"
        ),
        feedbackCount=len(feedback_logs),
        finalResponseCount=len(final_responses),
        sensitiveWarningShownCount=sum(
            1 for item in interactions if item.sensitive_warning_shown is True
        ),
        latestTrustChecklistSummary=_trust_summary(latest_trust_snapshot),
        lastActivityAt=to_iso(last_activity or study_session.started_at),
    )


def _session_scoped_records(
    session: Session,
    session_id: str,
) -> tuple[
    list[InteractionLog],
    list[StudyEventLog],
    list[FeedbackLog],
    list[FinalTaskResponse],
    list[EvidenceUse],
    list[TrustChecklistSnapshot],
]:
    interactions = session.exec(
        select(InteractionLog).where(InteractionLog.session_id == session_id)
    ).all()
    events = session.exec(
        select(StudyEventLog).where(StudyEventLog.session_id == session_id)
    ).all()
    feedback_logs = session.exec(
        select(FeedbackLog).where(FeedbackLog.session_id == session_id)
    ).all()
    final_responses = session.exec(
        select(FinalTaskResponse).where(FinalTaskResponse.session_id == session_id)
    ).all()
    evidence_uses = session.exec(
        select(EvidenceUse).where(EvidenceUse.session_id == session_id)
    ).all()
    trust_snapshots = session.exec(
        select(TrustChecklistSnapshot).where(
            TrustChecklistSnapshot.session_id == session_id
        )
    ).all()
    return (
        interactions,
        events,
        feedback_logs,
        final_responses,
        evidence_uses,
        trust_snapshots,
    )


def build_research_logs_csv(
    interactions: list[InteractionLog],
    events: list[StudyEventLog],
    feedback_logs: list[FeedbackLog],
    final_task_responses: list[FinalTaskResponse] | None = None,
    evidence_uses: list[EvidenceUse] | None = None,
    trust_checklists: list[TrustChecklistSnapshot] | None = None,
    study_sessions: list[StudySession] | None = None,
    tasks_by_id: dict[str, dict] | None = None,
) -> str:
    interactions_by_id = {log.id: log for log in interactions}
    interactions_by_answer_id = {log.answer_id: log for log in interactions}
    sessions_by_id = {item.session_id: item for item in study_sessions or []}
    tasks_by_id = tasks_by_id or study_tasks_by_id()
    rows: list[dict[str, str]] = []

    for interaction in interactions:
        row = _base_interaction_fields(interaction, sessions_by_id, tasks_by_id)
        row["row_type"] = "interaction"
        row["created_at"] = to_iso(interaction.created_at)
        rows.append(row)

    for event in events:
        metadata = _metadata(event.metadata_json)
        event_trace = metadata.get("retrieval_trace")
        if not isinstance(event_trace, list):
            event_trace = []
        event_chunk_ids = [
            item.get("chunk_id")
            for item in event_trace
            if isinstance(item, dict) and item.get("chunk_id")
        ]
        event_usage = metadata.get("token_usage")
        if not isinstance(event_usage, dict):
            event_usage = {}
        event_runtime = metadata.get("runtime_config")
        if not isinstance(event_runtime, dict):
            event_runtime = {}
        row = _base_interaction_fields(
            interactions_by_id.get(event.interaction_id or ""),
            sessions_by_id,
            tasks_by_id,
        )
        row.update(
            {
                "row_type": "event",
                "interaction_id": event.interaction_id or row["interaction_id"],
                "session_id": event.session_id or row["session_id"],
                "participant_label": event.participant_label
                or row["participant_label"],
                "participant_id": event.participant_id or row["participant_id"],
                "task_id": event.task_id or row["task_id"],
                "condition": event.condition or row["condition"],
                "event_id": event.id,
                "event_type": event.event_type,
                "created_at": to_iso(event.created_at),
                "error_type": _metadata_value(metadata, "error_code"),
                "retrieval_status": _metadata_value(
                    metadata, "retrieval_status"
                )
                or row["retrieval_status"],
                "retrieval_trace_json": (
                    json.dumps(event_trace, ensure_ascii=False, sort_keys=True)
                    if event_trace
                    else row["retrieval_trace_json"]
                ),
                "retrieved_chunk_ids": (
                    json.dumps(event_chunk_ids, ensure_ascii=False)
                    if event_chunk_ids
                    else row["retrieved_chunk_ids"]
                ),
                "chunk_ids": (
                    json.dumps(event_chunk_ids, ensure_ascii=False)
                    if event_chunk_ids
                    else row["chunk_ids"]
                ),
                "provider_response_id": _metadata_value(
                    metadata, "provider_response_id"
                )
                or row["provider_response_id"],
                "provider_response_model": _metadata_value(
                    metadata, "provider_response_model"
                )
                or row["provider_response_model"],
                "input_tokens": _number_to_csv(event_usage.get("input_tokens"))
                or row["input_tokens"],
                "output_tokens": _number_to_csv(event_usage.get("output_tokens"))
                or row["output_tokens"],
                "total_tokens": _number_to_csv(event_usage.get("total_tokens"))
                or row["total_tokens"],
                "token_usage_json": (
                    json.dumps(event_usage, ensure_ascii=False, sort_keys=True)
                    if event_usage
                    else row["token_usage_json"]
                ),
                "response_time_ms": _metadata_value(
                    metadata, "response_time_ms"
                ),
                "embedding_provider": event_runtime.get("embedding_provider")
                or row["embedding_provider"],
                "embedding_model": event_runtime.get("embedding_model")
                or row["embedding_model"],
                "embedding_dimension": _number_to_csv(
                    event_runtime.get("embedding_dimension")
                )
                or row["embedding_dimension"],
                "vector_collection": event_runtime.get(
                    "vector_store_collection"
                )
                or row["vector_collection"],
                "retrieval_partial_threshold": _number_to_csv(
                    event_runtime.get("retrieval_partial_threshold")
                )
                or row["retrieval_partial_threshold"],
                "retrieval_grounded_threshold": _number_to_csv(
                    event_runtime.get("retrieval_grounded_threshold")
                )
                or row["retrieval_grounded_threshold"],
                "retrieval_top_k": _number_to_csv(
                    event_runtime.get("retrieval_top_k")
                )
                or row["retrieval_top_k"],
                "retrieval_mode": event_runtime.get("retrieval_source_mode")
                or row["retrieval_mode"],
                "scope_registry_version": event_runtime.get(
                    "scope_registry_version"
                )
                or row["scope_registry_version"],
                "scope_registry_fingerprint": event_runtime.get(
                    "scope_registry_fingerprint"
                )
                or row["scope_registry_fingerprint"],
                "corpus_manifest_fingerprint": event_runtime.get(
                    "corpus_fingerprint"
                )
                or row["corpus_manifest_fingerprint"],
                "ai_provider": event_runtime.get("ai_provider")
                or row["ai_provider"],
                "ai_model": _metadata_value(
                    metadata, "provider_response_model"
                )
                or event_runtime.get("ai_model")
                or row["ai_model"],
                "ai_model_requested": event_runtime.get("ai_model")
                or row["ai_model_requested"],
                "answer_mode": event_runtime.get("answer_mode")
                or row["answer_mode"],
                "app_version": row["app_version"],
                "app_revision": event.app_revision or row["app_revision"],
                "execution_context": event_runtime.get("execution_context")
                or row["execution_context"],
                "release_id": event.release_id or row["release_id"],
                "release_version": event_runtime.get("pilot_release_version")
                or row["release_version"],
                "condition_id": event.condition_id or row["condition_id"],
                "condition_version": event_runtime.get("condition_version")
                or row["condition_version"],
                "task_manifest_version": event_runtime.get(
                    "task_manifest_version"
                )
                or row["task_manifest_version"],
                "runtime_config_fingerprint": (
                    event.runtime_config_fingerprint
                    or row["runtime_config_fingerprint"]
                ),
                "runtime_config_json": (
                    json.dumps(event_runtime, ensure_ascii=False, sort_keys=True)
                    if event_runtime
                    else row["runtime_config_json"]
                ),
                "prompt_template_version": event_runtime.get(
                    "prompt_template_version"
                )
                or row["prompt_template_version"],
                "generation_temperature": _number_to_csv(
                    event_runtime.get("generation_temperature")
                )
                or row["generation_temperature"],
                "generation_max_tokens": _number_to_csv(
                    event_runtime.get("generation_max_tokens")
                )
                or row["generation_max_tokens"],
                "citation_id": _metadata_value(metadata, "citationId"),
                "source_id": _metadata_value(metadata, "sourceId"),
                "chunk_id": _metadata_value(metadata, "chunkId"),
                "checked_source": _metadata_value(metadata, "checkedSource"),
                "evidence_supports_answer": _metadata_value(
                    metadata, "evidenceSupportsAnswer"
                )
                or _metadata_value(metadata, "sourceSupportsAnswer"),
                "answer_clear": _metadata_value(metadata, "answerClear"),
                "evidence_checked": _metadata_value(metadata, "evidenceChecked"),
                "source_supports_answer": _metadata_value(
                    metadata, "sourceSupportsAnswer"
                ),
                "understands_limitation": _metadata_value(
                    metadata, "understandsLimitation"
                ),
                "uncertainty_noticed": _metadata_value(
                    metadata, "uncertaintyNoticed"
                ),
                "knows_when_to_contact_staff": _metadata_value(
                    metadata, "knowsWhenToContactStaff"
                )
                or _metadata_value(
                    metadata, "wouldContactStaffIfNeeded"
                ),
                "would_contact_staff_if_needed": _metadata_value(
                    metadata, "wouldContactStaffIfNeeded"
                ),
                "evidence_use_id": _metadata_value(metadata, "evidenceUseId"),
                "evidence_action": _metadata_value(metadata, "evidenceAction"),
                "evidence_relevance_rating": _metadata_value(
                    metadata, "evidenceRelevanceRating"
                ),
                "evidence_support_rating": _metadata_value(
                    metadata, "evidenceSupportRating"
                ),
                "user_marked_helpful": _metadata_value(
                    metadata, "userMarkedHelpful"
                ),
                "user_marked_confusing": _metadata_value(
                    metadata, "userMarkedConfusing"
                ),
                "trust_snapshot_id": _metadata_value(metadata, "trustSnapshotId"),
                "pre_confidence": _metadata_value(metadata, "preConfidence"),
                "post_confidence": _metadata_value(metadata, "postConfidence"),
                "final_decision_length": _metadata_value(
                    metadata, "finalDecisionLength"
                ),
                "metadata_json": _json_text(event.metadata_json),
            }
        )
        _apply_study_context(
            row,
            event.session_id or row["session_id"],
            event.task_id or row["task_id"],
            sessions_by_id,
            tasks_by_id,
        )
        rows.append(row)

    for evidence_use in evidence_uses or []:
        row = _base_interaction_fields(
            interactions_by_id.get(evidence_use.interaction_id or ""),
            sessions_by_id,
            tasks_by_id,
        )
        row.update(
            {
                "row_type": "evidence_use",
                "interaction_id": evidence_use.interaction_id
                or row["interaction_id"],
                "session_id": evidence_use.session_id or row["session_id"],
                "participant_label": evidence_use.participant_label
                or row["participant_label"],
                "task_id": evidence_use.task_id or row["task_id"],
                "event_type": _event_type_for_evidence_action(
                    evidence_use.evidence_action
                ),
                "evidence_use_id": evidence_use.evidence_use_id,
                "evidence_action": evidence_use.evidence_action,
                "citation_id": evidence_use.citation_id or "",
                "source_id": evidence_use.source_id or "",
                "chunk_id": evidence_use.chunk_id or "",
                "evidence_relevance_rating": (
                    str(evidence_use.evidence_relevance_rating)
                    if evidence_use.evidence_relevance_rating is not None
                    else ""
                ),
                "evidence_support_rating": (
                    str(evidence_use.evidence_support_rating)
                    if evidence_use.evidence_support_rating is not None
                    else ""
                ),
                "user_marked_helpful": (
                    str(evidence_use.user_marked_helpful).lower()
                    if evidence_use.user_marked_helpful is not None
                    else ""
                ),
                "user_marked_confusing": (
                    str(evidence_use.user_marked_confusing).lower()
                    if evidence_use.user_marked_confusing is not None
                    else ""
                ),
                "evidence_use_notes": evidence_use.notes or "",
                "evidence_use_created_at": to_iso(evidence_use.created_at),
                "created_at": to_iso(evidence_use.created_at),
            }
        )
        _apply_study_context(
            row,
            evidence_use.session_id or row["session_id"],
            evidence_use.task_id or row["task_id"],
            sessions_by_id,
            tasks_by_id,
        )
        rows.append(row)

    for snapshot in trust_checklists or []:
        row = _base_interaction_fields(
            interactions_by_id.get(snapshot.interaction_id or ""),
            sessions_by_id,
            tasks_by_id,
        )
        row.update(
            {
                "row_type": "trust_checklist",
                "interaction_id": snapshot.interaction_id or row["interaction_id"],
                "session_id": snapshot.session_id or row["session_id"],
                "participant_label": snapshot.participant_label
                or row["participant_label"],
                "task_id": snapshot.task_id or row["task_id"],
                "event_type": "trust_check_updated",
                "trust_snapshot_id": snapshot.trust_snapshot_id,
                "answer_clear": (
                    str(snapshot.answer_clear).lower()
                    if snapshot.answer_clear is not None
                    else ""
                ),
                "evidence_checked": (
                    str(snapshot.evidence_checked).lower()
                    if snapshot.evidence_checked is not None
                    else ""
                ),
                "source_supports_answer": (
                    str(snapshot.source_supports_answer).lower()
                    if snapshot.source_supports_answer is not None
                    else ""
                ),
                "uncertainty_noticed": (
                    str(snapshot.uncertainty_noticed).lower()
                    if snapshot.uncertainty_noticed is not None
                    else ""
                ),
                "would_contact_staff_if_needed": (
                    str(snapshot.would_contact_staff_if_needed).lower()
                    if snapshot.would_contact_staff_if_needed is not None
                    else ""
                ),
                "trust_snapshot_created_at": to_iso(snapshot.created_at),
                "created_at": to_iso(snapshot.created_at),
            }
        )
        _apply_study_context(
            row,
            snapshot.session_id or row["session_id"],
            snapshot.task_id or row["task_id"],
            sessions_by_id,
            tasks_by_id,
        )
        rows.append(row)

    for feedback in feedback_logs:
        row = _base_interaction_fields(
            interactions_by_id.get(feedback.interaction_id or "")
            or interactions_by_answer_id.get(feedback.answer_id),
            sessions_by_id,
            tasks_by_id,
        )
        row.update(
            {
                "row_type": "feedback",
                "interaction_id": feedback.interaction_id or row["interaction_id"],
                "session_id": feedback.session_id or row["session_id"],
                "participant_label": feedback.participant_label
                or row["participant_label"],
                "task_id": feedback.task_id or row["task_id"],
                "feedback_id": feedback.id,
                "event_type": "feedback_submitted",
                "answer_id": feedback.answer_id,
                "created_at": to_iso(feedback.created_at),
                "feedback_rating": feedback.rating,
                "feedback_text": feedback.comment or "",
            }
        )
        _apply_study_context(
            row,
            feedback.session_id or row["session_id"],
            feedback.task_id or row["task_id"],
            sessions_by_id,
            tasks_by_id,
        )
        rows.append(row)

    for final_response in final_task_responses or []:
        study_session = sessions_by_id.get(final_response.session_id)
        row = _base_interaction_fields(
            interactions_by_id.get(final_response.interaction_id or ""),
            sessions_by_id,
            tasks_by_id,
        )
        row.update(
            {
                "row_type": "final_response",
                "interaction_id": final_response.interaction_id
                or row["interaction_id"],
                "session_id": final_response.session_id,
                "participant_label": final_response.participant_label
                or row["participant_label"],
                "task_id": final_response.task_id,
                "condition": row["condition"]
                or (study_session.study_condition if study_session else ""),
                "event_type": "final_response_submitted",
                "final_response_id": final_response.response_id,
                "created_at": to_iso(final_response.created_at),
                "confidence_rating": str(final_response.confidence_rating),
                "would_contact_staff": final_response.would_contact_staff,
                "perceived_answer_supported": str(
                    final_response.perceived_answer_supported
                ),
                "perceived_task_difficulty": (
                    str(final_response.perceived_task_difficulty)
                    if final_response.perceived_task_difficulty is not None
                    else ""
                ),
                "final_decision_text": final_response.final_decision_text,
                "final_decision_length": str(
                    len(final_response.final_decision_text.strip())
                ),
                "final_response_notes": final_response.notes or "",
                "final_response_created_at": to_iso(final_response.created_at),
                "decision_appropriateness": (
                    final_response.decision_appropriateness or ""
                ),
                "researcher_code": final_response.researcher_code or "",
            }
        )
        _apply_study_context(
            row,
            final_response.session_id,
            final_response.task_id,
            sessions_by_id,
            tasks_by_id,
        )
        rows.append(row)

    rows.sort(key=lambda item: (item["created_at"], item["row_type"], item["event_id"]))

    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _write_csv(columns: list[str], rows: list[dict[str, str]]) -> str:
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue()


def _record_session_id(
    item,
    interactions_by_id: dict[str, InteractionLog],
    interactions_by_answer_id: dict[str, InteractionLog],
) -> str | None:
    session_id = getattr(item, "session_id", None)
    if session_id:
        return session_id

    interaction_id = getattr(item, "interaction_id", None)
    if interaction_id and interaction_id in interactions_by_id:
        return interactions_by_id[interaction_id].session_id

    answer_id = getattr(item, "answer_id", None)
    if answer_id and answer_id in interactions_by_answer_id:
        return interactions_by_answer_id[answer_id].session_id

    return None


def _record_task_id(
    item,
    interactions_by_id: dict[str, InteractionLog],
    interactions_by_answer_id: dict[str, InteractionLog],
) -> str | None:
    task_id = getattr(item, "task_id", None)
    if task_id:
        return task_id

    interaction_id = getattr(item, "interaction_id", None)
    if interaction_id and interaction_id in interactions_by_id:
        return interactions_by_id[interaction_id].task_id

    answer_id = getattr(item, "answer_id", None)
    if answer_id and answer_id in interactions_by_answer_id:
        return interactions_by_answer_id[answer_id].task_id

    return None


def _latest_trust_values(snapshot: TrustChecklistSnapshot | None) -> dict[str, str]:
    return {
        "latest_answer_clear": bool_to_csv(snapshot.answer_clear if snapshot else None),
        "latest_evidence_checked": bool_to_csv(
            snapshot.evidence_checked if snapshot else None
        ),
        "latest_source_supports_answer": bool_to_csv(
            snapshot.source_supports_answer if snapshot else None
        ),
        "latest_uncertainty_noticed": bool_to_csv(
            snapshot.uncertainty_noticed if snapshot else None
        ),
        "latest_would_contact_staff_if_needed": bool_to_csv(
            snapshot.would_contact_staff_if_needed if snapshot else None
        ),
    }


def _final_contact_counts(final_responses: list[FinalTaskResponse]) -> Counter:
    counts: Counter = Counter()
    for final_response in final_responses:
        value = final_response.would_contact_staff
        if value == "not_sure":
            value = "unsure"
        counts.update([value])
    return counts


def _task_metadata(task_id: str | None, tasks_by_id: dict[str, dict]) -> dict:
    if not task_id:
        return {}
    return tasks_by_id.get(task_id, {})


def _task_metadata_value(task: dict, key: str, default: str = "") -> str:
    value = task.get(key, default)
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def build_session_summary_rows(
    study_sessions: list[StudySession],
    interactions: list[InteractionLog],
    events: list[StudyEventLog],
    feedback_logs: list[FeedbackLog],
    final_task_responses: list[FinalTaskResponse],
    evidence_uses: list[EvidenceUse],
    trust_checklists: list[TrustChecklistSnapshot],
) -> list[dict[str, str]]:
    interactions_by_id = {item.id: item for item in interactions}
    interactions_by_answer_id = {item.answer_id: item for item in interactions}

    def session_id_for(item) -> str | None:
        return _record_session_id(item, interactions_by_id, interactions_by_answer_id)

    rows: list[dict[str, str]] = []
    for study_session in study_sessions:
        session_id = study_session.session_id
        session_interactions = [
            item for item in interactions if session_id_for(item) == session_id
        ]
        session_events = [item for item in events if session_id_for(item) == session_id]
        session_feedback = [
            item for item in feedback_logs if session_id_for(item) == session_id
        ]
        session_finals = [
            item for item in final_task_responses if session_id_for(item) == session_id
        ]
        session_evidence = [
            item for item in evidence_uses if session_id_for(item) == session_id
        ]
        session_trust = [
            item for item in trust_checklists if session_id_for(item) == session_id
        ]
        latest_trust = latest_by_created_at(session_trust)
        contact_counts = _final_contact_counts(session_finals)
        started_task_ids = {
            event.task_id
            for event in session_events
            if event.event_type == "task_started" and event.task_id
        }
        completed_task_ids = {
            event.task_id
            for event in session_events
            if event.event_type == "task_completed" and event.task_id
        }
        last_activity = _latest_datetime(
            [
                study_session.started_at,
                study_session.completed_at,
                *[item.created_at for item in session_interactions],
                *[item.created_at for item in session_events],
                *[item.created_at for item in session_feedback],
                *[item.created_at for item in session_finals],
                *[item.created_at for item in session_evidence],
                *[item.created_at for item in session_trust],
            ]
        )
        evidence_support_average = safe_average(
            [item.evidence_support_rating for item in session_evidence]
        )
        confidence_average = safe_average(
            [item.confidence_rating for item in session_finals]
        )
        perceived_support_average = safe_average(
            [item.perceived_answer_supported for item in session_finals]
        )

        row = {
            "session_id": session_id,
            "participant_label": study_session.participant_label,
            "study_condition": study_session.study_condition or "",
            "session_started_at": to_iso(study_session.started_at),
            "session_completed_at": _iso_or_empty(study_session.completed_at),
            "session_duration_seconds": _number_to_csv(
                seconds_between(study_session.started_at, study_session.completed_at)
            ),
            "current_task_id": study_session.current_task_id or "",
            "prototype_notice_acknowledged": bool_to_csv(
                study_session.prototype_notice_acknowledged
            ),
            "prototype_notice_acknowledged_at": _iso_or_empty(
                study_session.prototype_notice_acknowledged_at
            ),
            "total_tasks_started": str(len(started_task_ids)),
            "total_tasks_completed": str(len(completed_task_ids)),
            "total_interactions": str(len(session_interactions)),
            "total_questions": str(len(session_interactions)),
            "total_answers": str(len(session_interactions)),
            "total_feedback_submitted": str(len(session_feedback)),
            "total_evidence_actions": str(len(session_evidence)),
            "total_evidence_panel_opened": str(
                sum(
                    1
                    for item in session_evidence
                    if item.evidence_action == "evidence_panel_opened"
                )
            ),
            "total_source_checked": str(
                sum(1 for item in session_evidence if item.evidence_action == "source_checked")
            ),
            "total_evidence_ratings": str(
                sum(
                    1
                    for item in session_evidence
                    if item.evidence_support_rating is not None
                    or item.evidence_relevance_rating is not None
                )
            ),
            "average_evidence_support_rating": _number_to_csv(
                evidence_support_average
            ),
            "total_final_responses": str(len(session_finals)),
            "average_confidence_rating": _number_to_csv(confidence_average),
            "average_perceived_answer_supported": _number_to_csv(
                perceived_support_average
            ),
            "would_contact_staff_yes_count": str(contact_counts.get("yes", 0)),
            "would_contact_staff_no_count": str(contact_counts.get("no", 0)),
            "would_contact_staff_unsure_count": str(contact_counts.get("unsure", 0)),
            "high_stakes_interaction_count": str(
                sum(1 for item in session_interactions if item.high_stakes_detected is True)
            ),
            "ambiguous_or_partial_retrieval_count": str(
                sum(
                    1
                    for item in session_interactions
                    if item.retrieval_status
                    in {"ambiguous", "individual_assessment", "partial_evidence"}
                )
            ),
            "insufficient_evidence_count": str(
                sum(
                    1
                    for item in session_interactions
                    if item.retrieval_status == "insufficient_evidence"
                )
            ),
            "sensitive_warning_shown_count": str(
                sum(
                    1
                    for item in session_interactions
                    if item.sensitive_warning_shown is True
                )
            ),
            "last_activity_at": to_iso(last_activity or study_session.started_at),
        }
        row.update(_latest_trust_values(latest_trust))
        rows.append(row)

    return rows


def build_task_summary_rows(
    study_sessions: list[StudySession],
    interactions: list[InteractionLog],
    events: list[StudyEventLog],
    feedback_logs: list[FeedbackLog],
    final_task_responses: list[FinalTaskResponse],
    evidence_uses: list[EvidenceUse],
    trust_checklists: list[TrustChecklistSnapshot],
    tasks_by_id: dict[str, dict] | None = None,
) -> list[dict[str, str]]:
    interactions_by_id = {item.id: item for item in interactions}
    interactions_by_answer_id = {item.answer_id: item for item in interactions}
    sessions_by_id = {item.session_id: item for item in study_sessions}
    tasks_by_id = tasks_by_id or study_tasks_by_id()

    def context_for(item) -> tuple[str | None, str | None]:
        return (
            _record_session_id(item, interactions_by_id, interactions_by_answer_id),
            _record_task_id(item, interactions_by_id, interactions_by_answer_id),
        )

    session_task_pairs: set[tuple[str, str]] = set()
    for item in [
        *events,
        *interactions,
        *feedback_logs,
        *final_task_responses,
        *evidence_uses,
        *trust_checklists,
    ]:
        session_id, task_id = context_for(item)
        if session_id and task_id:
            session_task_pairs.add((session_id, task_id))

    rows: list[dict[str, str]] = []
    for session_id, task_id in sorted(session_task_pairs):
        study_session = sessions_by_id.get(session_id)
        task = _task_metadata(task_id, tasks_by_id)
        task_events = [
            item
            for item in events
            if context_for(item) == (session_id, task_id)
        ]
        task_interactions = [
            item
            for item in interactions
            if context_for(item) == (session_id, task_id)
        ]
        task_finals = [
            item
            for item in final_task_responses
            if context_for(item) == (session_id, task_id)
        ]
        task_evidence = [
            item
            for item in evidence_uses
            if context_for(item) == (session_id, task_id)
        ]
        task_trust = [
            item
            for item in trust_checklists
            if context_for(item) == (session_id, task_id)
        ]
        task_started_at = _earliest_datetime(
            [
                item.created_at
                for item in task_events
                if item.event_type == "task_started"
            ]
        )
        task_completed_at = _latest_datetime(
            [
                item.created_at
                for item in task_events
                if item.event_type == "task_completed"
            ]
        )
        latest_final = latest_by_created_at(task_finals)
        latest_trust = latest_by_created_at(task_trust)
        retrieval_statuses = sorted(
            {item.retrieval_status for item in task_interactions if item.retrieval_status}
        )
        source_ids = {
            source_id
            for interaction in task_interactions
            for source_id in parse_csv_id_list(interaction.source_ids)
        }
        source_ids.update(
            item.source_id for item in task_evidence if item.source_id
        )
        chunk_ids = {
            chunk_id
            for interaction in task_interactions
            for chunk_id in parse_csv_id_list(interaction.retrieved_chunk_ids)
        }
        chunk_ids.update(item.chunk_id for item in task_evidence if item.chunk_id)
        evidence_support_average = safe_average(
            [item.evidence_support_rating for item in task_evidence]
        )

        row = {
            "session_id": session_id,
            "participant_label": (
                study_session.participant_label if study_session else ""
            ),
            "study_condition": (
                study_session.study_condition if study_session else ""
            )
            or "",
            "task_id": task_id,
            "task_title": _task_metadata_value(task, "title", task_id),
            "task_type": _task_metadata_value(task, "task_type", "unknown"),
            "task_difficulty": _task_metadata_value(task, "difficulty", "unknown"),
            "escalation_expected": _task_metadata_value(
                task, "escalation_expected", False
            ),
            "expected_safe_behaviour": _task_metadata_value(
                task, "expected_safe_behaviour"
            ),
            "prototype_notice_acknowledged": bool_to_csv(
                study_session.prototype_notice_acknowledged if study_session else None
            ),
            "task_started_at": _iso_or_empty(task_started_at),
            "task_completed_at": _iso_or_empty(task_completed_at),
            "task_duration_seconds": _number_to_csv(
                seconds_between(task_started_at, task_completed_at)
            ),
            "interaction_count": str(len(task_interactions)),
            "question_count": str(len(task_interactions)),
            "answer_count": str(len(task_interactions)),
            "retrieval_statuses": "|".join(retrieval_statuses),
            "high_stakes_detected_count": str(
                sum(1 for item in task_interactions if item.high_stakes_detected is True)
            ),
            "sensitive_warning_shown_count": str(
                sum(
                    1
                    for item in task_interactions
                    if item.sensitive_warning_shown is True
                )
            ),
            "citation_count_total": str(
                sum(item.citation_count for item in task_interactions)
            ),
            "distinct_source_count": str(len(source_ids)),
            "distinct_chunk_count": str(len(chunk_ids)),
            "evidence_action_count": str(len(task_evidence)),
            "evidence_panel_opened_count": str(
                sum(
                    1
                    for item in task_evidence
                    if item.evidence_action == "evidence_panel_opened"
                )
            ),
            "source_checked_count": str(
                sum(1 for item in task_evidence if item.evidence_action == "source_checked")
            ),
            "evidence_rating_count": str(
                sum(
                    1
                    for item in task_evidence
                    if item.evidence_support_rating is not None
                    or item.evidence_relevance_rating is not None
                )
            ),
            "average_evidence_support_rating": _number_to_csv(
                evidence_support_average
            ),
            "user_marked_helpful_count": str(
                sum(1 for item in task_evidence if item.user_marked_helpful is True)
            ),
            "user_marked_confusing_count": str(
                sum(1 for item in task_evidence if item.user_marked_confusing is True)
            ),
            "final_response_submitted": bool_to_csv(latest_final is not None),
            "final_decision_length": (
                str(len(latest_final.final_decision_text.strip()))
                if latest_final
                else ""
            ),
            "confidence_rating": (
                str(latest_final.confidence_rating) if latest_final else ""
            ),
            "would_contact_staff": (
                latest_final.would_contact_staff if latest_final else ""
            ),
            "perceived_answer_supported": (
                str(latest_final.perceived_answer_supported) if latest_final else ""
            ),
            "perceived_task_difficulty": (
                str(latest_final.perceived_task_difficulty)
                if latest_final and latest_final.perceived_task_difficulty is not None
                else ""
            ),
            "decision_appropriateness": (
                latest_final.decision_appropriateness if latest_final else ""
            )
            or "",
            "researcher_code": (
                latest_final.researcher_code if latest_final else ""
            )
            or "",
            "notes_present": bool_to_csv(
                bool(latest_final and (latest_final.notes or "").strip())
            ),
        }
        row.update(_latest_trust_values(latest_trust))
        rows.append(row)

    return rows


def build_session_summary_csv(
    study_sessions: list[StudySession],
    interactions: list[InteractionLog],
    events: list[StudyEventLog],
    feedback_logs: list[FeedbackLog],
    final_task_responses: list[FinalTaskResponse],
    evidence_uses: list[EvidenceUse],
    trust_checklists: list[TrustChecklistSnapshot],
) -> str:
    return _write_csv(
        SESSION_SUMMARY_COLUMNS,
        build_session_summary_rows(
            study_sessions,
            interactions,
            events,
            feedback_logs,
            final_task_responses,
            evidence_uses,
            trust_checklists,
        ),
    )


def build_task_summary_csv(
    study_sessions: list[StudySession],
    interactions: list[InteractionLog],
    events: list[StudyEventLog],
    feedback_logs: list[FeedbackLog],
    final_task_responses: list[FinalTaskResponse],
    evidence_uses: list[EvidenceUse],
    trust_checklists: list[TrustChecklistSnapshot],
    tasks_by_id: dict[str, dict] | None = None,
) -> str:
    return _write_csv(
        TASK_SUMMARY_COLUMNS,
        build_task_summary_rows(
            study_sessions,
            interactions,
            events,
            feedback_logs,
            final_task_responses,
            evidence_uses,
            trust_checklists,
            tasks_by_id=tasks_by_id,
        ),
    )


@router.get("/sessions", response_model=AdminSessionsResponse)
def get_admin_sessions(
    session: Session = Depends(get_session),
) -> AdminSessionsResponse:
    study_sessions = session.exec(
        select(StudySession).order_by(StudySession.started_at.desc())
    ).all()
    summaries: list[AdminSessionSummary] = []
    for study_session in study_sessions:
        (
            interactions,
            events,
            feedback_logs,
            final_responses,
            evidence_uses,
            trust_snapshots,
        ) = _session_scoped_records(session, study_session.session_id)
        summaries.append(
            _build_session_summary(
                study_session,
                interactions,
                events,
                feedback_logs,
                final_responses,
                evidence_uses,
                trust_snapshots,
            )
        )

    summaries.sort(key=lambda item: item.lastActivityAt, reverse=True)
    return AdminSessionsResponse(items=summaries)


@router.get("/sessions/{session_id}", response_model=AdminSessionDetail)
def get_admin_session_detail(
    session_id: str,
    session: Session = Depends(get_session),
) -> AdminSessionDetail:
    study_session = session.get(StudySession, session_id)
    if not study_session:
        raise HTTPException(status_code=404, detail="Study session not found")

    (
        interactions,
        events,
        feedback_logs,
        final_responses,
        evidence_uses,
        trust_snapshots,
    ) = _session_scoped_records(session, session_id)
    summary = _build_session_summary(
        study_session,
        interactions,
        events,
        feedback_logs,
        final_responses,
        evidence_uses,
        trust_snapshots,
    )

    evidence_by_interaction: dict[str, list[EvidenceUse]] = {}
    for evidence_use in evidence_uses:
        if evidence_use.interaction_id:
            evidence_by_interaction.setdefault(
                evidence_use.interaction_id,
                [],
            ).append(evidence_use)

    started_task_ids = sorted(
        {
            event.task_id
            for event in events
            if event.event_type == "task_started" and event.task_id
        }
    )
    completed_task_ids = sorted(
        {
            event.task_id
            for event in events
            if event.event_type == "task_completed" and event.task_id
        }
    )
    latest_trust_snapshot = (
        max(trust_snapshots, key=lambda item: item.created_at)
        if trust_snapshots
        else None
    )
    action_counts = Counter(item.evidence_action for item in evidence_uses)

    return AdminSessionDetail(
        summary=summary,
        taskProgress={
            "startedTaskIds": started_task_ids,
            "completedTaskIds": completed_task_ids,
        },
        interactions=[
            AdminInteractionSummary(
                interactionId=interaction.id,
                taskId=interaction.task_id,
                questionPreview=_preview_text(interaction.question),
                answerPreview=_preview_text(interaction.short_answer),
                retrievalStatus=interaction.retrieval_status,
                highStakesDetected=interaction.high_stakes_detected,
                sensitiveWarningShown=interaction.sensitive_warning_shown,
                citationCount=interaction.citation_count,
                evidenceUseCount=len(evidence_by_interaction.get(interaction.id, [])),
                sourceCheckedCount=sum(
                    1
                    for item in evidence_by_interaction.get(interaction.id, [])
                    if item.evidence_action == "source_checked"
                ),
                createdAt=to_iso(interaction.created_at),
            )
            for interaction in sorted(interactions, key=lambda item: item.created_at)
        ],
        evidenceUseSummary=[
            AdminEvidenceUseSummary(evidenceAction=action, count=count)
            for action, count in sorted(action_counts.items())
        ],
        latestTrustChecklist=_trust_summary(latest_trust_snapshot),
        finalResponses=[
            AdminFinalResponseSummary(
                responseId=response.response_id,
                taskId=response.task_id,
                interactionId=response.interaction_id,
                finalDecisionLength=len(response.final_decision_text.strip()),
                finalDecisionPreview=_preview_text(response.final_decision_text),
                confidenceRating=response.confidence_rating,
                wouldContactStaff=response.would_contact_staff,
                perceivedAnswerSupported=response.perceived_answer_supported,
                createdAt=to_iso(response.created_at),
            )
            for response in sorted(final_responses, key=lambda item: item.created_at)
        ],
        feedback=[
            AdminFeedbackSummary(
                feedbackId=feedback.id,
                taskId=(
                    next(
                        (
                            interaction.task_id
                            for interaction in interactions
                            if interaction.id == feedback.interaction_id
                        ),
                        None,
                    )
                    or feedback.task_id
                ),
                interactionId=feedback.interaction_id,
                rating=feedback.rating,
                commentLength=len(feedback.comment or ""),
                createdAt=to_iso(feedback.created_at),
            )
            for feedback in sorted(feedback_logs, key=lambda item: item.created_at)
        ],
        eventTimeline=[
            AdminEventTimelineItem(
                eventId=event.id,
                eventType=event.event_type,
                taskId=event.task_id,
                interactionId=event.interaction_id,
                metadataKeys=_metadata_keys(event.metadata_json),
                createdAt=to_iso(event.created_at),
            )
            for event in sorted(events, key=lambda item: item.created_at)
        ],
    )


@router.get("/tasks", response_model=AdminTasksResponse)
def get_admin_tasks(
    session: Session = Depends(get_session),
) -> AdminTasksResponse:
    tasks_by_id = study_tasks_by_id()
    events = session.exec(select(StudyEventLog)).all()
    final_responses = session.exec(select(FinalTaskResponse)).all()
    evidence_uses = session.exec(select(EvidenceUse)).all()
    trust_snapshots = session.exec(select(TrustChecklistSnapshot)).all()

    sessions_started_by_task: dict[str, set[str]] = {}
    sessions_completed_by_task: dict[str, set[str]] = {}
    for event in events:
        if not event.task_id or not event.session_id:
            continue
        if event.event_type == "task_started":
            sessions_started_by_task.setdefault(event.task_id, set()).add(
                event.session_id
            )
        if event.event_type == "task_completed":
            sessions_completed_by_task.setdefault(event.task_id, set()).add(
                event.session_id
            )

    confidence_by_task: dict[str, list[int]] = {}
    contact_counts_by_task: dict[str, Counter] = {}
    for final_response in final_responses:
        confidence_by_task.setdefault(final_response.task_id, []).append(
            final_response.confidence_rating
        )
        contact_counts_by_task.setdefault(final_response.task_id, Counter()).update(
            [final_response.would_contact_staff]
        )

    evidence_count_by_task = Counter(
        item.task_id for item in evidence_uses if item.task_id
    )
    trust_snapshot_count_by_task = Counter(
        item.task_id for item in trust_snapshots if item.task_id
    )
    trust_checklist_keys_by_task: dict[str, set[str]] = {}
    for item in trust_snapshots:
        if not item.task_id:
            continue
        checklist_key = (
            item.session_id
            or item.interaction_id
            or item.participant_label
            or item.trust_snapshot_id
        )
        trust_checklist_keys_by_task.setdefault(item.task_id, set()).add(checklist_key)

    items: list[AdminTaskSummary] = []
    for task_id, task in sorted(tasks_by_id.items()):
        confidence_values = confidence_by_task.get(task_id, [])
        contact_counts = contact_counts_by_task.get(task_id, Counter())
        items.append(
            AdminTaskSummary(
                taskId=task_id,
                title=str(task.get("title") or task_id),
                taskType=str(task.get("task_type") or ""),
                difficulty=str(task.get("difficulty") or ""),
                escalationExpected=bool(task.get("escalation_expected")),
                sessionsStartedCount=len(sessions_started_by_task.get(task_id, set())),
                sessionsCompletedCount=len(
                    sessions_completed_by_task.get(task_id, set())
                ),
                finalResponseCount=sum(
                    1 for item in final_responses if item.task_id == task_id
                ),
                averageConfidence=(
                    round(sum(confidence_values) / len(confidence_values), 2)
                    if confidence_values
                    else None
                ),
                contactStaffYesCount=contact_counts.get("yes", 0),
                contactStaffNoCount=contact_counts.get("no", 0),
                contactStaffUnsureCount=contact_counts.get("not_sure", 0),
                evidenceUseCount=evidence_count_by_task.get(task_id, 0),
                trustChecklistCount=len(
                    trust_checklist_keys_by_task.get(task_id, set())
                ),
                trustSnapshotCount=trust_snapshot_count_by_task.get(task_id, 0),
            )
        )

    known_task_ids = set(tasks_by_id)
    for task_id in sorted(
        {
            *sessions_started_by_task.keys(),
            *sessions_completed_by_task.keys(),
            *confidence_by_task.keys(),
            *evidence_count_by_task.keys(),
            *trust_snapshot_count_by_task.keys(),
        }
        - known_task_ids
    ):
        confidence_values = confidence_by_task.get(task_id, [])
        contact_counts = contact_counts_by_task.get(task_id, Counter())
        items.append(
            AdminTaskSummary(
                taskId=task_id,
                title=task_id,
                taskType="unknown",
                difficulty="unknown",
                escalationExpected=False,
                sessionsStartedCount=len(sessions_started_by_task.get(task_id, set())),
                sessionsCompletedCount=len(
                    sessions_completed_by_task.get(task_id, set())
                ),
                finalResponseCount=sum(
                    1 for item in final_responses if item.task_id == task_id
                ),
                averageConfidence=(
                    round(sum(confidence_values) / len(confidence_values), 2)
                    if confidence_values
                    else None
                ),
                contactStaffYesCount=contact_counts.get("yes", 0),
                contactStaffNoCount=contact_counts.get("no", 0),
                contactStaffUnsureCount=contact_counts.get("not_sure", 0),
                evidenceUseCount=evidence_count_by_task.get(task_id, 0),
                trustChecklistCount=len(
                    trust_checklist_keys_by_task.get(task_id, set())
                ),
                trustSnapshotCount=trust_snapshot_count_by_task.get(task_id, 0),
            )
        )

    return AdminTasksResponse(items=items)


@router.get("/logs", response_model=AdminLogsResponse)
def get_admin_logs(
    limit: int = Query(100, ge=1, le=500),
    session: Session = Depends(get_session),
) -> AdminLogsResponse:
    logs = session.exec(
        select(InteractionLog)
        .order_by(InteractionLog.created_at.desc())
        .limit(limit)
    ).all()
    tasks_by_id = study_tasks_by_id()
    sessions_by_id = {
        item.session_id: item
        for item in session.exec(select(StudySession)).all()
    }
    final_responses_by_context: dict[tuple[str, str], FinalTaskResponse] = {}
    for final_response in session.exec(
        select(FinalTaskResponse).order_by(FinalTaskResponse.created_at.asc())
    ).all():
        final_responses_by_context[
            (final_response.session_id, final_response.task_id)
        ] = final_response

    evidence_uses_by_interaction: dict[str, list[EvidenceUse]] = {}
    for evidence_use in session.exec(select(EvidenceUse)).all():
        if evidence_use.interaction_id:
            evidence_uses_by_interaction.setdefault(
                evidence_use.interaction_id,
                [],
            ).append(evidence_use)

    trust_snapshots_by_interaction: dict[str, TrustChecklistSnapshot] = {}
    for snapshot in session.exec(
        select(TrustChecklistSnapshot).order_by(
            TrustChecklistSnapshot.created_at.asc()
        )
    ).all():
        if snapshot.interaction_id:
            trust_snapshots_by_interaction[snapshot.interaction_id] = snapshot

    items: list[AdminLogItem] = []
    for log in logs:
        study_session = sessions_by_id.get(log.session_id or "")
        task = tasks_by_id.get(log.task_id or "", {})
        final_response = final_responses_by_context.get(
            (log.session_id or "", log.task_id or "")
        )
        evidence_uses = evidence_uses_by_interaction.get(log.id, [])
        latest_trust_snapshot = trust_snapshots_by_interaction.get(log.id)
        items.append(
            AdminLogItem(
                id=log.id,
                sessionId=log.session_id,
                participantLabel=log.participant_label,
                studyCondition=study_session.study_condition if study_session else None,
                participantId=log.participant_id,
                taskId=log.task_id,
                taskTitle=task.get("title"),
                taskType=task.get("task_type"),
                taskDifficulty=task.get("difficulty"),
                escalationExpected=task.get("escalation_expected"),
                condition=log.condition,
                question=log.question,
                answerId=log.answer_id,
                shortAnswer=log.short_answer,
                fullAnswer=log.full_answer or log.short_answer,
                basedOn=log.based_on,
                limitations=log.limitations,
                uncertainty=log.uncertainty,
                escalationGuidance=log.escalation_guidance,
                highStakesDetected=log.high_stakes_detected,
                uncertaintyLevel=log.uncertainty_level,
                escalationRecommended=log.escalation_recommended,
                escalationCategory=log.escalation_category,
                escalationReasons=_chunk_ids(log.escalation_reasons_json),
                citationCount=log.citation_count,
                retrievalStatus=log.retrieval_status,
                citationIds=_chunk_ids(log.citation_ids),
                citations=_json_object_list(log.citations_json),
                sourceIds=_chunk_ids(log.source_ids),
                retrievedChunkIds=_chunk_ids(log.retrieved_chunk_ids),
                retrievalTrace=_json_object_list(log.retrieval_trace_json),
                retrievedContextCount=log.retrieved_context_count,
                escalationGuidancePresent=log.escalation_guidance_present,
                sensitiveWarningShown=log.sensitive_warning_shown,
                createdAt=to_iso(log.created_at),
                timeToFirstAnswerMs=log.time_to_first_answer_ms,
                responseTimeMs=log.response_time_ms,
                errorType=log.error_type,
                embeddingProvider=log.embedding_provider,
                embeddingModel=log.embedding_model,
                embeddingDimension=log.embedding_dimension,
                vectorCollection=log.vector_collection,
                retrievalPartialThreshold=log.retrieval_partial_threshold,
                retrievalGroundedThreshold=log.retrieval_grounded_threshold,
                retrievalTopK=log.retrieval_top_k,
                retrievalMode=log.retrieval_mode,
                scopeDecision=log.scope_decision,
                scopeRegistryVersion=log.scope_registry_version,
                scopeRegistryFingerprint=log.scope_registry_fingerprint,
                scopeMatchedTopics=_chunk_ids(log.scope_matched_topics),
                corpusManifestFingerprint=log.corpus_manifest_fingerprint,
                aiProvider=log.ai_provider,
                aiModel=log.ai_model,
                aiModelRequested=log.ai_model_requested,
                providerResponseModel=log.provider_response_model,
                providerResponseId=log.provider_response_id,
                inputTokens=log.input_tokens,
                outputTokens=log.output_tokens,
                totalTokens=log.total_tokens,
                tokenUsage=_json_object(log.token_usage_json),
                answerMode=log.answer_mode,
                taskVersion=log.task_version,
                appVersion=log.app_version,
                appRevision=log.app_revision or log.app_version,
                executionContext=log.execution_context,
                answerStrategyVersion=log.answer_strategy_version,
                releaseId=log.release_id,
                releaseVersion=log.release_version,
                conditionId=log.condition_id,
                conditionVersion=log.condition_version,
                taskManifestVersion=log.task_manifest_version,
                runtimeConfigFingerprint=log.runtime_config_fingerprint,
                runtimeConfig=_json_object(log.runtime_config_json),
                promptTemplateVersion=log.prompt_template_version,
                generationTemperature=log.generation_temperature,
                generationMaxTokens=log.generation_max_tokens,
                finalResponseId=(
                    final_response.response_id if final_response else None
                ),
                finalResponseSubmitted=final_response is not None,
                finalDecisionLength=(
                    len(final_response.final_decision_text.strip())
                    if final_response
                    else None
                ),
                confidenceRating=(
                    final_response.confidence_rating if final_response else None
                ),
                wouldContactStaff=(
                    final_response.would_contact_staff if final_response else None
                ),
                perceivedAnswerSupported=(
                    final_response.perceived_answer_supported
                    if final_response
                    else None
                ),
                finalResponseCreatedAt=(
                    to_iso(final_response.created_at) if final_response else None
                ),
                evidenceUseCount=len(evidence_uses),
                sourceCheckedCount=sum(
                    1
                    for evidence_use in evidence_uses
                    if evidence_use.evidence_action == "source_checked"
                ),
                latestTrustAnswerClear=(
                    latest_trust_snapshot.answer_clear
                    if latest_trust_snapshot
                    else None
                ),
                latestTrustEvidenceChecked=(
                    latest_trust_snapshot.evidence_checked
                    if latest_trust_snapshot
                    else None
                ),
                latestTrustSourceSupportsAnswer=(
                    latest_trust_snapshot.source_supports_answer
                    if latest_trust_snapshot
                    else None
                ),
                latestTrustUncertaintyNoticed=(
                    latest_trust_snapshot.uncertainty_noticed
                    if latest_trust_snapshot
                    else None
                ),
                latestTrustWouldContactStaffIfNeeded=(
                    latest_trust_snapshot.would_contact_staff_if_needed
                    if latest_trust_snapshot
                    else None
                ),
            )
        )

    return AdminLogsResponse(items=items)


@router.get("/logs/export.csv")
def export_admin_logs_csv(
    session: Session = Depends(get_session),
) -> Response:
    # TODO: Protect this local research prototype endpoint before deployment.
    interactions = session.exec(
        select(InteractionLog).order_by(InteractionLog.created_at.asc())
    ).all()
    events = session.exec(
        select(StudyEventLog).order_by(StudyEventLog.created_at.asc())
    ).all()
    feedback_logs = session.exec(
        select(FeedbackLog).order_by(FeedbackLog.created_at.asc())
    ).all()
    final_task_responses = session.exec(
        select(FinalTaskResponse).order_by(FinalTaskResponse.created_at.asc())
    ).all()
    evidence_uses = session.exec(
        select(EvidenceUse).order_by(EvidenceUse.created_at.asc())
    ).all()
    trust_checklists = session.exec(
        select(TrustChecklistSnapshot).order_by(
            TrustChecklistSnapshot.created_at.asc()
        )
    ).all()
    study_sessions = session.exec(
        select(StudySession).order_by(StudySession.started_at.asc())
    ).all()
    csv_content = build_research_logs_csv(
        interactions,
        events,
        feedback_logs,
        final_task_responses=final_task_responses,
        evidence_uses=evidence_uses,
        trust_checklists=trust_checklists,
        study_sessions=study_sessions,
        tasks_by_id=study_tasks_by_id(),
    )

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="uni_navigator_logs.csv"'
        },
    )


def _all_research_records(
    session: Session,
) -> tuple[
    list[InteractionLog],
    list[StudyEventLog],
    list[FeedbackLog],
    list[FinalTaskResponse],
    list[EvidenceUse],
    list[TrustChecklistSnapshot],
    list[StudySession],
]:
    interactions = session.exec(
        select(InteractionLog).order_by(InteractionLog.created_at.asc())
    ).all()
    events = session.exec(
        select(StudyEventLog).order_by(StudyEventLog.created_at.asc())
    ).all()
    feedback_logs = session.exec(
        select(FeedbackLog).order_by(FeedbackLog.created_at.asc())
    ).all()
    final_task_responses = session.exec(
        select(FinalTaskResponse).order_by(FinalTaskResponse.created_at.asc())
    ).all()
    evidence_uses = session.exec(
        select(EvidenceUse).order_by(EvidenceUse.created_at.asc())
    ).all()
    trust_checklists = session.exec(
        select(TrustChecklistSnapshot).order_by(
            TrustChecklistSnapshot.created_at.asc()
        )
    ).all()
    study_sessions = session.exec(
        select(StudySession).order_by(StudySession.started_at.asc())
    ).all()
    return (
        interactions,
        events,
        feedback_logs,
        final_task_responses,
        evidence_uses,
        trust_checklists,
        study_sessions,
    )


@router.get("/export/session-summary.csv")
def export_session_summary_csv(
    session: Session = Depends(get_session),
) -> Response:
    (
        interactions,
        events,
        feedback_logs,
        final_task_responses,
        evidence_uses,
        trust_checklists,
        study_sessions,
    ) = _all_research_records(session)
    csv_content = build_session_summary_csv(
        study_sessions,
        interactions,
        events,
        feedback_logs,
        final_task_responses,
        evidence_uses,
        trust_checklists,
    )

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="uni_navigator_session_summary.csv"'
            )
        },
    )


@router.get("/export/task-summary.csv")
def export_task_summary_csv(
    session: Session = Depends(get_session),
) -> Response:
    (
        interactions,
        events,
        feedback_logs,
        final_task_responses,
        evidence_uses,
        trust_checklists,
        study_sessions,
    ) = _all_research_records(session)
    csv_content = build_task_summary_csv(
        study_sessions,
        interactions,
        events,
        feedback_logs,
        final_task_responses,
        evidence_uses,
        trust_checklists,
        tasks_by_id=study_tasks_by_id(),
    )

    return Response(
        content=csv_content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (
                'attachment; filename="uni_navigator_task_summary.csv"'
            )
        },
    )


@router.get("/corpus/status")
def get_admin_corpus_status() -> dict:
    return get_corpus_status()


@router.get("/pilot/preflight")
def get_pilot_preflight() -> dict:
    from app.config import get_settings
    from app.services.pilot_preflight_service import run_pilot_preflight

    return run_pilot_preflight(get_settings(), session_labels=[]).to_dict()
