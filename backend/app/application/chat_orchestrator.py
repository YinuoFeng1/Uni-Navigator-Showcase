from __future__ import annotations

from dataclasses import dataclass, replace
from time import monotonic
from typing import Any

from app.core.errors import ApplicationError
from app.core.runtime_config import RuntimeConfigSnapshot
from app.schemas import AssistantAnswer
from app.services.answer_strategies import AnswerStrategy, AnswerStrategyInput
from app.services.rag_evidence_service import (
    NO_CITATION_STATUSES,
    build_retrieved_context,
    citations_from_chunks,
    is_explicitly_out_of_scope,
    scope_response,
    select_official_policy_chunks,
    retrieval_trace_from_chunks,
    validate_answer_citations,
)
from app.services.corpus_scope_service import (
    apply_scope_to_retrieval_status,
    decide_corpus_scope,
    load_scope_registry,
)
from app.services.escalation_service import decide_escalation_category
from app.services.interaction_provenance import build_interaction_provenance
from app.services.policy_safety import assess_policy_safety
from app.services.retrieval_service import (
    classify_retrieval_status,
    retrieve_policy_chunks,
)
from app.utils.ids import make_id


@dataclass(frozen=True)
class ChatCommand:
    question: str
    session_id: str | None = None
    task_id: str | None = None
    condition_id: str | None = None


@dataclass(frozen=True)
class ServerChatContext:
    session_id: str
    task_id: str | None
    condition_id: str
    condition_version: str
    release_id: str
    release_version: str
    session_active: bool
    task_active: bool
    task_required: bool = True


@dataclass(frozen=True)
class OrchestratedChatResult:
    answer: AssistantAnswer
    time_to_first_answer_ms: int
    provenance: dict[str, Any]


class ChatOrchestrator:
    """Coordinates chat policy without SQL, FastAPI, or provider construction."""

    def __init__(
        self,
        *,
        settings: Any,
        runtime: RuntimeConfigSnapshot,
        answer_strategy: AnswerStrategy,
        embedding_provider: Any,
        vector_store: Any,
    ) -> None:
        self.settings = settings
        self.runtime = runtime
        self.answer_strategy = answer_strategy
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store

    def execute(
        self,
        command: ChatCommand,
        *,
        server_context: ServerChatContext | None = None,
    ) -> OrchestratedChatResult:
        started_at = monotonic()
        self._validate_context(command, server_context)
        safety = assess_policy_safety(command.question)
        registry = self._scope_registry()
        preliminary_scope = self._scope_decision(command.question, [], registry)

        if is_explicitly_out_of_scope(preliminary_scope):
            chunks: list[dict[str, Any]] = []
            scope_decision = preliminary_scope
        else:
            chunks = self._retrieve(command.question)
            chunks = select_official_policy_chunks(chunks)
            scope_decision = self._scope_decision(command.question, chunks, registry)

        retrieval_status = classify_retrieval_status(
            chunks, settings=self.settings
        )
        retrieval_status = apply_scope_to_retrieval_status(
            retrieval_status, scope_decision
        )
        escalation_decision = decide_escalation_category(
            question=command.question,
            retrieval_status=retrieval_status,
            scope_decision=scope_decision,
            high_stakes_detected=safety.high_stakes_detected,
            safety_categories=safety.categories,
        )
        if (
            escalation_decision.requires_individual_assessment
            and retrieval_status == "grounded"
        ):
            retrieval_status = "individual_assessment"

        citations = citations_from_chunks(chunks)
        if retrieval_status in NO_CITATION_STATUSES:
            citations = []
        retrieval_trace = retrieval_trace_from_chunks(chunks, citations)
        strategy_result = None
        try:
            strategy_input = AnswerStrategyInput(
                question=command.question,
                task_id=(
                    server_context.task_id if server_context else command.task_id
                ),
                condition_id=(
                    server_context.condition_id
                    if server_context
                    else command.condition_id
                ),
                citations=citations,
                retrieved_context=build_retrieved_context(citations),
                retrieval_status=retrieval_status,
                high_stakes_detected=safety.high_stakes_detected,
                escalation_decision=escalation_decision,
                runtime=self.runtime,
            )
            strategy_result = self.answer_strategy.generate(strategy_input)
            strategy_result = self._validate_with_one_revision(
                strategy_input,
                strategy_result,
                citations,
            )
        except ApplicationError as failure:
            failure.context.setdefault("retrieval_status", retrieval_status)
            failure.context.setdefault("retrieval_trace", retrieval_trace)
            failure.context.setdefault("scope_decision", scope_decision.decision)
            failure.context.setdefault(
                "escalation_recommended", escalation_decision.recommended
            )
            failure.context.setdefault(
                "escalation_category", escalation_decision.category
            )
            failure.context.setdefault(
                "escalation_reasons", escalation_decision.reasons
            )
            failure.context.setdefault(
                "high_stakes_detected", safety.high_stakes_detected
            )
            failure.context.setdefault(
                "citations",
                [
                    citation.model_dump(mode="json", by_alias=True)
                    for citation in citations
                ],
            )
            if strategy_result is not None:
                failure.context.setdefault("generated_answer", strategy_result.answer)
                failure.context.setdefault(
                    "provider_response_id",
                    strategy_result.strategy_provenance.get("provider_response_id"),
                )
                failure.context.setdefault(
                    "provider_response_model",
                    strategy_result.strategy_provenance.get("model_active"),
                )
                failure.context.setdefault(
                    "token_usage",
                    strategy_result.strategy_provenance.get("token_usage") or {},
                )
            raise
        answer = self._answer(
            strategy_result,
            scope_decision,
            escalation_decision,
        )
        provenance = build_interaction_provenance(
            settings=self.settings,
            task_id=server_context.task_id if server_context else command.task_id,
            scope_decision=scope_decision,
            escalation_decision=escalation_decision,
            provider_name=str(
                strategy_result.strategy_provenance.get("provider_active")
                or self.runtime.ai_provider
            ),
            provider_model=str(
                strategy_result.strategy_provenance.get("model_active")
                or self.runtime.ai_model
            ),
            vector_status=self.vector_store.status(),
            runtime_snapshot=self.runtime,
            strategy_version=strategy_result.strategy_version,
            strategy_provenance=strategy_result.strategy_provenance,
            retrieval_trace=retrieval_trace,
            server_context=server_context,
        )
        return OrchestratedChatResult(
            answer=answer,
            time_to_first_answer_ms=round((monotonic() - started_at) * 1000),
            provenance=provenance,
        )

    def _validate_with_one_revision(
        self,
        strategy_input: AnswerStrategyInput,
        strategy_result: Any,
        citations: list[Any],
    ) -> Any:
        try:
            validate_answer_citations(
                strategy_result.answer,
                citations,
                retrieval_status=strategy_result.retrieval_status,
            )
            return strategy_result
        except ApplicationError as failure:
            if failure.code != "citation_validation_failed":
                raise
            validation_detail = failure.researcher_safe_detail

        first_result = strategy_result
        strategy_result = self.answer_strategy.generate(
            strategy_input,
            previous_answer=first_result.answer,
            validation_feedback=validation_detail,
        )
        strategy_result = replace(
            strategy_result,
            strategy_provenance=_retry_provenance(
                first_result,
                strategy_result,
                validation_detail,
            ),
        )
        try:
            validate_answer_citations(
                strategy_result.answer,
                citations,
                retrieval_status=strategy_result.retrieval_status,
            )
        except ApplicationError as final_failure:
            provenance = strategy_result.strategy_provenance
            final_failure.context.update(
                {
                    "generated_answer": strategy_result.answer,
                    "provider_response_id": provenance.get(
                        "provider_response_id"
                    ),
                    "provider_response_ids": provenance.get(
                        "provider_response_ids"
                    )
                    or [],
                    "provider_response_model": provenance.get("model_active"),
                    "token_usage": provenance.get("token_usage") or {},
                    "citation_validation_retry_count": provenance.get(
                        "citation_validation_retry_count", 1
                    ),
                    "generation_attempts": provenance.get("generation_attempts")
                    or [],
                }
            )
            raise
        return strategy_result

    def _scope_registry(self) -> dict[str, Any]:
        try:
            return load_scope_registry(self.settings.scope_registry_path)
        except Exception as exc:
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail="corpus scope registry is unavailable",
            ) from exc

    def _scope_decision(
        self,
        question: str,
        chunks: list[dict[str, Any]],
        registry: dict[str, Any],
    ) -> Any:
        try:
            return decide_corpus_scope(
                question,
                chunks,
                registry,
                partial_threshold=self.runtime.retrieval_partial_threshold,
                grounded_threshold=self.runtime.retrieval_grounded_threshold,
            )
        except Exception as exc:
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail="corpus scope check failed",
            ) from exc

    def _retrieve(self, question: str) -> list[dict[str, Any]]:
        try:
            return retrieve_policy_chunks(
                question,
                top_k=self.runtime.retrieval_top_k,
                settings=self.settings,
                source_mode="official",
                embedding_provider=self.embedding_provider,
                vector_store=self.vector_store,
            )
        except Exception as exc:
            raise ApplicationError(
                "vector_store_unavailable",
                researcher_safe_detail="embedding or vector retrieval failed",
            ) from exc

    def _validate_context(
        self, command: ChatCommand, context: ServerChatContext | None
    ) -> None:
        participant = self.runtime.execution_context == "participant_study"
        if participant and self.runtime.answer_mode != "live_llm":
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail="participant study strategy is not live_llm",
            )
        if not participant:
            return
        if context is None or not context.session_active or (context.task_required and not context.task_active):
            raise ApplicationError(
                "invalid_state_transition",
                researcher_safe_detail="participant chat requires an active server session and task",
            )
        if command.session_id != context.session_id or command.task_id != context.task_id:
            raise ApplicationError(
                "client_context_mismatch",
                researcher_safe_detail="client session or task differs from server context",
            )
        if command.condition_id and command.condition_id != context.condition_id:
            raise ApplicationError(
                "client_context_mismatch",
                researcher_safe_detail="client condition differs from server context",
            )
        if (
            context.release_id != self.runtime.pilot_release_id
            or context.release_version != self.runtime.pilot_release_version
        ):
            raise ApplicationError(
                "release_component_mismatch",
                researcher_safe_detail="session release differs from runtime release",
            )

    @staticmethod
    def _answer(
        strategy_result: Any,
        scope_decision: Any,
        escalation_decision: Any,
    ) -> AssistantAnswer:
        if strategy_result.retrieval_status == "insufficient_evidence":
            uncertainty_level = "high"
        elif strategy_result.retrieval_status != "grounded":
            uncertainty_level = "medium"
        else:
            uncertainty_level = "low"
        next_step = strategy_result.escalation_guidance or (
            "Review the cited policy passages before acting."
        )
        return AssistantAnswer(
            id=make_id("answer"),
            interactionId=make_id("interaction"),
            answer=strategy_result.answer,
            shortAnswer=strategy_result.answer,
            basedOn=strategy_result.based_on,
            evidenceSummary=strategy_result.based_on,
            nextStep=next_step,
            limitations=strategy_result.limitations,
            uncertainty=strategy_result.uncertainty,
            uncertaintyLevel=uncertainty_level,
            escalationRecommended=escalation_decision.recommended,
            escalationCategory=escalation_decision.category,
            escalationReasons=escalation_decision.reasons,
            highStakesDetected=strategy_result.high_stakes_detected,
            citations=strategy_result.citations,
            retrievalStatus=strategy_result.retrieval_status,
            escalationGuidance=strategy_result.escalation_guidance,
            scopeDecision=scope_response(scope_decision),
        )


def _retry_provenance(
    first_result: Any,
    final_result: Any,
    validation_detail: str,
) -> dict[str, Any]:
    first = first_result.strategy_provenance
    final = final_result.strategy_provenance
    response_ids = [
        value
        for value in (
            first.get("provider_response_id"),
            final.get("provider_response_id"),
        )
        if value
    ]
    return {
        **final,
        "provider_response_ids": response_ids,
        "token_usage": _sum_usage(
            first.get("token_usage") or {},
            final.get("token_usage") or {},
        ),
        "citation_validation_retry_count": 1,
        "generation_attempts": [
            {
                "attempt": 1,
                "answer": first_result.answer,
                "provider_response_id": first.get("provider_response_id"),
                "model_active": first.get("model_active"),
                "token_usage": first.get("token_usage") or {},
                "validation_error": validation_detail,
            },
            {
                "attempt": 2,
                "answer": final_result.answer,
                "provider_response_id": final.get("provider_response_id"),
                "model_active": final.get("model_active"),
                "token_usage": final.get("token_usage") or {},
                "validation_error": None,
            },
        ],
    }


def _sum_usage(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    combined: dict[str, Any] = {}
    for key in first.keys() | second.keys():
        left = first.get(key)
        right = second.get(key)
        if isinstance(left, dict) or isinstance(right, dict):
            combined[key] = _sum_usage(
                left if isinstance(left, dict) else {},
                right if isinstance(right, dict) else {},
            )
        elif isinstance(left, (int, float)) or isinstance(right, (int, float)):
            combined[key] = (
                left if isinstance(left, (int, float)) else 0
            ) + (
                right if isinstance(right, (int, float)) else 0
            )
    return combined
