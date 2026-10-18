import csv
from io import StringIO

from sqlmodel import Session, select

from app.database import engine
from app.models import FinalTaskResponse, StudyEventLog


def _csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(text)))


def _start_session(client) -> dict:
    response = client.post(
        "/api/study/session/start",
        json={
            "participantLabel": "P-FINAL-001",
            "studyCondition": "C_HIGHLIGHT",
        },
    )
    assert response.status_code == 200
    return response.json()


def _valid_final_response(session_id: str, task_id: str) -> dict:
    return {
        "sessionId": session_id,
        "taskId": task_id,
        "finalDecisionText": "I would check the cited evidence and contact staff before acting.",
        "confidenceRating": 4,
        "wouldContactStaff": "yes",
        "perceivedAnswerSupported": 5,
        "perceivedTaskDifficulty": 3,
        "notes": "The citation made the escalation point clearer.",
    }


def test_submitting_final_task_response_succeeds(client) -> None:
    session_data = _start_session(client)
    task_id = "task_withdrawal_census_penalty"

    response = client.post(
        "/api/study/task/final-response",
        json=_valid_final_response(session_data["sessionId"], task_id),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["responseId"].startswith("final_response_")
    assert data["sessionId"] == session_data["sessionId"]
    assert data["taskId"] == task_id
    assert data["createdAt"]


def test_final_task_response_missing_required_field_returns_validation_error(
    client,
) -> None:
    session_data = _start_session(client)
    payload = _valid_final_response(
        session_data["sessionId"],
        "task_special_consideration_illness",
    )
    payload.pop("finalDecisionText")

    response = client.post("/api/study/task/final-response", json=payload)

    assert response.status_code == 422


def test_final_task_response_rejects_invalid_confidence_rating(client) -> None:
    session_data = _start_session(client)
    payload = _valid_final_response(
        session_data["sessionId"],
        "task_special_consideration_illness",
    )
    payload["confidenceRating"] = 6

    response = client.post("/api/study/task/final-response", json=payload)

    assert response.status_code == 422


def test_final_task_response_creates_row_and_event(client) -> None:
    session_data = _start_session(client)
    task_id = "task_academic_progression_notice"

    response = client.post(
        "/api/study/task/final-response",
        json=_valid_final_response(session_data["sessionId"], task_id),
    )

    assert response.status_code == 200
    response_id = response.json()["responseId"]
    with Session(engine) as db_session:
        final_response = db_session.get(FinalTaskResponse, response_id)
        event = db_session.exec(
            select(StudyEventLog).where(
                StudyEventLog.session_id == session_data["sessionId"],
                StudyEventLog.task_id == task_id,
                StudyEventLog.event_type == "final_response_submitted",
            )
        ).first()

    assert final_response is not None
    assert final_response.participant_label == "P-FINAL-001"
    assert final_response.confidence_rating == 4
    assert final_response.would_contact_staff == "yes"
    assert final_response.perceived_answer_supported == 5
    assert final_response.decision_appropriateness is None
    assert final_response.researcher_code is None
    assert event is not None
    assert '"confidenceRating": 4' in (event.metadata_json or "")
    assert response_id in (event.metadata_json or "")


def test_csv_export_includes_final_response_fields(client) -> None:
    session_data = _start_session(client)
    task_id = "task_withdrawal_census_penalty"
    final_response = client.post(
        "/api/study/task/final-response",
        json=_valid_final_response(session_data["sessionId"], task_id),
    )
    assert final_response.status_code == 200

    export_response = client.get("/api/admin/logs/export.csv")
    rows = _csv_rows(export_response.text)
    row = next(item for item in rows if item["row_type"] == "final_response")

    assert row["final_response_id"] == final_response.json()["responseId"]
    assert row["session_id"] == session_data["sessionId"]
    assert row["participant_label"] == "P-FINAL-001"
    assert row["task_id"] == task_id
    assert row["task_title"] == "Withdrawal timing and academic penalty"
    assert row["task_type"] == "multi_condition"
    assert row["task_difficulty"] == "medium"
    assert row["escalation_expected"] == "true"
    assert row["final_decision_text"].startswith("I would check")
    assert row["final_decision_length"] == "65"
    assert row["confidence_rating"] == "4"
    assert row["would_contact_staff"] == "yes"
    assert row["perceived_answer_supported"] == "5"
    assert row["perceived_task_difficulty"] == "3"
    assert row["final_response_notes"] == "The citation made the escalation point clearer."
    assert row["final_response_created_at"]
    assert row["decision_appropriateness"] == ""
    assert row["researcher_code"] == ""


def test_task_completion_still_works_without_final_response(client) -> None:
    session_data = _start_session(client)
    task_id = "task_special_consideration_illness"
    client.post(
        "/api/study/session/task/start",
        json={"sessionId": session_data["sessionId"], "taskId": task_id},
    )

    response = client.post(
        "/api/study/session/task/complete",
        json={"sessionId": session_data["sessionId"], "taskId": task_id},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"


def test_chat_still_works_with_session_and_task_after_final_response_changes(
    client,
) -> None:
    session_data = _start_session(client)
    task_id = "task_academic_progression_notice"

    response = client.post(
        "/api/chat",
        json={
            "sessionId": session_data["sessionId"],
            "participantLabel": "P-FINAL-001",
            "participantId": "P-FINAL-001",
            "taskId": task_id,
            "condition": "C_HIGHLIGHT",
            "question": "What should I do about an academic progression notice?",
        },
    )

    assert response.status_code == 200
    assert response.json()["interactionId"].startswith("interaction_")


def test_old_study_logs_export_with_blank_final_response_fields(client) -> None:
    response = client.post("/api/chat", json={"question": "When should I contact staff?"})
    assert response.status_code == 200

    export_response = client.get("/api/admin/logs/export.csv")
    rows = _csv_rows(export_response.text)
    interaction_row = next(row for row in rows if row["row_type"] == "interaction")

    assert interaction_row["final_response_id"] == ""
    assert interaction_row["final_decision_text"] == ""
    assert interaction_row["confidence_rating"] == ""
    assert interaction_row["decision_appropriateness"] == ""
    assert interaction_row["researcher_code"] == ""
