import os
from pathlib import Path

from sqlmodel import Session, select

from app.database import engine
from app.models import FeedbackLog, StudyEventLog


def test_database_file_is_created_on_startup(client) -> None:
    assert Path(os.environ["UNI_NAVIGATOR_DB_PATH"]).exists()


def test_log_event_endpoint_returns_ok(client) -> None:
    response = client.post(
        "/api/study/log-event",
        json={
            "interactionId": "interaction_test_001",
            "participantId": "P001",
            "taskId": "T001",
            "condition": "C_HIGHLIGHT",
            "eventType": "citation_clicked",
            "timestamp": "2026-05-24T10:00:00Z",
            "metadata": {
                "citationId": "citation_001",
                "chunkId": "mock_chunk_001",
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["eventId"].startswith("event_")


def test_invalid_event_type_returns_validation_error(client) -> None:
    response = client.post(
        "/api/study/log-event",
        json={"eventType": "not_supported"},
    )

    assert response.status_code == 422


def test_feedback_endpoint_returns_ok(client) -> None:
    response = client.post(
        "/api/study/feedback",
        json={
            "interactionId": "interaction_test_001",
            "answerId": "answer_test_001",
            "rating": "up",
            "comment": "The highlighted evidence was useful.",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["feedbackId"].startswith("feedback_")

    with Session(engine) as session:
        feedback = session.get(FeedbackLog, data["feedbackId"])
        event = session.exec(
            select(StudyEventLog).where(
                StudyEventLog.event_type == "feedback_submitted",
                StudyEventLog.interaction_id == "interaction_test_001",
            )
        ).one()

    assert feedback is not None
    assert event.metadata_json is not None
    assert data["feedbackId"] in event.metadata_json


def test_invalid_feedback_rating_returns_validation_error(client) -> None:
    response = client.post(
        "/api/study/feedback",
        json={"answerId": "answer_test_001", "rating": "maybe"},
    )

    assert response.status_code == 422


def test_chat_creates_interaction_log_visible_to_admin(client) -> None:
    chat_response = client.post(
        "/api/chat",
        json={
            "question": "Can I apply for special consideration after missing an exam?",
            "participantId": "P900",
            "taskId": "T900",
            "condition": "C_HIGHLIGHT",
        },
    )
    assert chat_response.status_code == 200
    chat_data = chat_response.json()

    logs_response = client.get("/api/admin/logs")
    assert logs_response.status_code == 200
    logs = logs_response.json()["items"]
    matching_log = next(
        item for item in logs if item["id"] == chat_data["interactionId"]
    )

    assert matching_log["participantId"] == "P900"
    assert matching_log["taskId"] == "T900"
    assert matching_log["condition"] == "C_HIGHLIGHT"
    assert matching_log["answerId"] == chat_data["id"]
    assert matching_log["citationCount"] == len(chat_data["citations"])
    assert matching_log["retrievedChunkIds"] == []
    assert "shortAnswer" in matching_log
    assert "createdAt" in matching_log
