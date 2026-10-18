"""Filtered exports for Chat study sessions; historical exports stay unchanged."""

import csv
import io
import json
from collections import Counter
from typing import Literal

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, select

from app.database import get_session
from app.models import FeedbackLog, InteractionLog, StudyEventLog, StudySession
from app.services.chat_session_service import is_chat_session, session_metadata
from app.utils.time import to_iso

router = APIRouter()
COMMON = ["round_id", "participant_code", "session_id", "execution_context"]
SUMMARY = COMMON + [
    "started_at", "completed_at", "state", "duration_seconds", "question_count",
    "answer_count", "citation_click_count", "evidence_open_count", "source_open_count",
    "source_checked_count", "feedback_count", "error_count", "runtime_config_fingerprint",
]
TIMELINE = COMMON + [
    "event_id", "occurred_at", "recorded_at", "elapsed_seconds", "event_type",
    "interaction_id", "citation_id", "source_id", "chunk_id", "metadata_json",
]
ANSWERS = COMMON + [
    "interaction_id", "created_at", "question", "answer", "based_on", "limitations",
    "uncertainty", "escalation_recommended", "escalation_category", "escalation_guidance",
    "citations_json", "retrieval_trace_json", "response_time_ms", "error_type",
    "ai_model", "prompt_template_version", "corpus_manifest_fingerprint",
    "runtime_config_fingerprint", "runtime_config_json", "feedback_json",
]
ERROR_EVENTS = {
    "system_failure", "provider_unavailable", "vector_store_unavailable",
    "provenance_write_failed", "release_component_mismatch", "client_context_mismatch",
    "invalid_state_transition", "release_not_frozen", "release_retired",
}


def filtered_sessions(db: Session, round_id: str | None, participant: str | None):
    query = select(StudySession).order_by(StudySession.started_at)
    if participant:
        query = query.where(StudySession.participant_label == participant)
    return [s for s in db.exec(query).all() if is_chat_session(s)
            and (not round_id or session_metadata(s).get("roundId") == round_id)]


def records(db: Session, model, session_id: str):
    return db.exec(select(model).where(model.session_id == session_id)).all()


def common(s: StudySession):
    meta = session_metadata(s)
    return {"round_id": meta.get("roundId"), "participant_code": s.participant_label,
            "session_id": s.session_id, "execution_context": meta.get("executionContext")}


def summary(db: Session, s: StudySession):
    counts = Counter(e.event_type for e in records(db, StudyEventLog, s.session_id))
    return {
        **common(s), "started_at": to_iso(s.started_at),
        "completed_at": to_iso(s.completed_at) if s.completed_at else "", "state": s.state,
        "duration_seconds": round((s.completed_at - s.started_at).total_seconds(), 3) if s.completed_at else "",
        "question_count": counts["question_submitted"],
        "answer_count": len(records(db, InteractionLog, s.session_id)),
        "citation_click_count": counts["citation_clicked"],
        "evidence_open_count": counts["evidence_opened"], "source_open_count": counts["source_opened"],
        "source_checked_count": counts["source_checked"],
        "feedback_count": len(records(db, FeedbackLog, s.session_id)),
        "error_count": sum(counts[k] for k in ERROR_EVENTS),
        "runtime_config_fingerprint": s.runtime_config_fingerprint,
    }


@router.get("/research/sessions")
def list_research_sessions(round_id: str | None = None, participant: str | None = None,
                           db: Session = Depends(get_session)):
    return {"items": [summary(db, s) for s in filtered_sessions(db, round_id, participant)]}


def safe_cell(value):
    value = "" if value is None else str(value)
    # Spreadsheet programs must not execute participant text as formulas.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else value


@router.get("/research/export/{kind}.csv")
def export_research(kind: Literal["participants", "timeline", "answers"],
                    round_id: str | None = None, participant: str | None = None,
                    db: Session = Depends(get_session)):
    rows = []
    for s in filtered_sessions(db, round_id, participant):
        base = common(s)
        if kind == "participants":
            rows.append(summary(db, s))
        elif kind == "timeline":
            for event in records(db, StudyEventLog, s.session_id):
                meta = json.loads(event.metadata_json or "{}")
                occurred = event.occurred_at or event.created_at
                rows.append({
                    **base, "event_id": event.id, "occurred_at": to_iso(occurred),
                    "recorded_at": to_iso(event.recorded_at or event.created_at),
                    "elapsed_seconds": round((occurred - s.started_at).total_seconds(), 3),
                    "event_type": event.event_type, "interaction_id": event.interaction_id,
                    "citation_id": meta.get("citationId"), "source_id": meta.get("sourceId"),
                    "chunk_id": meta.get("chunkId"), "metadata_json": event.metadata_json,
                })
        else:
            feedback = records(db, FeedbackLog, s.session_id)
            for item in records(db, InteractionLog, s.session_id):
                if item.technical_run_id or item.execution_context == "technical_evaluation":
                    continue
                row = {key: getattr(item, key, None) for key in ANSWERS}
                row.update(base)
                row.update({"interaction_id": item.id, "created_at": to_iso(item.created_at),
                            "answer": item.full_answer or item.short_answer,
                            "feedback_json": json.dumps([
                                {"rating": f.rating, "comment": f.comment, "created_at": to_iso(f.created_at)}
                                for f in feedback if f.interaction_id == item.id
                            ], ensure_ascii=False)})
                rows.append(row)
    if kind == "timeline":
        rows.sort(key=lambda r: (r["occurred_at"], r["event_id"]))
    elif kind == "answers":
        rows.sort(key=lambda r: (r["created_at"], r["interaction_id"]))
    columns = {"participants": SUMMARY, "timeline": TIMELINE, "answers": ANSWERS}[kind]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()
    writer.writerows({key: safe_cell(row.get(key)) for key in columns} for row in rows)
    return Response("\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="uni_navigator_{kind}.csv"'})
