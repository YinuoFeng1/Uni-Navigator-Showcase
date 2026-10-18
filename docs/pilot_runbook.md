# Pilot and User Evaluation Runbook

Follow [study_flow.md](study_flow.md) for the current research design. Participants use the shared `/chat` interface and complete the agreed questionnaire separately. The application is a local research prototype, not an official advice service or a public deployment.

## Current Implementation Boundary

Chat supports self-testing and researcher-controlled participant sessions:

- Researcher setup sends a round, a participant code (`P` followed by 2-6 digits), a unique session identifier, and confirmation that consent was completed separately.
- Chat sends the session ID with questions and all recorded activity. The backend derives participant attribution from that session, not a client-supplied name.
- The Chat workflow does not require a task. Formal `participant_study` still validates the frozen release, runtime fingerprint, and single evidence presentation. Existing task contracts serve historical workflows, not this UI.
- Setting `EXECUTION_CONTEXT=participant_study` alone is insufficient: pilot configuration, OpenAI providers, Chroma, valid release and preflight must also pass.
- Development sessions are clearly labelled as development. Do not reclassify them as formal participant data.

Confirm the intended runtime and complete a consented synthetic rehearsal before collecting formal data. Automated integration tests cover session attribution in both runtimes; they do not establish that the current local release is ready or that ethics approval has been granted.

## Local Self-Test Setup

Use the backend virtual environment and the local frontend tools described in [developer_notes.md](developer_notes.md). Keep `STUDY_MODE=development` and `EXECUTION_CONTEXT=development` for self-testing. Application chat requires OpenAI generation, OpenAI embeddings, official policy retrieval, Chroma, and fallback disabled.

In the first terminal, from the repository root:

```bash
cd backend
.venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, from the repository root:

```bash
cd frontend
../.tools/bin/pnpm dev --port 3000
```

Set `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000` in the local frontend environment and ensure the backend allows `http://localhost:3000`. Restart the frontend after changing its environment.

Open `http://localhost:3000/chat` for Chat and `http://localhost:3000/admin` for researcher diagnostics. The existing VS Code full-stack task starts the backend on **8001**, so using that task requires a matching frontend API URL. Keep the port consistent on both sides.

## Before an Evaluation Round

1. Confirm the study materials, consent process, questions, questionnaire, and data handling match the agreed protocol.
2. Complete the application phase checks in [development_rules.md](development_rules.md) for the build being evaluated.
3. Inspect `/api/admin/corpus/status` on the selected backend port. Confirm the intended model, embedding model, collection, official corpus, source/chunk counts, and `fallbackUsed=false`.
4. Record the model snapshot, prompt version, corpus fingerprint, embedding model, Chroma collection, `top_k`, thresholds, scope registry, generation settings, app revision, and interface version. Keep them stable within a comparison round.
5. Verify Chat, citation links, evidence viewing, feedback saving, retry behaviour, and visible logging failures using synthetic input. Real requests incur API charges.
6. For formal application-log collection, verify the release/preflight checks and that the Chat session says **Participant study**, not **Development test**. Start a new round if the system configuration changes; do not bypass the fingerprint guard.

The existing `validate_pilot_release`, `finalize_pilot_release`, and `pilot_preflight` scripts validate and freeze backend configuration. They are researcher operations, not steps that ordinary Chat users complete. Do not use the retired `/study` route.

## User Evaluation Procedure

For each participant:

1. Provide the agreed participant information and obtain consent outside the Chat interface.
2. Open `/chat`, expand **Researcher setup**, enter the round (for example `pilot-01`) and code (for example `P01`), confirm the completed consent process, and select **Start test**. Wait for the active session acknowledgement. Keep one browser tab for the session.
3. Let the participant use Chat and inspect evidence. Use general or synthetic questions, without personal identifiers or case documents. Inline citation links, View evidence, both original-source links, source checks, feedback, transcript downloads, and conversation clearing are logged. The application is not a complete recording of every mouse movement or page scroll.
4. If permitted by the consent and protocol, record audio/screen separately. Use names such as `pilot-01_P01_audio` and `pilot-01_P01_screen`; record recording start time separately because media and application clocks are not automatically synchronised. Collect the separate questionnaire and note interruptions and facilitator interventions.
5. Wait for queued saves, select **End test**, and wait for **Test ended**. A failed end request remains retryable. Starting the next participant clears the visible conversation; stored records are preserved.
6. Open `/admin`, find **Chat study exports**, and select the round and participant. Download **Participant summary**, **Activity timeline**, and **Questions and answers**. Verify session IDs and counts before the next participant.

The researcher confirmation is not an electronic consent form or evidence of recording consent. There is no assigned task flow, condition selector, trust checklist, or final-decision form.

## Failure Handling

- Provider, retrieval, or citation-validation failures must remain visible; never substitute a Mock or prewritten answer.
- For a retryable request failure, the question remains available for retry. For a blocking failure, pause and investigate the reported error before continuing.
- A logging error means the affected activity is not confirmed as saved, even if an answer is visible. Record the interruption and inspect the backend before treating the interaction as complete research data.
- Use **Retry saves** for queued activity. Stable operation IDs prevent a lost response from creating duplicate event/evidence/feedback records. Ending a session waits for this queue. Do not edit SQLite during a session.
- Queued activity and session IDs survive refresh in the same tab using session storage, but the visible conversation and unsent drafts do not. Closing the tab can lose pending data. Keep it open until saves succeed; storage failures are surfaced explicitly.
- The Chat question retry generates a new answer attempt; it is not an idempotent replay of a model response. Record interruptions and distinguish question attempts from successfully served answers.

## Data and Results

New filtered endpoints are `/api/admin/research/sessions` and `/api/admin/research/export/{participants|timeline|answers}.csv`, with optional `round_id` and `participant` filters. These include only the new Chat workflow. Older raw/session/task exports remain available for historical records.

Participant summary has one row per session, not one row per distinct person across all sessions. Timeline timestamps distinguish occurrence from recording, so an offline retry retains the original action time. Source-open events indicate link activation, not proof the document loaded or was read. Questions and answers contains sensitive free text, actual served answers, citations, retrieval provenance and feedback. Failed generations are represented in the timeline rather than invented answer rows. CSV exports use UTF-8 with BOM and guard against spreadsheet formula injection.

Keep research databases and historical logs, including `data/logs/uni_navigator.db`. Corpus-index rebuilding is separate from research-data storage. Protect Admin and raw exports from public access and handle participant text according to the agreed data management process.

Live answers can vary under the same configuration. Preserve actual outputs and provenance. Keep technical evaluation records separate from participant data and leave human judgements unfilled until reviewed.
