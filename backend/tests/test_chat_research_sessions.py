import csv
import io
import json
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models import EvidenceUse, FeedbackLog, InteractionLog, StudyEventLog, StudySession


def start(client, participant="P01", round_id="pilot-01", **kwargs):
    payload = {"sessionId": str(uuid4()), "participantLabel": participant,
               "roundId": round_id, "prototypeNoticeAcknowledged": True, **kwargs}
    return client.post("/api/study/session/start", json=payload), payload


def interaction(session_id):
    with Session(engine) as db:
        item = InteractionLog(
            id=str(uuid4()), session_id=session_id, participant_label="P01",
            condition="C_HIGHLIGHT", question="=unsafe()", answer_id=str(uuid4()),
            short_answer="A rule [1]", full_answer="A full policy answer [1]",
            uncertainty_level="low", escalation_recommended=False, citation_count=1,
            citations_json=json.dumps([{"id": "c1", "citationId": "c1", "sourceId": "s1", "chunkId": "chunk1"}]),
            execution_context="development",
        )
        db.add(item); db.commit(); db.refresh(item)
        return item


def read_csv(client, kind, query=""):
    response = client.get(f"/api/admin/research/export/{kind}.csv{query}")
    assert response.status_code == 200
    return list(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))


def test_start_retry_and_complete_are_idempotent(client):
    response, payload = start(client)
    assert response.status_code == 200
    sid = response.json()["sessionId"]
    assert response.json()["roundId"] == "pilot-01"
    assert response.json()["executionContext"] == "development"
    assert response.json()["currentTaskId"] is None
    assert client.post("/api/study/session/start", json=payload).json() == response.json()
    first = client.post("/api/study/session/complete", json={"sessionId": sid})
    second = client.post("/api/study/session/complete", json={"sessionId": sid})
    assert first.status_code == 200 and first.json() == second.json()
    with Session(engine) as db:
        assert len(db.exec(select(StudySession)).all()) == 1
        assert [e.event_type for e in db.exec(select(StudyEventLog)).all()] == ["session_started", "session_completed"]


@pytest.mark.parametrize("changes", [{"participantLabel": "A Real Name"}, {"prototypeNoticeAcknowledged": False}, {"roundId": "invalid round"}])
def test_start_requires_codes_and_consent(client, changes):
    response, _ = start(client, **changes)
    assert response.status_code == 422


def test_writes_have_server_identity_distinct_evidence_and_safe_retries(client):
    response, _ = start(client)
    sid = response.json()["sessionId"]
    answer = interaction(sid)
    for action in ("citation_clicked", "evidence_panel_opened", "source_opened"):
        payload = {"requestId": str(uuid4()), "sessionId": sid, "participantLabel": "forged",
                   "interactionId": answer.id, "citationId": "c1", "sourceId": "s1",
                   "chunkId": "chunk1", "evidenceAction": action}
        first = client.post("/api/study/evidence-use", json=payload)
        assert first.status_code == 200, first.text
        assert client.post("/api/study/evidence-use", json=payload).json() == first.json()
        assert client.post("/api/study/evidence-use", json={**payload, "chunkId": "other"}).status_code == 409
    feedback = {"requestId": str(uuid4()), "sessionId": sid, "interactionId": answer.id,
                "answerId": answer.answer_id, "rating": "up", "comment": "Useful"}
    first = client.post("/api/study/feedback", json=feedback)
    assert first.status_code == 200
    assert client.post("/api/study/feedback", json=feedback).json() == first.json()
    event = {"requestId": str(uuid4()), "sessionId": sid, "eventType": "question_submitted"}
    first = client.post("/api/study/log-event", json=event)
    assert client.post("/api/study/log-event", json=event).json() == first.json()
    with Session(engine) as db:
        assert len(db.exec(select(EvidenceUse)).all()) == 3
        assert len(db.exec(select(FeedbackLog)).all()) == 1
        assert all(e.participant_label == "P01" for e in db.exec(select(StudyEventLog)).all())
    client.post("/api/study/session/complete", json={"sessionId": sid})
    assert client.post("/api/study/feedback", json=feedback).status_code == 200
    assert client.post("/api/study/log-event", json={**event, "requestId": str(uuid4())}).status_code == 409
    assert client.post("/api/chat", json={"sessionId": sid, "question": "Any policy?"}).status_code == 409


def test_reject_cross_session_and_unknown_citations(client):
    first, _ = start(client)
    second, _ = start(client, "P02")
    answer = interaction(first.json()["sessionId"])
    payload = {"sessionId": second.json()["sessionId"], "interactionId": answer.id,
               "answerId": answer.answer_id, "rating": "up"}
    assert client.post("/api/study/feedback", json=payload).status_code == 409
    assert client.post("/api/study/feedback", json={**payload, "sessionId": None}).status_code == 409
    assert client.post("/api/study/evidence-use", json={
        "sessionId": first.json()["sessionId"], "interactionId": answer.id,
        "evidenceAction": "source_opened", "citationId": "fake",
    }).status_code == 409


def test_exports_filter_round_and_participant_and_preserve_history(client):
    first, _ = start(client)
    second, _ = start(client, "P02")
    third, _ = start(client, "P01", "pilot-02")
    for result in (first, second, third):
        interaction(result.json()["sessionId"])
    legacy = client.post("/api/study/session/start", json={"participantLabel": "historical"})
    assert legacy.status_code == 200
    sid = first.json()["sessionId"]
    client.post("/api/study/log-event", json={"sessionId": sid, "eventType": "question_submitted"})
    client.post("/api/study/session/complete", json={"sessionId": sid})
    query = "?round_id=pilot-01&participant=P01"
    summaries = read_csv(client, "participants", query)
    assert len(summaries) == 1 and summaries[0]["session_id"] == sid
    assert summaries[0]["answer_count"] == "1"
    assert summaries[0]["question_count"] == "1"
    assert float(summaries[0]["duration_seconds"]) >= 0
    timeline = read_csv(client, "timeline", query)
    assert len(timeline) == 3
    assert [r["occurred_at"] for r in timeline] == sorted(r["occurred_at"] for r in timeline)
    answers = read_csv(client, "answers", query)
    assert len(answers) == 1
    assert answers[0]["question"] == "'=unsafe()"
    assert answers[0]["answer"] == "A full policy answer [1]"
    assert answers[0]["citations_json"]
    assert len(read_csv(client, "participants")) == 3
    assert read_csv(client, "answers", "?round_id=missing") == []
    with Session(engine) as db:
        assert db.get(StudySession, legacy.json()["sessionId"]) is not None


def test_chat_is_attributed_without_task_or_client_identity(client):
    result, _ = start(client)
    sid = result.json()["sessionId"]
    answer = client.post("/api/chat", json={"sessionId": sid, "question": "How do I apply for a deferred exam?"})
    assert answer.status_code == 200, answer.text
    with Session(engine) as db:
        row = db.get(InteractionLog, answer.json()["interactionId"])
        assert row.participant_label == "P01" and row.session_id == sid
        assert row.task_id is None
        assert row.execution_context == "development"


def test_changed_round_configuration_is_rejected(client):
    result, _ = start(client)
    with Session(engine) as db:
        row = db.get(StudySession, result.json()["sessionId"])
        row.runtime_config_fingerprint = "old"
        db.add(row); db.commit()
    response, _ = start(client, "P02")
    assert response.status_code == 409


def test_failed_write_can_retry_without_false_success(client, monkeypatch):
    result, _ = start(client)
    payload = {"sessionId": result.json()["sessionId"], "requestId": str(uuid4()), "eventType": "question_submitted"}
    original = Session.commit
    monkeypatch.setattr(Session, "commit", lambda _: (_ for _ in ()).throw(RuntimeError("simulated disk failure")))
    with pytest.raises(RuntimeError):
        client.post("/api/study/log-event", json=payload)
    monkeypatch.setattr(Session, "commit", original)
    assert client.post("/api/study/log-event", json=payload).status_code == 200
    assert client.post("/api/study/log-event", json=payload).status_code == 200
    with Session(engine) as db:
        assert len(db.exec(select(StudyEventLog).where(StudyEventLog.event_type == "question_submitted")).all()) == 1


def test_failed_provenance_can_be_reported_after_database_recovers(client):
    first, _ = start(client)
    second, _ = start(client, "P02")
    payload = {"sessionId": first.json()["sessionId"], "requestId": str(uuid4()),
               "interactionId": "failed-commit-no-row", "eventType": "system_failure"}
    assert client.post("/api/study/log-event", json=payload).status_code == 200
    assert client.post("/api/study/log-event", json=payload).status_code == 200
    assert client.post("/api/study/log-event", json={
        **payload, "sessionId": second.json()["sessionId"], "requestId": str(uuid4()),
    }).status_code == 409
