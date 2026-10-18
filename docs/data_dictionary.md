# Research Data Dictionary

This dictionary covers current Chat records and retained backend contracts. Chat creates researcher-controlled sessions, interactions, evidence activity, events, and optional feedback; it creates no tasks, trust checklists, or final decisions. Historical records remain readable. Runtime prerequisites are described in [pilot_runbook.md](pilot_runbook.md).

## Participant Tables

`StudySession` stores a research code, assigned condition, timestamps, current task, notice acknowledgement, lifecycle state, frozen release ID/version, condition version, runtime fingerprint, and app revision.

For the Chat workflow, `metadata_json` contains `workflow: chat`, `roundId`, and `executionContext`. `participant_label` is a code such as P01, `current_task_id` is null, and one internal presentation identifier is used. `session_started` and `session_completed` events accompany acknowledged lifecycle writes. Replaying the same session start/end does not create another session.

`InteractionLog` stores the participant question, complete served answer, complete citation objects, and the ordered retrieval trace. The trace records rank, score, distance, source ID, chunk ID, pages, and the answer-local citation label. Reproducibility fields include the requested and returned model snapshots, provider response ID, prompt version, token usage, total response time, corpus fingerprint, scope registry version and fingerprint, embedding model and dimension, Chroma collection, thresholds, `top_k`, generation settings, release and condition versions, app revision, the complete non-secret runtime snapshot, and its fingerprint. `error_type` is empty for a successful interaction.

`FinalTaskResponse` is the purpose-specific store for participant decision text, confidence, staff-contact judgement, perceived support, optional difficulty, and notes. Generic events must not duplicate the decision text.

`EvidenceUse`, `TrustChecklistSnapshot`, and `FeedbackLog` retain their existing purpose-specific meanings.

## Event Envelope

New pilot-critical `StudyEventLog` rows may include:

- `event_id`, `event_type`, `schema_version`
- `occurred_at`, `recorded_at`
- `session_id`, `task_id`, `interaction_id`
- `release_id`, `condition_id`, `app_revision`
- `runtime_config_fingerprint`, `idempotency_key`
- allowlisted `payload`

Chat failure events include `error_code`, elapsed response time, any available retrieval trace and provider metadata, and the complete non-secret runtime snapshot. Their event envelope records the active release, app revision, and runtime fingerprint. Failed questions, provider error bodies, API keys, and unserved model output are not duplicated into failure metadata.

Generic payloads exclude participant questions, final decisions, API keys, provider response bodies, stack traces, and raw SQL errors. Existing `metadata_json` remains readable to preserve historical research records; this does not require retaining obsolete user-facing workflows.

For retryable Chat writes, `idempotency_key` stores the client operation ID and `payload_json` stores a request hash and acknowledgement receipt. The corresponding event's research metadata remains in `metadata_json`. Client `timestamp` is the occurrence time; server recording time is separate. Client clock differences may affect elapsed-time comparisons.

Evidence actions are distinct: `citation_clicked` means an inline answer reference was activated; `evidence_opened` mirrors `EvidenceUse.evidence_action=evidence_panel_opened`; `source_opened` means either original-file link was activated. They do not establish that a participant read or understood the evidence. `source_checked` is a participant's explicit mark, not an independent correctness rating.

## Chat Exports

All three exports filter by `round_id` and `participant`, with common columns `round_id`, `participant_code`, `session_id`, and `execution_context`:

- `participants`: one row per session, start/end/duration, answer and question-attempt counts, separate evidence-action counts, feedback and error counts, runtime fingerprint.
- `timeline`: one row per event, original and recorded timestamps, elapsed seconds, event/interaction/citation/source/chunk identifiers and metadata. EvidenceUse rows are not counted a second time.
- `answers`: one row per successfully served interaction, question and full answer, supporting explanation, limitations, uncertainty, escalation, complete citations, retrieval trace, response time, model/prompt/corpus/configuration provenance and feedback. Failed generations appear in the timeline, not as fabricated answers.

Exports exclude legacy task sessions and technical evaluation runs. The existing historical exports remain unchanged. UTF-8 BOM supports spreadsheet opening, and formula-like cell text is escaped.

## Technical Evaluation

Dynamic evaluation uses `TechnicalEvaluationRecord` and the separate `data/evaluation/technical_runs.jsonl` repository by default. Each attempt records the run/query/repetition identifiers, synthetic question, task category, success or error status, full generated answer, limitations, uncertainty, retrieval and scope status, escalation decision, complete citation objects, latency, error type, and frozen provenance. Provenance includes the ordered retrieval ranks, scores, source and chunk IDs, pages, requested and returned model, prompt version, token usage, corpus and scope fingerprints, generation settings, app revision, and complete non-secret runtime snapshot.

The versioned 50-question end-to-end dataset is `data/evaluation/end_to_end_technical_evaluation.json`. Batch reports and blank manual coding sheets are written to `data/evaluation/results/`. Technical records must not contain a participant session ID and are not included in participant raw/session/task CSV exports.

## Sensitive Text

Raw participant question and decision text remain only in existing approved purpose-specific tables and raw export paths. Summary exports continue to prefer counts, ratings, booleans, and text lengths.
