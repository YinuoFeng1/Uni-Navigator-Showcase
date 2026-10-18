import csv
import json
from io import StringIO


def _csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(text)))


def test_csv_export_empty_database_returns_header(client) -> None:
    response = client.get("/api/admin/logs/export.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "uni_navigator_logs.csv" in response.headers["content-disposition"]
    assert response.text.startswith("row_type,interaction_id,session_id")
    assert _csv_rows(response.text) == []


def test_csv_export_includes_interaction_event_and_feedback(client) -> None:
    chat_response = client.post(
        "/api/chat",
        json={
            "question": "What evidence do I need for an assessment extension?",
            "participantId": "P-CSV",
            "taskId": "task_extension",
            "condition": "C_HIGHLIGHT",
        },
    )
    assert chat_response.status_code == 200
    answer = chat_response.json()

    event_response = client.post(
        "/api/study/log-event",
        json={
            "interactionId": answer["interactionId"],
            "participantId": "P-CSV",
            "taskId": "task_extension",
            "condition": "C_HIGHLIGHT",
            "eventType": "trust_check_updated",
            "metadata": {
                "citationId": "citation_csv",
                "chunkId": "mock_chunk_001",
                "checkedSource": True,
                "evidenceSupportsAnswer": True,
                "understandsLimitation": False,
                "knowsWhenToContactStaff": True,
            },
        },
    )
    assert event_response.status_code == 200

    feedback_response = client.post(
        "/api/study/feedback",
        json={
            "interactionId": answer["interactionId"],
            "answerId": answer["id"],
            "rating": "up",
            "comment": 'Clear evidence, "useful" for export.',
        },
    )
    assert feedback_response.status_code == 200

    export_response = client.get("/api/admin/logs/export.csv")
    assert export_response.status_code == 200
    rows = _csv_rows(export_response.text)

    interaction_row = next(row for row in rows if row["row_type"] == "interaction")
    event_row = next(row for row in rows if row["row_type"] == "event")
    feedback_row = next(row for row in rows if row["row_type"] == "feedback")

    assert interaction_row["interaction_id"] == answer["interactionId"]
    assert interaction_row["participant_id"] == "P-CSV"
    assert interaction_row["question"] == "What evidence do I need for an assessment extension?"
    assert interaction_row["based_on"]
    assert interaction_row["limitations"]
    assert interaction_row["uncertainty"]
    assert interaction_row["escalation_guidance"]
    assert interaction_row["high_stakes_detected"] == "true"
    assert interaction_row["escalation_category"]
    assert json.loads(interaction_row["escalation_reasons_json"])
    assert interaction_row["retrieval_status"] == "insufficient_evidence"
    assert interaction_row["citation_ids"] == "[]"
    assert interaction_row["source_ids"] == "[]"
    assert interaction_row["chunk_ids"] == "[]"
    assert interaction_row["retrieved_chunk_ids"] == "[]"
    assert interaction_row["retrieved_context_count"] == "0"
    assert interaction_row["escalation_guidance_present"] == "true"

    assert event_row["event_type"] == "trust_check_updated"
    assert event_row["citation_id"] == "citation_csv"
    assert event_row["chunk_id"] == "mock_chunk_001"
    assert event_row["checked_source"] == "true"
    assert event_row["understands_limitation"] == "false"

    assert feedback_row["event_type"] == "feedback_submitted"
    assert feedback_row["feedback_rating"] == "up"
    assert feedback_row["feedback_text"] == 'Clear evidence, "useful" for export.'


def test_csv_export_includes_retrieval_citation_fields(monkeypatch, client) -> None:
    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [
            {
                "chunk_id": "chunk_csv_001",
                "source_id": "uq-assessment-procedure",
                "title": "CSV Policy",
                "document_name": "CSV Procedure",
                "section": "Evidence",
                "url": "https://example.edu/csv-policy",
                "source_type": "official_policy",
                "chunk_text": "Students may need supporting evidence for extension requests.",
                "score": 0.9,
                "active": True,
            }
        ],
    )

    chat_response = client.post(
        "/api/chat",
        json={
            "question": "What evidence do I need for an extension?",
            "participantId": "P-RAG-CSV",
            "condition": "C_HIGHLIGHT",
        },
    )
    assert chat_response.status_code == 200

    export_response = client.get("/api/admin/logs/export.csv")
    rows = _csv_rows(export_response.text)
    interaction_row = next(row for row in rows if row["row_type"] == "interaction")

    assert interaction_row["retrieval_status"] == "ambiguous"
    assert interaction_row["based_on"]
    assert interaction_row["limitations"]
    assert interaction_row["uncertainty"]
    assert interaction_row["escalation_guidance"]
    assert interaction_row["high_stakes_detected"] == "true"
    assert interaction_row["escalation_recommended"] == "true"
    assert interaction_row["escalation_category"]
    assert json.loads(interaction_row["escalation_reasons_json"])
    assert interaction_row["citation_ids"] == '["c1"]'
    assert interaction_row["source_ids"] == '["uq-assessment-procedure"]'
    assert interaction_row["chunk_ids"] == '["chunk_csv_001"]'
    assert interaction_row["retrieved_chunk_ids"] == '["chunk_csv_001"]'
    assert interaction_row["retrieved_context_count"] == "1"
    assert interaction_row["escalation_guidance_present"] == "true"
    assert interaction_row["full_answer"]
    assert json.loads(interaction_row["citations_json"])[0]["chunkId"] == "chunk_csv_001"
    retrieval_trace = json.loads(interaction_row["retrieval_trace_json"])
    assert retrieval_trace[0]["rank"] == 1
    assert retrieval_trace[0]["score"] == 0.9
    assert interaction_row["response_time_ms"]
    assert interaction_row["error_type"] == ""
    assert interaction_row["provider_response_id"] == "resp_test_fixture"
    assert interaction_row["total_tokens"] == "150"
    assert interaction_row["prompt_template_version"] == "grounded-v9"
    assert interaction_row["runtime_config_fingerprint"].startswith("sha256:")


def test_csv_export_includes_failed_attempt_runtime(monkeypatch, client) -> None:
    def fail_retrieval(*args, **kwargs):
        raise RuntimeError("vector unavailable")

    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        fail_retrieval,
    )
    response = client.post(
        "/api/chat",
        json={"question": "How do I apply for special consideration?"},
    )

    assert response.status_code == 503
    rows = _csv_rows(client.get("/api/admin/logs/export.csv").text)
    failure_row = next(
        row
        for row in rows
        if row["row_type"] == "event"
        and row["error_type"] == "vector_store_unavailable"
    )

    assert failure_row["retrieval_status"] == "not_completed"
    assert failure_row["retrieval_trace_json"] == ""
    assert failure_row["ai_provider"] == "openai"
    assert failure_row["ai_model_requested"]
    assert failure_row["prompt_template_version"] == "grounded-v9"
    assert failure_row["retrieval_top_k"] == "5"
    assert failure_row["response_time_ms"]
    assert failure_row["runtime_config_fingerprint"].startswith("sha256:")
    assert json.loads(failure_row["runtime_config_json"])["answer_mode"] == "live_llm"
