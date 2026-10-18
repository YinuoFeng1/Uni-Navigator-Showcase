import csv
from io import StringIO

from sqlmodel import Session, select

from app.database import engine
from app.models import EvidenceUse, FinalTaskResponse, StudyEventLog, TrustChecklistSnapshot


def _csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(text)))


def _start_session(client) -> dict:
    response = client.post(
        "/api/study/session/start",
        json={
            "participantLabel": "P-EVIDENCE-001",
            "studyCondition": "C_HIGHLIGHT",
        },
    )
    assert response.status_code == 200
    return response.json()


def _chat(client, session_id: str, task_id: str) -> dict:
    response = client.post(
        "/api/chat",
        json={
            "sessionId": session_id,
            "participantLabel": "P-EVIDENCE-001",
            "participantId": "P-EVIDENCE-001",
            "taskId": task_id,
            "condition": "C_HIGHLIGHT",
            "question": "If I withdraw after census date, could there be fee consequences?",
        },
    )
    assert response.status_code == 200
    return response.json()


def test_submitting_evidence_use_event_succeeds(client) -> None:
    session_data = _start_session(client)

    response = client.post(
        "/api/study/evidence-use",
        json={
            "sessionId": session_data["sessionId"],
            "taskId": "task_withdrawal_census_penalty",
            "evidenceAction": "evidence_rating_submitted",
            "citationId": "c1",
            "sourceId": "prepared-course-withdrawal-census",
            "chunkId": "prepared_course_withdrawal_census_chunk_0000",
            "evidenceSupportRating": 4,
            "userMarkedHelpful": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["evidenceUseId"].startswith("evidence_use_")
    assert response.json()["createdAt"]


def test_evidence_use_rating_validation_works(client) -> None:
    response = client.post(
        "/api/study/evidence-use",
        json={
            "evidenceAction": "evidence_rating_submitted",
            "evidenceSupportRating": 6,
        },
    )

    assert response.status_code == 422


def test_evidence_use_row_and_study_event_are_created(client) -> None:
    session_data = _start_session(client)
    task_id = "task_withdrawal_census_penalty"
    chat_data = _chat(client, session_data["sessionId"], task_id)

    response = client.post(
        "/api/study/evidence-use",
        json={
            "sessionId": session_data["sessionId"],
            "participantLabel": "P-EVIDENCE-001",
            "taskId": task_id,
            "interactionId": chat_data["interactionId"],
            "citationId": "c1",
            "sourceId": "prepared-course-withdrawal-census",
            "chunkId": "prepared_course_withdrawal_census_chunk_0000",
            "evidenceAction": "source_checked",
            "evidenceRelevanceRating": 5,
            "evidenceSupportRating": 4,
            "userMarkedHelpful": True,
            "userMarkedConfusing": False,
            "notes": "Useful policy passage.",
        },
    )

    assert response.status_code == 200
    evidence_use_id = response.json()["evidenceUseId"]
    with Session(engine) as db_session:
        evidence_use = db_session.get(EvidenceUse, evidence_use_id)
        event = db_session.exec(
            select(StudyEventLog).where(
                StudyEventLog.session_id == session_data["sessionId"],
                StudyEventLog.interaction_id == chat_data["interactionId"],
                StudyEventLog.event_type == "source_checked",
            )
        ).first()

    assert evidence_use is not None
    assert evidence_use.participant_label == "P-EVIDENCE-001"
    assert evidence_use.evidence_support_rating == 4
    assert evidence_use.user_marked_helpful is True
    assert evidence_use.user_marked_confusing is False
    assert event is not None
    assert evidence_use_id in (event.metadata_json or "")


def test_submitting_trust_checklist_snapshot_succeeds(client) -> None:
    session_data = _start_session(client)

    response = client.post(
        "/api/study/trust-checklist",
        json={
            "sessionId": session_data["sessionId"],
            "taskId": "task_withdrawal_census_penalty",
            "answerClear": True,
            "evidenceChecked": True,
            "sourceSupportsAnswer": True,
            "uncertaintyNoticed": False,
            "wouldContactStaffIfNeeded": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["trustSnapshotId"].startswith("trust_snapshot_")
    assert response.json()["createdAt"]


def test_trust_checklist_snapshot_row_and_study_event_are_created(client) -> None:
    session_data = _start_session(client)
    task_id = "task_academic_progression_notice"
    chat_data = _chat(client, session_data["sessionId"], task_id)

    response = client.post(
        "/api/study/trust-checklist",
        json={
            "sessionId": session_data["sessionId"],
            "participantLabel": "P-EVIDENCE-001",
            "taskId": task_id,
            "interactionId": chat_data["interactionId"],
            "answerClear": True,
            "evidenceChecked": True,
            "sourceSupportsAnswer": False,
            "uncertaintyNoticed": True,
            "wouldContactStaffIfNeeded": True,
        },
    )

    assert response.status_code == 200
    snapshot_id = response.json()["trustSnapshotId"]
    with Session(engine) as db_session:
        snapshot = db_session.get(TrustChecklistSnapshot, snapshot_id)
        event = db_session.exec(
            select(StudyEventLog).where(
                StudyEventLog.session_id == session_data["sessionId"],
                StudyEventLog.interaction_id == chat_data["interactionId"],
                StudyEventLog.event_type == "trust_check_updated",
            )
        ).first()

    assert snapshot is not None
    assert snapshot.participant_label == "P-EVIDENCE-001"
    assert snapshot.source_supports_answer is False
    assert snapshot.uncertainty_noticed is True
    assert event is not None
    assert snapshot_id in (event.metadata_json or "")


def test_csv_export_includes_evidence_use_and_trust_checklist_rows(client) -> None:
    session_data = _start_session(client)
    task_id = "task_withdrawal_census_penalty"
    chat_data = _chat(client, session_data["sessionId"], task_id)
    evidence_response = client.post(
        "/api/study/evidence-use",
        json={
            "sessionId": session_data["sessionId"],
            "participantLabel": "P-EVIDENCE-001",
            "taskId": task_id,
            "interactionId": chat_data["interactionId"],
            "citationId": "c1",
            "sourceId": "prepared-course-withdrawal-census",
            "chunkId": "prepared_course_withdrawal_census_chunk_0000",
            "evidenceAction": "evidence_rating_submitted",
            "evidenceSupportRating": 5,
            "userMarkedHelpful": True,
            "userMarkedConfusing": False,
            "notes": "This supported the answer.",
        },
    )
    trust_response = client.post(
        "/api/study/trust-checklist",
        json={
            "sessionId": session_data["sessionId"],
            "participantLabel": "P-EVIDENCE-001",
            "taskId": task_id,
            "interactionId": chat_data["interactionId"],
            "answerClear": True,
            "evidenceChecked": True,
            "sourceSupportsAnswer": True,
            "uncertaintyNoticed": True,
            "wouldContactStaffIfNeeded": True,
        },
    )
    assert evidence_response.status_code == 200
    assert trust_response.status_code == 200

    export_response = client.get("/api/admin/logs/export.csv")
    rows = _csv_rows(export_response.text)
    evidence_row = next(row for row in rows if row["row_type"] == "evidence_use")
    trust_row = next(row for row in rows if row["row_type"] == "trust_checklist")

    assert evidence_row["evidence_use_id"] == evidence_response.json()["evidenceUseId"]
    assert evidence_row["session_id"] == session_data["sessionId"]
    assert evidence_row["participant_label"] == "P-EVIDENCE-001"
    assert evidence_row["task_id"] == task_id
    assert evidence_row["task_title"] == "Withdrawal timing and academic penalty"
    assert evidence_row["evidence_action"] == "evidence_rating_submitted"
    assert evidence_row["citation_id"] == "c1"
    assert evidence_row["source_id"] == "prepared-course-withdrawal-census"
    assert evidence_row["evidence_support_rating"] == "5"
    assert evidence_row["user_marked_helpful"] == "true"
    assert evidence_row["user_marked_confusing"] == "false"
    assert evidence_row["evidence_use_notes"] == "This supported the answer."
    assert evidence_row["evidence_use_created_at"]

    assert trust_row["trust_snapshot_id"] == trust_response.json()["trustSnapshotId"]
    assert trust_row["answer_clear"] == "true"
    assert trust_row["evidence_checked"] == "true"
    assert trust_row["source_supports_answer"] == "true"
    assert trust_row["uncertainty_noticed"] == "true"
    assert trust_row["would_contact_staff_if_needed"] == "true"
    assert trust_row["trust_snapshot_created_at"]


def test_old_study_events_still_export_with_blank_new_fields(client) -> None:
    response = client.post(
        "/api/study/log-event",
        json={
            "participantId": "P-OLD",
            "taskId": "T-OLD",
            "condition": "C_HIGHLIGHT",
            "eventType": "source_checked",
            "metadata": {"checkedSource": True},
        },
    )
    assert response.status_code == 200

    export_response = client.get("/api/admin/logs/export.csv")
    rows = _csv_rows(export_response.text)
    event_row = next(row for row in rows if row["row_type"] == "event")
    assert event_row["checked_source"] == "true"
    assert event_row["evidence_use_id"] == ""
    assert event_row["trust_snapshot_id"] == ""


def test_chat_and_final_response_flow_still_work(client) -> None:
    session_data = _start_session(client)
    task_id = "task_withdrawal_census_penalty"
    chat_data = _chat(client, session_data["sessionId"], task_id)

    response = client.post(
        "/api/study/task/final-response",
        json={
            "sessionId": session_data["sessionId"],
            "taskId": task_id,
            "interactionId": chat_data["interactionId"],
            "finalDecisionText": "I would check evidence and contact staff if needed.",
            "confidenceRating": 4,
            "wouldContactStaff": "not_sure",
            "perceivedAnswerSupported": 4,
        },
    )

    assert response.status_code == 200
    with Session(engine) as db_session:
        final_response = db_session.get(FinalTaskResponse, response.json()["responseId"])
    assert final_response is not None
    assert final_response.would_contact_staff == "not_sure"
