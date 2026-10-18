"""Run one billable, synthetic deployment check, never a participant rating."""

import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import re
import sqlite3
import sys
import uuid

import httpx

from public_test import ACCESS, LOCAL, ROOT, URL, private_write

sys.path.insert(0, str(ROOT / "backend"))
from app.config import get_settings  # noqa: E402
from app.database import DB_PATH  # noqa: E402


def verify() -> dict:
    if get_settings().execution_context != "development":
        raise RuntimeError("Synthetic deployment checks require a development runtime.")
    base = URL.read_text().strip().removesuffix("/chat")
    access = json.loads(ACCESS.read_text())
    researcher = tuple(access["researcher"][key] for key in ("username", "password"))
    with sqlite3.connect(DB_PATH) as db:
        old_interactions = {row[0] for row in db.execute("SELECT id FROM interactionlog")}
    result = {"url": base + "/chat", "verificationOnly": True}
    with httpx.Client(base_url=base, timeout=90, follow_redirects=False) as client:
        client.get("/api/health").raise_for_status()
        for path in ("/admin", "/api/admin/corpus/status", "/api/admin/research/export/answers.csv"):
            assert client.get(path).status_code == 401, path
            assert client.get(path, auth=("researcher", "wrong")).status_code == 401, path
        page = client.get("/chat")
        page.raise_for_status()
        assert "www-authenticate" not in page.headers
        assert "Uni-Navigator" in page.text
        assets = re.findall(r'(?:src|href)="(/_next/[^" ]+)"', page.text)
        assert assets
        for asset in assets:
            client.get(asset.replace("&amp;", "&")).raise_for_status()
        status = client.get("/api/admin/corpus/status", auth=researcher)
        status.raise_for_status()
        corpus = status.json()
        assert corpus["vectorStoreProviderActive"] == "chroma"
        assert corpus["fallbackUsed"] is False
        assert corpus["embeddingProvider"] == "openai"
        assert corpus["chunkCount"] > 0
        result["corpus"] = {key: corpus[key] for key in (
            "vectorStoreProviderActive", "fallbackUsed", "embeddingProvider",
            "collectionName", "sourceCount", "chunkCount",
        )}
        client.get("/admin", auth=researcher).raise_for_status()
        round_id = "external-smoke-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        session_id = str(uuid.uuid4())
        response = client.post("/api/study/session/start", json={
            "sessionId": session_id, "roundId": round_id, "participantLabel": "P9999",
            "prototypeNoticeAcknowledged": True,
        })
        response.raise_for_status()
        assert response.json()["executionContext"] == "development"
        question = "What is the deadline for submitting a deferred examination request?"
        client.post("/api/study/log-event", json={
            "sessionId": session_id, "eventType": "question_submitted",
            "requestId": str(uuid.uuid4()), "metadata": {"syntheticVerification": True},
        }).raise_for_status()
        response = client.post("/api/chat", json={"sessionId": session_id, "question": question})
        response.raise_for_status()
        answer = response.json()
        assert answer["answer"] and answer["citations"]
        provided = {citation["label"] for citation in answer["citations"]}
        cited = set(re.findall(r"\[\d+\]", answer["answer"]))
        assert cited and cited <= provided
        assert all(citation["sourceType"] in {"official_policy", "official_student_guidance"}
                   for citation in answer["citations"])
        result["liveAnswer"] = {"interactionId": answer["interactionId"],
            "retrievalStatus": answer["retrievalStatus"], "citationCount": len(answer["citations"])}
        citation = answer["citations"][0]
        for action in ("citation_clicked", "evidence_panel_opened", "source_opened"):
            client.post("/api/study/evidence-use", json={
                "sessionId": session_id, "interactionId": answer["interactionId"],
                "citationId": citation["citationId"], "sourceId": citation["sourceId"],
                "chunkId": citation["chunkId"], "evidenceAction": action,
                "requestId": str(uuid.uuid4()),
                "notes": "Synthetic API deployment check, not observed participant behaviour.",
            }).raise_for_status()
        response = client.post("/api/study/session/complete", json={"sessionId": session_id})
        response.raise_for_status()
        assert response.json()["completedAt"]
        exports = {}
        for kind in ("participants", "timeline", "answers"):
            response = client.get(f"/api/admin/research/export/{kind}.csv", auth=researcher,
                params={"round_id": round_id, "participant": "P9999"})
            response.raise_for_status()
            rows = list(csv.DictReader(io.StringIO(response.text.lstrip("\ufeff"))))
            assert rows
            exports[kind] = rows
        assert len(exports["participants"]) == len(exports["answers"]) == 1
        assert exports["answers"][0]["answer"] == answer["answer"]
        event_types = {row["event_type"] for row in exports["timeline"]}
        assert {"citation_clicked", "evidence_opened", "source_opened", "session_completed"} <= event_types
        result.update({"roundId": round_id, "sessionId": session_id,
            "exports": {kind: len(rows) for kind, rows in exports.items()},
            "authenticationPassed": True, "publicChatPassed": True,
            "assetsPassed": True, "loggingPassed": True})
    with sqlite3.connect(DB_PATH) as db:
        current = {row[0] for row in db.execute("SELECT id FROM interactionlog")}
        assert old_interactions <= current
        assert answer["interactionId"] in current
        record = db.execute("SELECT answer_mode, ai_provider, ai_model FROM interactionlog WHERE id = ?",
            (answer["interactionId"],)).fetchone()
        assert record[0] == "live_llm" and record[1] == "openai"
        result["provider"] = {"answerMode": record[0], "aiProvider": record[1], "model": record[2]}
    result["historicalRecordsPreserved"] = True
    private_write(LOCAL / "verification.json", json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    print(json.dumps(verify(), indent=2))
