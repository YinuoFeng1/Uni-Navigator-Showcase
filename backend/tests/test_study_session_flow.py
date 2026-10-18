import csv
import json
from io import StringIO

from sqlmodel import Session, select

from app.database import engine
from app.models import InteractionLog, StudyEventLog, StudySession


def _csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(text)))


def _start_session(client) -> dict:
    response = client.post(
        "/api/study/session/start",
        json={
            "participantLabel": "P-STUDY-001",
            "studyCondition": "C_HIGHLIGHT",
            "metadata": {"cohort": "pilot"},
        },
    )
    assert response.status_code == 200
    return response.json()


def test_starting_and_completing_study_session(client) -> None:
    session_data = _start_session(client)

    assert session_data["sessionId"].startswith("session_")
    assert session_data["participantLabel"] == "P-STUDY-001"
    assert session_data["studyCondition"] == "C_HIGHLIGHT"
    assert session_data["completedAt"] is None
    assert session_data["prototypeNoticeAcknowledged"] is None

    complete_response = client.post(
        "/api/study/session/complete",
        json={"sessionId": session_data["sessionId"]},
    )

    assert complete_response.status_code == 200
    completed = complete_response.json()
    assert completed["sessionId"] == session_data["sessionId"]
    assert completed["completedAt"] is not None
    assert completed["currentTaskId"] is None


def test_starting_session_stores_prototype_notice_acknowledgement(client) -> None:
    response = client.post(
        "/api/study/session/start",
        json={
            "participantLabel": "P-ETHICS-001",
            "studyCondition": "C_HIGHLIGHT",
            "prototypeNoticeAcknowledged": True,
            "metadata": {"source": "test"},
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["prototypeNoticeAcknowledged"] is True
    assert data["prototypeNoticeAcknowledgedAt"]

    with Session(engine) as db_session:
        study_session = db_session.get(StudySession, data["sessionId"])

    assert study_session is not None
    assert study_session.prototype_notice_acknowledged is True
    assert study_session.prototype_notice_acknowledged_at is not None


def test_listing_and_reading_study_tasks(client) -> None:
    list_response = client.get("/api/study/tasks")

    assert list_response.status_code == 200
    tasks = list_response.json()["items"]
    assert len(tasks) >= 5
    first_task = tasks[0]
    assert first_task["taskId"]
    assert first_task["taskType"]
    assert first_task["difficulty"] in {"easy", "medium", "hard"}
    assert isinstance(first_task["escalationExpected"], bool)

    detail_response = client.get(f"/api/study/tasks/{first_task['taskId']}")
    assert detail_response.status_code == 200
    assert detail_response.json()["taskId"] == first_task["taskId"]


def test_starting_and_completing_task_in_session_logs_events(client) -> None:
    session_data = _start_session(client)
    task_id = "task_withdrawal_census_penalty"

    start_response = client.post(
        "/api/study/session/task/start",
        json={
            "sessionId": session_data["sessionId"],
            "taskId": task_id,
            "preConfidence": 4,
        },
    )
    assert start_response.status_code == 200
    assert start_response.json()["status"] == "started"
    assert start_response.json()["currentTaskId"] == task_id

    session_response = client.get(f"/api/study/session/{session_data['sessionId']}")
    assert session_response.status_code == 200
    assert session_response.json()["currentTaskId"] == task_id
    assert task_id in session_response.json()["taskProgress"]["startedTaskIds"]

    complete_response = client.post(
        "/api/study/session/task/complete",
        json={"sessionId": session_data["sessionId"], "taskId": task_id},
    )
    assert complete_response.status_code == 200
    assert complete_response.json()["status"] == "completed"
    assert complete_response.json()["currentTaskId"] is None

    with Session(engine) as db_session:
        events = db_session.exec(
            select(StudyEventLog).where(StudyEventLog.session_id == session_data["sessionId"])
        ).all()
    event_types = {event.event_type for event in events}
    assert {"task_started", "task_completed"}.issubset(event_types)
    started_event = next(event for event in events if event.event_type == "task_started")
    assert json.loads(started_event.metadata_json or "{}")["preConfidence"] == 4


def test_log_event_accepts_session_and_task(client) -> None:
    session_data = _start_session(client)
    task_id = "task_special_consideration_illness"

    response = client.post(
        "/api/study/log-event",
        json={
            "sessionId": session_data["sessionId"],
            "participantLabel": "P-STUDY-001",
            "participantId": "P-STUDY-001",
            "taskId": task_id,
            "condition": "C_HIGHLIGHT",
            "eventType": "source_checked",
            "metadata": {"checkedSource": True},
        },
    )

    assert response.status_code == 200
    with Session(engine) as db_session:
        event = db_session.get(StudyEventLog, response.json()["eventId"])
    assert event is not None
    assert event.session_id == session_data["sessionId"]
    assert event.participant_label == "P-STUDY-001"
    assert event.task_id == task_id


def test_chat_still_works_without_session_or_task(client) -> None:
    response = client.post("/api/chat", json={"question": "When should I contact staff?"})

    assert response.status_code == 200
    data = response.json()
    assert data["interactionId"].startswith("interaction_")


def test_chat_stores_optional_session_and_task(client) -> None:
    session_data = _start_session(client)
    task_id = "task_academic_progression_notice"

    response = client.post(
        "/api/chat",
        json={
            "sessionId": session_data["sessionId"],
            "participantLabel": "P-STUDY-001",
            "participantId": "P-STUDY-001",
            "taskId": task_id,
            "condition": "C_HIGHLIGHT",
            "question": "I received an academic progression notice. What should I do before the deadline?",
            "sensitiveWarningShown": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    with Session(engine) as db_session:
        log = db_session.get(InteractionLog, data["interactionId"])
    assert log is not None
    assert log.session_id == session_data["sessionId"]
    assert log.participant_label == "P-STUDY-001"
    assert log.task_id == task_id
    assert log.sensitive_warning_shown is True


def test_csv_export_includes_session_and_task_fields(client) -> None:
    session_response = client.post(
        "/api/study/session/start",
        json={
            "participantLabel": "P-STUDY-001",
            "studyCondition": "C_HIGHLIGHT",
            "prototypeNoticeAcknowledged": True,
        },
    )
    assert session_response.status_code == 200
    session_data = session_response.json()
    task_id = "task_withdrawal_census_penalty"
    client.post(
        "/api/study/session/task/start",
        json={"sessionId": session_data["sessionId"], "taskId": task_id},
    )
    chat_response = client.post(
        "/api/chat",
        json={
            "sessionId": session_data["sessionId"],
            "participantLabel": "P-STUDY-001",
            "participantId": "P-STUDY-001",
            "taskId": task_id,
            "condition": "C_HIGHLIGHT",
            "question": "If I withdraw after census date, could there be fee consequences?",
            "sensitiveWarningShown": True,
        },
    )
    assert chat_response.status_code == 200
    client.post(
        "/api/study/feedback",
        json={
            "sessionId": session_data["sessionId"],
            "participantLabel": "P-STUDY-001",
            "taskId": task_id,
            "interactionId": chat_response.json()["interactionId"],
            "answerId": chat_response.json()["id"],
            "rating": "up",
        },
    )

    export_response = client.get("/api/admin/logs/export.csv")
    rows = _csv_rows(export_response.text)
    interaction_row = next(row for row in rows if row["row_type"] == "interaction")
    event_row = next(row for row in rows if row["row_type"] == "event")
    feedback_row = next(row for row in rows if row["row_type"] == "feedback")

    for row in [interaction_row, event_row, feedback_row]:
        assert row["session_id"] == session_data["sessionId"]
        assert row["participant_label"] == "P-STUDY-001"
        assert row["study_condition"] == "C_HIGHLIGHT"
        assert row["task_id"] == task_id
        assert row["task_title"] == "Withdrawal timing and academic penalty"
        assert row["task_type"] == "multi_condition"
        assert row["task_difficulty"] == "medium"
        assert row["escalation_expected"] == "true"
        assert row["session_started_at"]
        assert row["prototype_notice_acknowledged"] == "true"
        assert row["prototype_notice_acknowledged_at"]

    assert interaction_row["sensitive_warning_shown"] == "true"


def test_old_logs_without_session_or_task_still_export(client) -> None:
    response = client.post("/api/chat", json={"question": "When should I contact staff?"})
    assert response.status_code == 200

    export_response = client.get("/api/admin/logs/export.csv")
    rows = _csv_rows(export_response.text)
    interaction_row = next(row for row in rows if row["row_type"] == "interaction")
    assert interaction_row["session_id"] == ""
    assert interaction_row["task_title"] == ""
