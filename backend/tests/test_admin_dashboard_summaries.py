def _start_session(client) -> dict:
    response = client.post(
        "/api/study/session/start",
        json={
            "participantLabel": "P-ADMIN-001",
            "studyCondition": "C_HIGHLIGHT",
        },
    )
    assert response.status_code == 200
    return response.json()


def _create_dashboard_data(client) -> dict:
    session_data = _start_session(client)
    session_id = session_data["sessionId"]
    task_id = "task_withdrawal_census_penalty"
    client.post(
        "/api/study/session/task/start",
        json={"sessionId": session_id, "taskId": task_id},
    )
    chat_response = client.post(
        "/api/chat",
        json={
            "sessionId": session_id,
            "participantLabel": "P-ADMIN-001",
            "participantId": "P-ADMIN-001",
            "taskId": task_id,
            "condition": "C_HIGHLIGHT",
            "question": "Could withdrawing after census date affect fees?",
        },
    )
    assert chat_response.status_code == 200
    chat_data = chat_response.json()
    client.post(
        "/api/study/evidence-use",
        json={
            "sessionId": session_id,
            "participantLabel": "P-ADMIN-001",
            "taskId": task_id,
            "interactionId": chat_data["interactionId"],
            "citationId": "c1",
            "sourceId": "prepared-course-withdrawal-census",
            "chunkId": "prepared_course_withdrawal_census_chunk_0000",
            "evidenceAction": "source_checked",
            "evidenceSupportRating": 5,
            "userMarkedHelpful": True,
        },
    )
    client.post(
        "/api/study/trust-checklist",
        json={
            "sessionId": session_id,
            "participantLabel": "P-ADMIN-001",
            "taskId": task_id,
            "interactionId": chat_data["interactionId"],
            "answerClear": True,
            "evidenceChecked": True,
            "sourceSupportsAnswer": True,
            "uncertaintyNoticed": True,
            "wouldContactStaffIfNeeded": True,
        },
    )
    final_decision = (
        "I would check the cited withdrawal and fee evidence, avoid assuming that "
        "my personal case is automatically eligible, and contact authorised staff "
        "before making an enrolment or financial decision."
    )
    final_response = client.post(
        "/api/study/task/final-response",
        json={
            "sessionId": session_id,
            "taskId": task_id,
            "interactionId": chat_data["interactionId"],
            "finalDecisionText": final_decision,
            "confidenceRating": 4,
            "wouldContactStaff": "yes",
            "perceivedAnswerSupported": 5,
        },
    )
    assert final_response.status_code == 200
    client.post(
        "/api/study/feedback",
        json={
            "sessionId": session_id,
            "participantLabel": "P-ADMIN-001",
            "taskId": task_id,
            "interactionId": chat_data["interactionId"],
            "answerId": chat_data["id"],
            "rating": "up",
            "comment": "Evidence was clear.",
        },
    )
    client.post(
        "/api/study/session/task/complete",
        json={"sessionId": session_id, "taskId": task_id},
    )
    return {
        "sessionId": session_id,
        "taskId": task_id,
        "interactionId": chat_data["interactionId"],
        "finalDecision": final_decision,
    }


def test_admin_sessions_returns_empty_list_safely(client) -> None:
    response = client.get("/api/admin/sessions")

    assert response.status_code == 200
    assert response.json()["items"] == []


def test_admin_sessions_returns_session_summary(client) -> None:
    data = _create_dashboard_data(client)

    response = client.get("/api/admin/sessions")

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["sessionId"] == data["sessionId"]
    assert item["participantLabel"] == "P-ADMIN-001"
    assert item["tasksStartedCount"] == 1
    assert item["tasksCompletedCount"] == 1
    assert item["interactionCount"] == 1
    assert item["evidenceUseCount"] == 1
    assert item["sourceCheckedCount"] == 1
    assert item["feedbackCount"] == 1
    assert item["finalResponseCount"] == 1
    assert item["latestTrustChecklistSummary"]["evidenceChecked"] is True
    assert item["lastActivityAt"]


def test_admin_session_detail_returns_safe_summary_without_full_final_text(
    client,
) -> None:
    data = _create_dashboard_data(client)

    response = client.get(f"/api/admin/sessions/{data['sessionId']}")

    assert response.status_code == 200
    detail = response.json()
    assert detail["summary"]["sessionId"] == data["sessionId"]
    assert detail["taskProgress"]["startedTaskIds"] == [data["taskId"]]
    assert detail["taskProgress"]["completedTaskIds"] == [data["taskId"]]
    assert detail["interactions"][0]["interactionId"] == data["interactionId"]
    assert detail["evidenceUseSummary"][0]["evidenceAction"] == "source_checked"
    assert detail["latestTrustChecklist"]["sourceSupportsAnswer"] is True
    final_summary = detail["finalResponses"][0]
    assert final_summary["confidenceRating"] == 4
    assert final_summary["wouldContactStaff"] == "yes"
    assert final_summary["finalDecisionLength"] == len(data["finalDecision"])
    assert len(final_summary["finalDecisionPreview"]) <= 120
    assert data["finalDecision"] not in response.text
    assert detail["feedback"][0]["commentLength"] == len("Evidence was clear.")
    assert detail["eventTimeline"]


def test_admin_tasks_returns_task_summaries(client) -> None:
    data = _create_dashboard_data(client)

    response = client.get("/api/admin/tasks")

    assert response.status_code == 200
    task = next(item for item in response.json()["items"] if item["taskId"] == data["taskId"])
    assert task["title"] == "Withdrawal timing and academic penalty"
    assert task["taskType"] == "multi_condition"
    assert task["difficulty"] == "medium"
    assert task["escalationExpected"] is True
    assert task["sessionsStartedCount"] == 1
    assert task["sessionsCompletedCount"] == 1
    assert task["finalResponseCount"] == 1
    assert task["averageConfidence"] == 4
    assert task["contactStaffYesCount"] == 1
    assert task["contactStaffNoCount"] == 0
    assert task["contactStaffUnsureCount"] == 0
    assert task["evidenceUseCount"] == 1
    assert task["trustChecklistCount"] == 1
    assert task["trustSnapshotCount"] == 1


def test_admin_tasks_counts_one_checklist_per_session_task(client) -> None:
    data = _create_dashboard_data(client)
    second_snapshot = client.post(
        "/api/study/trust-checklist",
        json={
            "sessionId": data["sessionId"],
            "participantLabel": "P-ADMIN-001",
            "taskId": data["taskId"],
            "interactionId": data["interactionId"],
            "answerClear": False,
            "evidenceChecked": True,
            "sourceSupportsAnswer": False,
            "uncertaintyNoticed": True,
            "wouldContactStaffIfNeeded": True,
        },
    )
    assert second_snapshot.status_code == 200

    response = client.get("/api/admin/tasks")

    assert response.status_code == 200
    task = next(item for item in response.json()["items"] if item["taskId"] == data["taskId"])
    assert task["trustChecklistCount"] == 1
    assert task["trustSnapshotCount"] == 2


def test_admin_csv_export_still_works_with_dashboard_data(client) -> None:
    _create_dashboard_data(client)

    response = client.get("/api/admin/logs/export.csv")

    assert response.status_code == 200
    assert "row_type" in response.text
    assert "final_response" in response.text
    assert "evidence_use" in response.text
    assert "trust_checklist" in response.text
