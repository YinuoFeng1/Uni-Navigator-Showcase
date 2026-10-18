import csv
from io import StringIO


def _csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(text)))


def _create_summary_export_data(client) -> dict[str, str]:
    start_response = client.post(
        "/api/study/session/start",
        json={
            "participantLabel": "P-SUMMARY-001",
            "studyCondition": "C_HIGHLIGHT",
            "prototypeNoticeAcknowledged": True,
        },
    )
    assert start_response.status_code == 200
    session_id = start_response.json()["sessionId"]
    task_id = "task_withdrawal_census_penalty"

    task_start_response = client.post(
        "/api/study/session/task/start",
        json={"sessionId": session_id, "taskId": task_id},
    )
    assert task_start_response.status_code == 200

    chat_response = client.post(
        "/api/chat",
        json={
            "sessionId": session_id,
            "participantLabel": "P-SUMMARY-001",
            "participantId": "P-SUMMARY-001",
            "taskId": task_id,
            "condition": "C_HIGHLIGHT",
            "question": "Could withdrawing after census date affect fees?",
            "sensitiveWarningShown": True,
        },
    )
    assert chat_response.status_code == 200
    answer = chat_response.json()

    for payload in [
        {
            "evidenceAction": "evidence_panel_opened",
            "sourceId": "source-A",
            "chunkId": "chunk-A",
        },
        {
            "evidenceAction": "source_checked",
            "sourceId": "source-A",
            "chunkId": "chunk-A",
            "evidenceSupportRating": 4,
            "userMarkedHelpful": True,
        },
        {
            "evidenceAction": "evidence_rating_submitted",
            "sourceId": "source-A",
            "chunkId": "chunk-A",
            "evidenceSupportRating": 2,
            "userMarkedConfusing": True,
            "notes": "This private evidence note should not appear in summaries.",
        },
    ]:
        evidence_response = client.post(
            "/api/study/evidence-use",
            json={
                "sessionId": session_id,
                "participantLabel": "P-SUMMARY-001",
                "taskId": task_id,
                "interactionId": answer["interactionId"],
                "citationId": "c1",
                **payload,
            },
        )
        assert evidence_response.status_code == 200

    first_trust_response = client.post(
        "/api/study/trust-checklist",
        json={
            "sessionId": session_id,
            "participantLabel": "P-SUMMARY-001",
            "taskId": task_id,
            "interactionId": answer["interactionId"],
            "answerClear": False,
            "evidenceChecked": False,
            "sourceSupportsAnswer": False,
            "uncertaintyNoticed": False,
            "wouldContactStaffIfNeeded": False,
        },
    )
    assert first_trust_response.status_code == 200
    latest_trust_response = client.post(
        "/api/study/trust-checklist",
        json={
            "sessionId": session_id,
            "participantLabel": "P-SUMMARY-001",
            "taskId": task_id,
            "interactionId": answer["interactionId"],
            "answerClear": True,
            "evidenceChecked": True,
            "sourceSupportsAnswer": False,
            "uncertaintyNoticed": True,
            "wouldContactStaffIfNeeded": True,
        },
    )
    assert latest_trust_response.status_code == 200

    first_decision = "FIRST SECRET DECISION TEXT"
    latest_decision = "LATEST SECRET DECISION TEXT"
    first_final_response = client.post(
        "/api/study/task/final-response",
        json={
            "sessionId": session_id,
            "taskId": task_id,
            "interactionId": answer["interactionId"],
            "finalDecisionText": first_decision,
            "confidenceRating": 3,
            "wouldContactStaff": "yes",
            "perceivedAnswerSupported": 4,
        },
    )
    assert first_final_response.status_code == 200
    latest_final_response = client.post(
        "/api/study/task/final-response",
        json={
            "sessionId": session_id,
            "taskId": task_id,
            "interactionId": answer["interactionId"],
            "finalDecisionText": latest_decision,
            "confidenceRating": 5,
            "wouldContactStaff": "not_sure",
            "perceivedAnswerSupported": 2,
            "perceivedTaskDifficulty": 4,
            "notes": "Private final notes should not appear in summaries.",
        },
    )
    assert latest_final_response.status_code == 200

    feedback_response = client.post(
        "/api/study/feedback",
        json={
            "sessionId": session_id,
            "participantLabel": "P-SUMMARY-001",
            "taskId": task_id,
            "interactionId": answer["interactionId"],
            "answerId": answer["id"],
            "rating": "up",
            "comment": "This detailed feedback remains raw-log only.",
        },
    )
    assert feedback_response.status_code == 200

    task_complete_response = client.post(
        "/api/study/session/task/complete",
        json={"sessionId": session_id, "taskId": task_id},
    )
    assert task_complete_response.status_code == 200

    return {
        "session_id": session_id,
        "task_id": task_id,
        "interaction_id": answer["interactionId"],
        "first_decision": first_decision,
        "latest_decision": latest_decision,
    }


def test_session_summary_export_empty_database_returns_header(client) -> None:
    response = client.get("/api/admin/export/session-summary.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "uni_navigator_session_summary.csv" in response.headers[
        "content-disposition"
    ]
    assert response.text.startswith("session_id,participant_label,study_condition")
    assert _csv_rows(response.text) == []


def test_task_summary_export_empty_database_returns_header(client) -> None:
    response = client.get("/api/admin/export/task-summary.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "uni_navigator_task_summary.csv" in response.headers[
        "content-disposition"
    ]
    assert response.text.startswith("session_id,participant_label,study_condition")
    assert _csv_rows(response.text) == []


def test_session_summary_export_includes_session_level_counts(client) -> None:
    data = _create_summary_export_data(client)

    response = client.get("/api/admin/export/session-summary.csv")
    rows = _csv_rows(response.text)

    assert response.status_code == 200
    row = rows[0]
    assert row["session_id"] == data["session_id"]
    assert row["participant_label"] == "P-SUMMARY-001"
    assert row["study_condition"] == "C_HIGHLIGHT"
    assert row["prototype_notice_acknowledged"] == "true"
    assert row["prototype_notice_acknowledged_at"]
    assert row["total_tasks_started"] == "1"
    assert row["total_tasks_completed"] == "1"
    assert row["total_interactions"] == "1"
    assert row["total_questions"] == "1"
    assert row["total_answers"] == "1"
    assert row["total_feedback_submitted"] == "1"
    assert row["total_evidence_actions"] == "3"
    assert row["total_evidence_panel_opened"] == "1"
    assert row["total_source_checked"] == "1"
    assert row["total_evidence_ratings"] == "2"
    assert row["total_final_responses"] == "2"
    assert row["would_contact_staff_yes_count"] == "1"
    assert row["would_contact_staff_unsure_count"] == "1"
    assert row["insufficient_evidence_count"] == "1"
    assert row["sensitive_warning_shown_count"] == "1"
    assert row["last_activity_at"]


def test_task_summary_export_includes_task_level_counts(client) -> None:
    data = _create_summary_export_data(client)

    response = client.get("/api/admin/export/task-summary.csv")
    rows = _csv_rows(response.text)

    assert response.status_code == 200
    row = rows[0]
    assert row["session_id"] == data["session_id"]
    assert row["task_id"] == data["task_id"]
    assert row["task_title"] == "Withdrawal timing and academic penalty"
    assert row["task_type"] == "multi_condition"
    assert row["task_difficulty"] == "medium"
    assert row["escalation_expected"] == "true"
    assert row["expected_safe_behaviour"]
    assert row["prototype_notice_acknowledged"] == "true"
    assert row["task_started_at"]
    assert row["task_completed_at"]
    assert row["interaction_count"] == "1"
    assert row["question_count"] == "1"
    assert row["answer_count"] == "1"
    assert row["high_stakes_detected_count"] == "1"
    assert row["sensitive_warning_shown_count"] == "1"
    assert row["distinct_source_count"] == "1"
    assert row["distinct_chunk_count"] == "1"
    assert row["evidence_action_count"] == "3"
    assert row["evidence_panel_opened_count"] == "1"
    assert row["source_checked_count"] == "1"
    assert row["evidence_rating_count"] == "2"
    assert row["user_marked_helpful_count"] == "1"
    assert row["user_marked_confusing_count"] == "1"
    assert row["final_response_submitted"] == "true"
    assert row["confidence_rating"] == "5"
    assert row["would_contact_staff"] == "not_sure"
    assert row["perceived_answer_supported"] == "2"
    assert row["perceived_task_difficulty"] == "4"
    assert row["decision_appropriateness"] == ""
    assert row["researcher_code"] == ""


def test_summary_exports_calculate_averages_and_latest_trust_values(client) -> None:
    _create_summary_export_data(client)

    session_row = _csv_rows(client.get("/api/admin/export/session-summary.csv").text)[0]
    task_row = _csv_rows(client.get("/api/admin/export/task-summary.csv").text)[0]

    assert session_row["average_confidence_rating"] == "4"
    assert session_row["average_perceived_answer_supported"] == "3"
    assert session_row["average_evidence_support_rating"] == "3"
    assert task_row["average_evidence_support_rating"] == "3"
    assert task_row["latest_answer_clear"] == "true"
    assert task_row["latest_evidence_checked"] == "true"
    assert task_row["latest_source_supports_answer"] == "false"
    assert task_row["latest_uncertainty_noticed"] == "true"
    assert task_row["latest_would_contact_staff_if_needed"] == "true"


def test_summary_exports_do_not_export_sensitive_free_text(client) -> None:
    data = _create_summary_export_data(client)

    session_csv = client.get("/api/admin/export/session-summary.csv").text
    task_csv = client.get("/api/admin/export/task-summary.csv").text
    task_row = _csv_rows(task_csv)[0]

    assert data["first_decision"] not in session_csv
    assert data["latest_decision"] not in session_csv
    assert data["first_decision"] not in task_csv
    assert data["latest_decision"] not in task_csv
    assert "Private final notes should not appear in summaries." not in task_csv
    assert "This private evidence note should not appear in summaries." not in task_csv
    assert task_row["notes_present"] == "true"
