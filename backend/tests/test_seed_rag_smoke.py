import csv
import re
import shutil
from io import StringIO
from pathlib import Path

from sqlmodel import Session

from app.config import PROJECT_ROOT, get_settings
from app.database import engine
from app.models import InteractionLog
from app.scripts.ingest_corpus import ingest_corpus
from app.scripts.rag_smoke_test import run_rag_smoke_test
from app.services.corpus_loader import load_corpus
from app.services.retrieval_service import retrieve_policy_chunks

SEED_CORPUS_PATH = PROJECT_ROOT / "data" / "corpus"
SMOKE_QUESTIONS_PATH = PROJECT_ROOT / "data" / "evaluation" / "rag_smoke_questions.json"
EXPECTED_SEED_SOURCE_IDS = {
    "prepared-special-consideration",
    "prepared-course-withdrawal-census",
    "prepared-study-load-overload",
    "prepared-academic-progression",
    "prepared-fees-refunds-appeals",
}


def _configure_seed_rag(monkeypatch, tmp_path: Path) -> dict[str, int | str]:
    # Seed tests must not depend on privately downloaded official PDFs.
    corpus = tmp_path / "seed_corpus"
    corpus.mkdir()
    for source in SEED_CORPUS_PATH.glob("prepared-*.md"):
        shutil.copyfile(source, corpus / source.name)
    monkeypatch.setenv("CORPUS_PATH", str(corpus))
    monkeypatch.setenv("VECTOR_STORE_PATH", str(tmp_path / "vector_store"))
    monkeypatch.setenv("VECTOR_STORE_PROVIDER", "local_json")
    monkeypatch.setenv("EMBEDDING_PROVIDER", "mock")
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.setenv("RETRIEVAL_SOURCE_MODE", "prepared")
    get_settings.cache_clear()
    return ingest_corpus(source_type="prepared")


def _csv_rows(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(text)))


def _assert_citation_guardrails(answer: dict) -> None:
    citations = answer["citations"]
    if answer["retrievalStatus"] == "insufficient_evidence":
        assert citations == []
    for citation in citations:
        assert citation["chunkId"]
        assert citation["passage"]
        assert citation["label"]

    answer_labels = set(re.findall(r"\[\d+\]", answer["shortAnswer"]))
    citation_labels = {
        citation["label"] for citation in citations if citation.get("label")
    }
    assert answer_labels.issubset(citation_labels)

    if answer["retrievalStatus"] in {
        "insufficient_evidence",
        "partial_evidence",
        "individual_assessment",
        "ambiguous",
    }:
        assert answer["escalationGuidance"]


def _official_chunk(source_id: str, text: str) -> dict:
    return {
        "chunk_id": f"{source_id.replace('-', '_')}_chunk_001",
        "source_id": source_id,
        "title": "Official UQ Procedure",
        "document_name": "Official UQ Procedure",
        "section": "Relevant procedure",
        "url": "https://policies.uq.edu.au/",
        "source_type": "official_policy",
        "chunk_text": text,
        "page_start": 1,
        "page_end": 1,
        "score": 0.9,
        "active": True,
    }


def test_seed_corpus_files_can_be_loaded() -> None:
    documents = load_corpus(SEED_CORPUS_PATH, source_type="prepared")
    source_ids = {document.source_id for document in documents}

    assert EXPECTED_SEED_SOURCE_IDS.issubset(source_ids)
    assert len(documents) >= 5
    assert all(document.source_type == "prepared_policy" for document in documents)
    assert all("not official university advice" in document.text for document in documents)


def test_seed_ingestion_creates_chunks(monkeypatch, tmp_path: Path) -> None:
    summary = _configure_seed_rag(monkeypatch, tmp_path)

    get_settings.cache_clear()
    assert summary["documents_loaded"] >= 5
    assert summary["chunks_created"] >= 5
    assert summary["chunks_stored"] == summary["chunks_created"]
    assert summary["vector_store_provider"] == "local_json"
    assert summary["active_vector_store_provider"] == "local_json"
    assert summary["collection_name"] == "uni_navigator_policy_chunks"


def test_seed_retrieval_finds_expected_source(monkeypatch, tmp_path: Path) -> None:
    _configure_seed_rag(monkeypatch, tmp_path)

    results = retrieve_policy_chunks(
        "Can I apply for special consideration after illness during an exam?",
        top_k=5,
    )

    get_settings.cache_clear()
    assert any(
        result["source_id"] == "prepared-special-consideration"
        for result in results
    )


def test_rag_smoke_script_runs_with_seed_corpus(monkeypatch, tmp_path: Path) -> None:
    _configure_seed_rag(monkeypatch, tmp_path)

    summary = run_rag_smoke_test(SMOKE_QUESTIONS_PATH)

    get_settings.cache_clear()
    assert summary["questions"] >= 5
    assert summary["pass"] >= 4


def test_chat_high_stakes_seed_question_has_escalation_and_citations(
    monkeypatch,
    tmp_path: Path,
    client,
) -> None:
    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [
            _official_chunk(
                "uq-academic-progression-procedure",
                "A student who receives an academic progression notice may be "
                "asked to respond by the stated deadline.",
            )
        ],
    )

    response = client.post(
        "/api/chat",
        json={
            "question": "I received an academic progression notice and may need to appeal before a deadline. What should I do?",
            "participantId": "P-SEED",
            "taskId": "task_progression",
            "condition": "C_HIGHLIGHT",
        },
    )

    get_settings.cache_clear()
    assert response.status_code == 200
    answer = response.json()
    assert answer["retrievalStatus"] == "ambiguous"
    assert answer["citations"]
    assert answer["escalationRecommended"] is True
    assert answer["escalationGuidance"]
    assert answer["basedOn"]
    assert answer["limitations"]
    assert answer["uncertainty"]
    assert answer["highStakesDetected"] is True
    assert any(
        citation["sourceId"] == "uq-academic-progression-procedure"
        for citation in answer["citations"]
    )
    _assert_citation_guardrails(answer)


def test_out_of_corpus_empty_retrieval_does_not_fake_citations(
    monkeypatch,
    client,
) -> None:
    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [],
    )

    response = client.post(
        "/api/chat",
        json={"question": "Where can I book a xylophone practice room?"},
    )

    assert response.status_code == 200
    answer = response.json()
    assert answer["retrievalStatus"] == "insufficient_evidence"
    assert answer["citations"] == []
    _assert_citation_guardrails(answer)


def test_seed_rag_chat_logs_and_exports_citation_metadata(
    monkeypatch,
    tmp_path: Path,
    client,
) -> None:
    monkeypatch.setattr(
        "app.application.chat_orchestrator.retrieve_policy_chunks",
        lambda *args, **kwargs: [
            _official_chunk(
                "uq-removal-courses-special-circumstances-procedure",
                "A student may apply to remove a course in special circumstances "
                "after the census date.",
            )
        ],
    )

    chat_response = client.post(
        "/api/chat",
        json={
            "question": "If I withdraw after the census date, could there be fee consequences?",
            "participantId": "P-SEED-CSV",
            "condition": "C_HIGHLIGHT",
        },
    )
    assert chat_response.status_code == 200
    answer = chat_response.json()
    _assert_citation_guardrails(answer)

    with Session(engine) as session:
        log = session.get(InteractionLog, answer["interactionId"])

    assert log is not None
    assert log.retrieval_status == answer["retrievalStatus"]
    assert log.based_on == answer["basedOn"]
    assert log.limitations == answer["limitations"]
    assert log.uncertainty == answer["uncertainty"]
    assert log.escalation_guidance == answer.get("escalationGuidance")
    assert log.high_stakes_detected is True
    assert log.citation_count == len(answer["citations"])
    assert log.retrieved_context_count == len(answer["citations"])
    assert log.citation_ids and "c1" in log.citation_ids
    assert log.source_ids and "uq-removal-courses" in log.source_ids
    assert log.retrieved_chunk_ids and "uq_removal_courses" in log.retrieved_chunk_ids

    export_response = client.get("/api/admin/logs/export.csv")
    rows = _csv_rows(export_response.text)
    row = next(
        item
        for item in rows
        if item["row_type"] == "interaction"
        and item["interaction_id"] == answer["interactionId"]
    )

    get_settings.cache_clear()
    assert row["retrieval_status"] == answer["retrievalStatus"]
    assert row["based_on"] == answer["basedOn"]
    assert row["limitations"] == answer["limitations"]
    assert row["uncertainty"] == answer["uncertainty"]
    assert row["escalation_guidance"] == answer.get("escalationGuidance", "")
    assert row["high_stakes_detected"] == "true"
    assert row["citation_ids"]
    assert row["source_ids"]
    assert row["chunk_ids"]
    assert row["retrieved_context_count"] == str(len(answer["citations"]))
