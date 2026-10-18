import json
from time import monotonic

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session

from app.database import get_session
from app.config import get_settings
from app.models import InteractionLog
from app.schemas import AssistantAnswer, ChatRequest
from app.application.chat_orchestrator import ChatCommand, ServerChatContext
from app.core.errors import ApplicationError
from app.models import StudySession
from app.services.chat_session_service import bind_write, is_chat_session
from app.services.manifest_service import manifest_checksum
from app.utils.ids import make_id

router = APIRouter()


@router.post(
    "/chat", response_model=AssistantAnswer, response_model_exclude_none=True
)
def chat(
    request: ChatRequest,
    http_request: Request,
    session: Session = Depends(get_session),
) -> AssistantAnswer:
    request_started_at = monotonic()
    settings = get_settings()
    container = getattr(http_request.app.state, "container", None)
    bound_session = bind_write(session, request)
    try:
        if container is None:
            raise ApplicationError(
                "configuration_error",
                researcher_safe_detail="application container is not ready",
            )
        if _is_formal_participant_runtime(settings):
            server_context, study_session = _resolve_server_context(
                session, request, container, settings
            )
        else:
            server_context = None
            study_session = bound_session
            if is_chat_session(study_session) and study_session.runtime_config_fingerprint != container.runtime.runtime_config_fingerprint:
                raise ApplicationError(
                    "release_component_mismatch",
                    researcher_safe_detail="session runtime fingerprint changed",
                )
        result = container.chat_orchestrator.execute(
            ChatCommand(
                question=request.question,
                session_id=request.sessionId,
                task_id=request.taskId,
                condition_id=request.condition,
            ),
            server_context=server_context,
        )
        answer = result.answer
        time_to_first_answer_ms = result.time_to_first_answer_ms
        response_time_ms = result.time_to_first_answer_ms
        provenance = result.provenance
    except ApplicationError as failure:
        failure.correlation_id = failure.correlation_id or make_id("interaction")
        logged = _record_application_failure(
            session,
            request,
            failure,
            settings,
            container,
            response_time_ms=round((monotonic() - request_started_at) * 1000),
        )
        raise _application_http_error(failure, logged=logged) from failure
    except Exception as exc:
        failure = ApplicationError(
            "system_failure",
            researcher_safe_detail="unhandled chat orchestration failure",
            correlation_id=make_id("interaction"),
        )
        logged = _record_application_failure(
            session,
            request,
            failure,
            settings,
            container,
            response_time_ms=round((monotonic() - request_started_at) * 1000),
        )
        raise _application_http_error(failure, logged=logged) from exc

    participant_label = (
        study_session.participant_label if study_session else request.participantLabel
    )
    authoritative_condition = (
        study_session.study_condition if study_session else request.condition
    )
    retrieval_trace = provenance.get("retrieval_trace") or []
    session.add(
        InteractionLog(
            id=answer.interactionId,
            session_id=request.sessionId,
            participant_label=participant_label,
            participant_id=request.participantId,
            task_id=request.taskId,
            condition=authoritative_condition or request.condition,
            question=request.question,
            answer_id=answer.id,
            short_answer=answer.shortAnswer,
            full_answer=answer.answer,
            based_on=answer.basedOn,
            limitations=answer.limitations,
            uncertainty=answer.uncertainty,
            escalation_guidance=answer.escalationGuidance,
            high_stakes_detected=answer.highStakesDetected,
            escalation_category=answer.escalationCategory,
            escalation_reasons_json=json.dumps(
                answer.escalationReasons,
                ensure_ascii=True,
                sort_keys=True,
            ),
            uncertainty_level=answer.uncertaintyLevel,
            escalation_recommended=answer.escalationRecommended,
            citation_count=len(answer.citations),
            retrieval_status=answer.retrievalStatus,
            citation_ids=json.dumps(
                [
                    item.citationId or item.id
                    for item in answer.citations
                    if item.citationId or item.id
                ]
            ),
            citations_json=json.dumps(
                [item.model_dump(mode="json") for item in answer.citations],
                ensure_ascii=True,
                sort_keys=True,
            ),
            source_ids=json.dumps(
                [item.sourceId for item in answer.citations if item.sourceId]
            ),
            retrieved_chunk_ids=json.dumps(
                [
                    item.get("chunk_id")
                    for item in retrieval_trace
                    if isinstance(item, dict) and item.get("chunk_id")
                ]
            ),
            retrieval_trace_json=json.dumps(
                retrieval_trace,
                ensure_ascii=True,
                sort_keys=True,
            ),
            retrieved_context_count=len(answer.citations),
            escalation_guidance_present=bool(answer.escalationGuidance),
            sensitive_warning_shown=request.sensitiveWarningShown,
            time_to_first_answer_ms=time_to_first_answer_ms,
            response_time_ms=response_time_ms,
            error_type=None,
            embedding_provider=provenance["embedding_provider"],
            embedding_model=provenance["embedding_model"],
            embedding_dimension=provenance["embedding_dimension"],
            vector_collection=provenance["vector_collection"],
            retrieval_partial_threshold=provenance[
                "retrieval_partial_threshold"
            ],
            retrieval_grounded_threshold=provenance[
                "retrieval_grounded_threshold"
            ],
            retrieval_top_k=provenance["retrieval_top_k"],
            retrieval_mode=provenance["retrieval_mode"],
            scope_decision=provenance["scope_decision"],
            scope_registry_version=provenance["scope_registry_version"],
            scope_registry_fingerprint=provenance[
                "scope_registry_fingerprint"
            ],
            scope_matched_topics=json.dumps(provenance["scope_matched_topics"]),
            corpus_manifest_fingerprint=provenance[
                "corpus_manifest_fingerprint"
            ],
            ai_provider=provenance["ai_provider"],
            ai_model=provenance["ai_model"],
            ai_model_requested=provenance.get("ai_model_requested"),
            provider_response_model=provenance.get("provider_response_model"),
            provider_response_id=provenance.get("provider_response_id"),
            input_tokens=provenance.get("input_tokens"),
            output_tokens=provenance.get("output_tokens"),
            total_tokens=provenance.get("total_tokens"),
            token_usage_json=json.dumps(
                provenance.get("token_usage") or {},
                ensure_ascii=True,
                sort_keys=True,
            ),
            answer_mode=provenance["answer_mode"],
            task_version=provenance["task_version"],
            app_version=provenance["app_version"],
            app_revision=provenance["app_revision"],
            execution_context=provenance.get("execution_context"),
            answer_strategy_version=provenance.get("answer_strategy_version"),
            release_id=provenance.get("release_id"),
            release_version=provenance.get("release_version"),
            condition_id=provenance.get("condition_id"),
            condition_version=provenance.get("condition_version"),
            task_manifest_version=provenance.get("task_manifest_version"),
            runtime_config_fingerprint=provenance.get(
                "runtime_config_fingerprint"
            ),
            runtime_config_json=json.dumps(
                provenance.get("runtime_config") or {},
                ensure_ascii=True,
                sort_keys=True,
            ),
            prompt_template_version=provenance.get("prompt_template_version"),
            generation_temperature=provenance.get("generation_temperature"),
            generation_max_tokens=provenance.get("generation_max_tokens"),
            technical_run_id=provenance.get("technical_run_id"),
        )
    )
    if _is_formal_participant_runtime(settings) and container is not None:
        try:
            container.events.append(
                session,
                event_type="interaction_served",
                payload={
                    "answer_mode": provenance.get("answer_mode"),
                    "citation_count": len(answer.citations),
                    "retrieval_status": answer.retrievalStatus,
                    "escalation_recommended": answer.escalationRecommended,
                    "escalation_category": answer.escalationCategory,
                    "escalation_reasons": answer.escalationReasons,
                },
                session_id=request.sessionId,
                participant_label=participant_label,
                task_id=request.taskId,
                interaction_id=answer.interactionId,
                release_id=provenance.get("release_id"),
                condition_id=provenance.get("condition_id"),
                app_revision=provenance.get("app_revision"),
                runtime_config_fingerprint=provenance.get(
                    "runtime_config_fingerprint"
                ),
                idempotency_key=f"interaction-served:{answer.interactionId}",
            )
        except Exception as exc:
            session.rollback()
            raise _application_http_error(
                ApplicationError(
                    "provenance_write_failed",
                    researcher_safe_detail="interaction event could not be written",
                    correlation_id=answer.interactionId,
                ),
                logged=False,
            ) from exc
    try:
        session.commit()
    except Exception as exc:
        session.rollback()
        raise _application_http_error(
            ApplicationError(
                "provenance_write_failed",
                researcher_safe_detail="interaction log could not be committed",
                correlation_id=answer.interactionId,
            ),
            logged=False,
        ) from exc

    return answer


def _is_formal_participant_runtime(settings: object) -> bool:
    return (
        getattr(settings, "study_mode", "development") == "pilot"
        and getattr(settings, "execution_context", "development")
        == "participant_study"
    )


def _resolve_server_context(
    session: Session,
    request: ChatRequest,
    container: object,
    settings: object,
) -> tuple[ServerChatContext, StudySession]:
    if not request.sessionId:
        raise ApplicationError(
            "client_context_mismatch",
            researcher_safe_detail="participant chat has no session ID",
        )
    study_session = session.get(StudySession, request.sessionId)
    if not study_session:
        raise ApplicationError(
            "client_context_mismatch",
            researcher_safe_detail="participant session does not exist",
        )
    release = container.releases.resolve_active_release(require_frozen=True)
    condition_manifest = container.conditions.load_manifest()
    release_report = container.releases.validate(
        condition_manifest_checksum=manifest_checksum(condition_manifest),
    )
    if not release_report.valid:
        raise ApplicationError(
            "release_component_mismatch",
            researcher_safe_detail="active release or condition checksum changed",
        )
    container.releases.validate_runtime_binding(
        release=release,
        settings=settings,
        vector_status=container.chat_orchestrator.vector_store.status(),
    )
    container.releases.validate_session_binding(
        session_release_id=study_session.release_id,
        session_release_version=study_session.release_version,
        release=release,
    )
    active_fingerprint = container.runtime.runtime_config_fingerprint
    if study_session.runtime_config_fingerprint != active_fingerprint:
        raise ApplicationError(
            "release_component_mismatch",
            researcher_safe_detail="session runtime fingerprint differs from active runtime",
        )
    condition_id = study_session.study_condition or ""
    condition = container.conditions.get_condition(condition_id)
    chat_workflow = is_chat_session(study_session)
    task_id = None if chat_workflow else study_session.current_task_id or ""
    return (
        ServerChatContext(
            session_id=study_session.session_id,
            task_id=task_id,
            condition_id=condition_id,
            condition_version=str(condition.get("condition_version") or ""),
            release_id=str(release["release_id"]),
            release_version=str(release["release_version"]),
            session_active=study_session.state == "active",
            task_active=bool(task_id),
            task_required=not chat_workflow,
        ),
        study_session,
    )


def _record_application_failure(
    session: Session,
    request: ChatRequest,
    failure: ApplicationError,
    settings: object,
    container: object | None,
    *,
    response_time_ms: int,
) -> bool:
    if container is None:
        return False
    event_type = failure.definition.event_type
    candidate_payload = {
        "error_code": failure.code,
        "task_id": request.taskId,
        "failure_stage": failure.definition.category,
        "release_status": "unavailable",
        "context_field": "server_context",
        "researcher_action": "Pause the task and review the preflight report.",
        "response_time_ms": response_time_ms,
        "retrieval_status": failure.context.get(
            "retrieval_status", "not_completed"
        ),
        "retrieval_trace": failure.context.get("retrieval_trace") or [],
        "token_usage": failure.context.get("token_usage") or {},
        "runtime_config": (
            container.runtime.canonical_dict()
            if getattr(container, "runtime", None) is not None
            else {}
        ),
    }
    for key in (
        "provider_response_id",
        "provider_response_model",
    ):
        if key in failure.context and failure.context[key] is not None:
            candidate_payload[key] = failure.context[key]
    from app.services.event_repository import EVENT_PAYLOAD_ALLOWLISTS

    allowed = EVENT_PAYLOAD_ALLOWLISTS.get(event_type, set())
    payload = {key: value for key, value in candidate_payload.items() if key in allowed}
    try:
        container.events.append(
            session,
            event_type=event_type,
            payload=payload,
            session_id=request.sessionId,
            participant_label=request.participantLabel,
            task_id=request.taskId,
            interaction_id=failure.correlation_id,
            release_id=getattr(
                getattr(container, "runtime", None),
                "pilot_release_id",
                None,
            ),
            condition_id=request.condition,
            app_revision=getattr(settings, "app_revision", None),
            runtime_config_fingerprint=getattr(
                getattr(container, "runtime", None),
                "runtime_config_fingerprint",
                None,
            ),
            idempotency_key=f"failure:{failure.correlation_id}",
        )
        session.commit()
        return True
    except Exception:
        session.rollback()
        return False


def _application_http_error(
    failure: ApplicationError, *, logged: bool
) -> HTTPException:
    detail = failure.safe_payload()
    detail.update(
        {
            "interactionId": failure.correlation_id,
            "failureCategory": failure.definition.category,
            "failureStage": failure.definition.event_type,
            "systemFailureLogged": logged,
        }
    )
    return HTTPException(status_code=failure.definition.http_status, detail=detail)
