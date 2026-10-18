from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from app.core.errors import ApplicationError
from app.core.runtime_config import RuntimeConfigSnapshot
from app.schemas import Citation
from app.services.ai_provider import AIProviderError, AIProviderResult
from app.services.escalation_service import (
    EscalationDecision,
    escalation_guidance,
)


@dataclass(frozen=True)
class AnswerStrategyInput:
    question: str
    task_id: str | None
    condition_id: str | None
    citations: list[Citation]
    retrieved_context: str
    retrieval_status: str
    high_stakes_detected: bool
    escalation_decision: EscalationDecision
    runtime: RuntimeConfigSnapshot


@dataclass(frozen=True)
class AnswerStrategyResult:
    answer: str
    based_on: str
    limitations: str
    uncertainty: str
    escalation_guidance: str | None
    high_stakes_detected: bool
    citations: list[Citation]
    retrieval_status: str
    answer_mode: str
    strategy_version: str
    strategy_provenance: dict[str, Any]


class AnswerStrategy(Protocol):
    answer_mode: str
    strategy_version: str

    def generate(
        self,
        context: AnswerStrategyInput,
        *,
        previous_answer: str | None = None,
        validation_feedback: str | None = None,
    ) -> AnswerStrategyResult:
        ...


class LiveLlmAnswerStrategy:
    answer_mode = "live_llm"
    strategy_version = "live-rag-v5"

    def __init__(self, provider: Any) -> None:
        if getattr(provider, "provider_name", None) != "openai":
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail="live RAG requires the OpenAI answer provider",
            )
        self.provider = provider

    def generate(
        self,
        context: AnswerStrategyInput,
        *,
        previous_answer: str | None = None,
        validation_feedback: str | None = None,
    ) -> AnswerStrategyResult:
        provider_kwargs: dict[str, Any] = {
            "retrieved_context": context.retrieved_context or None,
            "citation_labels": [
                item.label for item in context.citations if item.label
            ],
            "retrieval_status": context.retrieval_status,
        }
        if previous_answer is not None and validation_feedback is not None:
            provider_kwargs.update(
                previous_answer=previous_answer,
                validation_feedback=validation_feedback,
            )
        try:
            provider_result = self.provider.generate_answer(
                context.question,
                **provider_kwargs,
            )
        except AIProviderError as exc:
            raise ApplicationError(
                "provider_unavailable",
                researcher_safe_detail="OpenAI answer generation failed",
            ) from exc
        except Exception as exc:
            raise ApplicationError(
                "provider_unavailable",
                researcher_safe_detail="answer provider raised an unexpected error",
            ) from exc
        if not isinstance(provider_result, AIProviderResult):
            raise ApplicationError(
                "provider_unavailable",
                researcher_safe_detail="AI provider returned an unsupported contract",
            )
        if provider_result.provider_mode != "openai":
            raise ApplicationError(
                "provider_unavailable",
                researcher_safe_detail="AI provider did not return a usable answer",
            )
        if (
            context.runtime.execution_context == "participant_study"
            and provider_result.model_name != context.runtime.ai_model
        ):
            raise ApplicationError(
                "release_component_mismatch",
                researcher_safe_detail="OpenAI response model differs from frozen model snapshot",
            )
        if context.runtime.execution_context == "participant_study":
            usage = provider_result.token_usage
            required_usage = {"input_tokens", "output_tokens", "total_tokens"}
            if not provider_result.provider_response_id or not required_usage <= set(
                usage
            ):
                raise ApplicationError(
                    "provider_unavailable",
                    researcher_safe_detail="OpenAI response omitted reproducibility metadata",
                )
        return AnswerStrategyResult(
            answer=provider_result.text,
            based_on=_based_on(context.citations),
            limitations=provider_result.limitations,
            uncertainty=_uncertainty(context.retrieval_status),
            escalation_guidance=escalation_guidance(context.escalation_decision),
            high_stakes_detected=context.high_stakes_detected,
            citations=context.citations,
            retrieval_status=context.retrieval_status,
            answer_mode="live_llm",
            strategy_version=self.strategy_version,
            strategy_provenance={
                "provider_active": provider_result.provider_name,
                "model_requested": context.runtime.ai_model,
                "model_active": provider_result.model_name,
                "provider_mode": "openai",
                "provider_response_id": provider_result.provider_response_id,
                "token_usage": provider_result.token_usage,
            },
        )


def _based_on(citations: list[Citation]) -> str:
    if not citations:
        return "No matching official policy evidence was available for this answer."
    return f"Based on {len(citations)} retrieved official policy passage(s)."


def _uncertainty(retrieval_status: str) -> str:
    if retrieval_status == "grounded":
        return "The retrieved official evidence directly supports the answer."
    if retrieval_status == "individual_assessment":
        return "The policy rule is supported, but authorised staff must confirm the personal outcome."
    if retrieval_status == "partial_evidence":
        return "Official evidence supports part of the answer, but not every requested detail."
    if retrieval_status == "ambiguous":
        return "The question combines a supported policy point with an unresolved issue."
    return "There was not enough matching official policy evidence to answer safely."
