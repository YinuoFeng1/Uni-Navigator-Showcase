from datetime import datetime

from sqlmodel import Field, SQLModel

from app.utils.time import utc_now


class InteractionLog(SQLModel, table=True):
    id: str = Field(primary_key=True)
    session_id: str | None = None
    participant_label: str | None = None
    participant_id: str | None = None
    task_id: str | None = None
    condition: str
    question: str
    answer_id: str
    short_answer: str
    full_answer: str | None = None
    based_on: str | None = None
    limitations: str | None = None
    uncertainty: str | None = None
    escalation_guidance: str | None = None
    high_stakes_detected: bool | None = None
    escalation_category: str | None = None
    escalation_reasons_json: str | None = None
    uncertainty_level: str
    escalation_recommended: bool
    citation_count: int
    retrieval_status: str | None = None
    citation_ids: str | None = None
    citations_json: str | None = None
    source_ids: str | None = None
    retrieved_chunk_ids: str | None = None
    retrieval_trace_json: str | None = None
    retrieved_context_count: int | None = None
    escalation_guidance_present: bool | None = None
    sensitive_warning_shown: bool | None = None
    created_at: datetime = Field(default_factory=utc_now)
    time_to_first_answer_ms: int | None = None
    response_time_ms: int | None = None
    error_type: str | None = None
    embedding_provider: str | None = None
    embedding_model: str | None = None
    embedding_dimension: int | None = None
    vector_collection: str | None = None
    retrieval_partial_threshold: float | None = None
    retrieval_grounded_threshold: float | None = None
    retrieval_top_k: int | None = None
    retrieval_mode: str | None = None
    scope_decision: str | None = None
    scope_registry_version: str | None = None
    scope_registry_fingerprint: str | None = None
    scope_matched_topics: str | None = None
    corpus_manifest_fingerprint: str | None = None
    ai_provider: str | None = None
    ai_model: str | None = None
    ai_model_requested: str | None = None
    provider_response_model: str | None = None
    provider_response_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    token_usage_json: str | None = None
    answer_mode: str | None = None
    task_version: str | None = None
    app_version: str | None = None
    app_revision: str | None = None
    execution_context: str | None = None
    answer_strategy_version: str | None = None
    release_id: str | None = None
    release_version: str | None = None
    condition_id: str | None = None
    condition_version: str | None = None
    task_manifest_version: str | None = None
    runtime_config_fingerprint: str | None = None
    runtime_config_json: str | None = None
    prompt_template_version: str | None = None
    generation_temperature: float | None = None
    generation_max_tokens: int | None = None
    technical_run_id: str | None = None


class StudyEventLog(SQLModel, table=True):
    id: str = Field(primary_key=True)
    session_id: str | None = None
    participant_label: str | None = None
    interaction_id: str | None = None
    participant_id: str | None = None
    task_id: str | None = None
    condition: str | None = None
    event_type: str
    metadata_json: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    schema_version: str | None = None
    occurred_at: datetime | None = None
    recorded_at: datetime | None = None
    release_id: str | None = None
    condition_id: str | None = None
    app_revision: str | None = None
    runtime_config_fingerprint: str | None = None
    idempotency_key: str | None = None
    payload_json: str | None = None


class FeedbackLog(SQLModel, table=True):
    id: str = Field(primary_key=True)
    session_id: str | None = None
    participant_label: str | None = None
    task_id: str | None = None
    interaction_id: str | None = None
    answer_id: str
    rating: str
    comment: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class FinalTaskResponse(SQLModel, table=True):
    response_id: str = Field(primary_key=True)
    session_id: str
    participant_label: str | None = None
    task_id: str
    interaction_id: str | None = None
    final_decision_text: str
    confidence_rating: int
    would_contact_staff: str
    perceived_answer_supported: int
    perceived_task_difficulty: int | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    decision_appropriateness: str | None = None
    researcher_code: str | None = None


class EvidenceUse(SQLModel, table=True):
    evidence_use_id: str = Field(primary_key=True)
    session_id: str | None = None
    participant_label: str | None = None
    task_id: str | None = None
    interaction_id: str | None = None
    citation_id: str | None = None
    source_id: str | None = None
    chunk_id: str | None = None
    evidence_action: str
    evidence_relevance_rating: int | None = None
    evidence_support_rating: int | None = None
    user_marked_helpful: bool | None = None
    user_marked_confusing: bool | None = None
    notes: str | None = None
    created_at: datetime = Field(default_factory=utc_now)


class TrustChecklistSnapshot(SQLModel, table=True):
    trust_snapshot_id: str = Field(primary_key=True)
    session_id: str | None = None
    participant_label: str | None = None
    task_id: str | None = None
    interaction_id: str | None = None
    answer_clear: bool | None = None
    evidence_checked: bool | None = None
    source_supports_answer: bool | None = None
    uncertainty_noticed: bool | None = None
    would_contact_staff_if_needed: bool | None = None
    created_at: datetime = Field(default_factory=utc_now)


class StudySession(SQLModel, table=True):
    session_id: str = Field(primary_key=True)
    participant_label: str
    study_condition: str | None = None
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    current_task_id: str | None = None
    metadata_json: str | None = None
    prototype_notice_acknowledged: bool | None = None
    prototype_notice_acknowledged_at: datetime | None = None
    state: str | None = None
    release_id: str | None = None
    release_version: str | None = None
    condition_version: str | None = None
    runtime_config_fingerprint: str | None = None
    app_revision: str | None = None
