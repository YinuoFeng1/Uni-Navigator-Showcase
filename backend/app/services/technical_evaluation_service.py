from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from time import monotonic
from typing import Any, Protocol

from app.application.chat_orchestrator import ChatCommand, ChatOrchestrator
from app.core.errors import ApplicationError


@dataclass(frozen=True)
class TechnicalEvaluationRecord:
    run_id: str
    query_id: str
    repetition: int
    question: str
    task_id: str | None
    status: str
    answer_id: str | None
    interaction_id: str | None
    answer: str | None
    based_on: str | None
    limitations: str | None
    uncertainty: str | None
    retrieval_status: str | None
    scope_decision: str | None
    escalation_recommended: bool | None
    escalation_category: str | None
    escalation_reasons: list[str]
    high_stakes_detected: bool | None
    citations: list[dict[str, Any]]
    citation_count: int
    latency_ms: int
    error_type: str | None
    error_detail: str | None
    provenance: dict[str, Any]
    partition: str | None = None


class TechnicalEvaluationRepository(Protocol):
    def append(self, record: TechnicalEvaluationRecord) -> None:
        ...


class JsonlTechnicalEvaluationRepository:
    """Separate technical-run store; never used by participant CSV exports."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def append(self, record: TechnicalEvaluationRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as output:
            output.write(
                json.dumps(asdict(record), ensure_ascii=True, sort_keys=True) + "\n"
            )


class TechnicalEvaluationService:
    def __init__(
        self,
        orchestrator: ChatOrchestrator,
        repository: TechnicalEvaluationRepository,
    ) -> None:
        self.orchestrator = orchestrator
        self.repository = repository

    def run(
        self,
        *,
        run_id: str,
        query_id: str,
        question: str,
        repetition: int = 1,
        task_id: str | None = None,
        partition: str | None = None,
        participant_session_id: str | None = None,
    ) -> TechnicalEvaluationRecord:
        runtime = self.orchestrator.runtime
        if participant_session_id:
            raise ApplicationError(
                "client_context_mismatch",
                researcher_safe_detail="technical evaluation cannot use participant session IDs",
            )
        if runtime.execution_context != "technical_evaluation":
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail="runtime is not configured for technical evaluation",
            )
        if runtime.answer_mode != "live_llm":
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail="technical evaluation requires live_llm",
            )
        if repetition < 1:
            raise ValueError("repetition must be positive")

        started_at = monotonic()
        try:
            result = self.orchestrator.execute(
                ChatCommand(question=question, task_id=task_id),
                server_context=None,
            )
        except ApplicationError as failure:
            record = self._failure_record(
                run_id=run_id,
                query_id=query_id,
                repetition=repetition,
                question=question,
                task_id=task_id,
                partition=partition,
                latency_ms=round((monotonic() - started_at) * 1000),
                failure=failure,
            )
            self.repository.append(record)
            return record

        provenance = {
            **result.provenance,
            "execution_context": "technical_evaluation",
            "technical_run_id": run_id,
        }
        answer = result.answer
        record = TechnicalEvaluationRecord(
            run_id=run_id,
            query_id=query_id,
            repetition=repetition,
            question=question,
            task_id=task_id,
            status="success",
            answer_id=answer.id,
            interaction_id=answer.interactionId,
            answer=answer.answer,
            based_on=answer.basedOn,
            limitations=answer.limitations,
            uncertainty=answer.uncertainty,
            retrieval_status=answer.retrievalStatus,
            scope_decision=(
                answer.scopeDecision.decision if answer.scopeDecision else None
            ),
            escalation_recommended=answer.escalationRecommended,
            escalation_category=answer.escalationCategory,
            escalation_reasons=answer.escalationReasons,
            high_stakes_detected=answer.highStakesDetected,
            citations=[
                citation.model_dump(mode="json", by_alias=True)
                for citation in answer.citations
            ],
            citation_count=len(answer.citations),
            latency_ms=result.time_to_first_answer_ms,
            error_type=None,
            error_detail=None,
            provenance=provenance,
            partition=partition,
        )
        self.repository.append(record)
        return record

    def _failure_record(
        self,
        *,
        run_id: str,
        query_id: str,
        repetition: int,
        question: str,
        task_id: str | None,
        partition: str | None,
        latency_ms: int,
        failure: ApplicationError,
    ) -> TechnicalEvaluationRecord:
        context = dict(failure.context)
        generated_answer = context.get("generated_answer")
        if not isinstance(generated_answer, str) or not generated_answer.strip():
            generated_answer = None
        citations = context.get("citations")
        if not isinstance(citations, list):
            citations = []
        escalation_reasons = context.get("escalation_reasons")
        if not isinstance(escalation_reasons, list):
            escalation_reasons = []
        provenance = {
            "execution_context": "technical_evaluation",
            "technical_run_id": run_id,
            "runtime_config": self.orchestrator.runtime.canonical_dict(),
            "runtime_config_fingerprint": (
                self.orchestrator.runtime.runtime_config_fingerprint
            ),
            "retrieval_trace": context.get("retrieval_trace") or [],
            "provider_response_id": context.get("provider_response_id"),
            "provider_response_ids": context.get("provider_response_ids") or [],
            "provider_response_model": context.get("provider_response_model"),
            "token_usage": context.get("token_usage") or {},
            "citation_validation_retry_count": context.get(
                "citation_validation_retry_count", 0
            ),
            "generation_attempts": context.get("generation_attempts") or [],
        }
        return TechnicalEvaluationRecord(
            run_id=run_id,
            query_id=query_id,
            repetition=repetition,
            question=question,
            task_id=task_id,
            status="error",
            answer_id=None,
            interaction_id=None,
            answer=generated_answer,
            based_on=None,
            limitations=None,
            uncertainty=None,
            retrieval_status=context.get("retrieval_status"),
            scope_decision=context.get("scope_decision"),
            escalation_recommended=context.get("escalation_recommended"),
            escalation_category=context.get("escalation_category"),
            escalation_reasons=escalation_reasons,
            high_stakes_detected=context.get("high_stakes_detected"),
            citations=citations,
            citation_count=len(citations),
            latency_ms=latency_ms,
            error_type=failure.code,
            error_detail=failure.researcher_safe_detail,
            provenance=provenance,
            partition=partition,
        )
