from pathlib import Path
import os
import shutil
import sys

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

TEST_DB_PATH = BACKEND_ROOT / ".test-data" / "uni_navigator_test.db"
TEST_VECTOR_PATH = BACKEND_ROOT / ".test-data" / "vector_store"
TEST_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()
os.environ["UNI_NAVIGATOR_DB_PATH"] = str(TEST_DB_PATH)
os.environ["AI_PROVIDER"] = "openai"
os.environ["OPENAI_API_KEY"] = "test-key-not-used"
os.environ["EXECUTION_CONTEXT"] = "development"
os.environ["EMBEDDING_PROVIDER"] = "mock"
os.environ["VECTOR_STORE_PROVIDER"] = "local_json"
os.environ["VECTOR_STORE_PATH"] = str(TEST_VECTOR_PATH)
os.environ["VECTOR_STORE_COLLECTION"] = "uni_navigator_policy_chunks"
os.environ["CORPUS_PATH"] = str(BACKEND_ROOT / ".test-data" / "corpus")
os.environ["RETRIEVAL_PARTIAL_SCORE_THRESHOLD"] = "0.15"
os.environ["RETRIEVAL_GROUNDED_SCORE_THRESHOLD"] = "0.35"
os.environ["RETRIEVAL_SOURCE_MODE"] = "official"
os.environ["STUDY_MODE"] = "development"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.database import engine
from app.models import (
    EvidenceUse,
    FeedbackLog,
    FinalTaskResponse,
    InteractionLog,
    StudyEventLog,
    StudySession,
    TrustChecklistSnapshot,
)
from main import app
from app.services.ai_provider import AIProviderResult
from app.services.answer_strategies import LiveLlmAnswerStrategy


class FakeOpenAIProvider:
    provider_name = "openai"

    def generate_answer(
        self,
        question: str,
        *,
        retrieved_context: str | None = None,
        citation_labels: list[str] | None = None,
        retrieval_status: str = "insufficient_evidence",
    ) -> AIProviderResult:
        labels = citation_labels or []
        if labels:
            passage = next(
                (
                    line.removeprefix("passage: ").strip()
                    for line in (retrieved_context or "").splitlines()
                    if line.startswith("passage: ")
                ),
                "The retrieved passage addresses the question.",
            ).rstrip(".")
            answer = f"{passage} {labels[0]}."
            if retrieval_status == "individual_assessment":
                answer += (
                    " Your personal outcome needs confirmation by authorised "
                    "university staff."
                )
            elif retrieval_status in {"partial_evidence", "ambiguous"}:
                answer += (
                    " The retrieved official policy evidence does not establish "
                    "every requested detail."
                )
        else:
            answer = (
                "I do not have enough matching official policy evidence to answer "
                "this question. Contact authorised university staff before acting."
            )
        return AIProviderResult(
            text=answer,
            provider_name="openai",
            model_name="test-openai-model",
            provider_mode="openai",
            retrieval_status=retrieval_status,
            limitations="Limited to the retrieved official policy evidence.",
            provider_response_id="resp_test_fixture",
            token_usage={
                "input_tokens": 120,
                "output_tokens": 30,
                "total_tokens": 150,
            },
        )


@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        container = test_client.app.state.container
        container.chat_orchestrator.answer_strategy = LiveLlmAnswerStrategy(
            FakeOpenAIProvider()
        )
        with Session(engine) as session:
            session.exec(delete(EvidenceUse))
            session.exec(delete(FeedbackLog))
            session.exec(delete(FinalTaskResponse))
            session.exec(delete(StudyEventLog))
            session.exec(delete(InteractionLog))
            session.exec(delete(StudySession))
            session.exec(delete(TrustChecklistSnapshot))
            session.commit()
        if TEST_VECTOR_PATH.exists():
            shutil.rmtree(TEST_VECTOR_PATH)
        TEST_VECTOR_PATH.mkdir(parents=True, exist_ok=True)
        yield test_client
