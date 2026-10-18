# Uni-Navigator Developer Notes

> Historical workstation notes. Use the [root README](../README.md) for portable
> setup and [study flow](study_flow.md) for current behaviour. Earlier statements
> below about Chat not creating participant sessions are superseded by the
> researcher-controlled Chat sessions now implemented.

Start with [../AGENTS.md](../AGENTS.md) and [development_rules.md](development_rules.md) before making development changes.

For seed corpus ingestion, RAG smoke tests, and manual citation checks, see [rag_testing.md](rag_testing.md).

For official PDF sidecars, validation, scoped rebuilds, OCR handling, and source governance, see [corpus_management.md](corpus_management.md). Corpus ingestion is RAG indexing, not model training.

For the current Chat interface and research procedure, see [study_flow.md](study_flow.md). Retained session/task records are documented in [data_dictionary.md](data_dictionary.md).

For human-participant ethics, privacy, data minimisation, and de-identification guidance, see [ethics_safety.md](ethics_safety.md).

For local startup, Chat participant sessions, formal-runtime prerequisites, exports, and failure handling, see [pilot_runbook.md](pilot_runbook.md).

For application boundaries and the participant runtime, see [architecture.md](architecture.md). New pilot-critical fields are listed in [data_dictionary.md](data_dictionary.md).

## Quality Checks

Use [development_rules.md](development_rules.md) to choose checks for the change. Full application phase checks, from the repository root:

```bash
cd backend
.venv/bin/pytest
cd ../frontend
../.tools/bin/pnpm test
../.tools/bin/pnpm lint
../.tools/bin/pnpm typecheck
../.tools/bin/pnpm build
```

Release validation is a separate check when changing backend release contracts. Documentation-only changes require document checks, not application tests.

## Local Environment and Startup

Use `backend/.venv` for Python. The local `.tools/bin/pnpm` wrapper needs Node.js on PATH or `CODEX_NODE_BIN`. VS Code configures the bundled Node executable; an external macOS terminal can use this path when it exists:

```bash
export CODEX_NODE_BIN="/Users/savtr/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
export PATH="$(dirname "$CODEX_NODE_BIN"):$PATH"
```

This absolute path is for the current Mac. VS Code sets `HOME` to the project's
`.home` directory, so `$HOME/.cache/.../node` is not the bundled runtime location
inside that terminal. On another machine, use its actual Node executable.

Use the two-terminal startup commands in [pilot_runbook.md](pilot_runbook.md). The ASGI target is `main:app` from `backend`, not `app.main:app`. The frontend example environment points to port 8000; the current VS Code backend task uses 8001. Match `NEXT_PUBLIC_API_BASE_URL` to the chosen port and restart the frontend after environment changes.

### Frontend theme development

The legacy UI remains the default. Preview the Research Workbench with:

```bash
NEXT_PUBLIC_UI_THEME=research_workbench ../.tools/bin/pnpm dev --port 3000
```

The Design Lab additionally requires `NEXT_PUBLIC_STUDY_MODE=development` and is available only under `next dev`. It must use `frontend/lib/designLabFixtures.ts` and must never import application API or logging functions.

Run the presentation and isolation tests with:

```bash
../.tools/bin/pnpm test:ui-research
```

The current Chat interface has one evidence presentation and no A/B/C/D selector. The former `presentationPolicy.mjs` has been removed. `frontend/lib/uiThemePolicy.mjs` resolves the theme and Design Lab access. Theme changes must not change answer generation or logging. Design Lab fixtures may illustrate historical task interfaces; they do not define the current study procedure.

The workspace terminal prepends `.tools/bin` to `PATH`. If the machine does not have a global Node.js install, the local wrappers use `CODEX_NODE_BIN`; the VSCode settings point this to the bundled Codex runtime under `${userHome}/.cache/codex-runtimes/...`.

## Research CSV Export

Start the backend, then open or download:

```text
http://127.0.0.1:8000/api/admin/logs/export.csv
http://127.0.0.1:8000/api/admin/export/session-summary.csv
http://127.0.0.1:8000/api/admin/export/task-summary.csv
```

Substitute the actual backend port when using a different local setup. Current `/chat` requests do not create participant sessions or tasks. The session/task exports and fields described below cover retained backend contracts and historical records; they are not evidence that formal recording is connected to the current UI.

The raw logs CSV is intended for local HCI research analysis of study logs, source-checking behaviour, evidence inspection, trust checklist events, feedback, and task activity. It may contain participant-entered free text and must be handled as research data under the approved ethics/data management process. It exports rows from the available SQLite tables:

- `interaction` rows from chat answers
- `event` rows from study behaviour logs
- `feedback` rows from feedback submissions

Unavailable fields are left blank rather than invented. Raw event metadata is preserved in `metadata_json`, and selected metadata fields such as citation IDs, chunk IDs, trust checklist values, confidence values, and final decision length are flattened into stable columns when present. Chat rows also include retrieval status, based-on text, limitations, uncertainty, escalation guidance, and high-stakes detection flags for later HCI analysis.

This is a local research prototype endpoint. It should be protected before any deployment or real participant data collection outside a controlled study environment.

The session summary CSV exports one row per `StudySession`. The task summary CSV exports one row per session-task pair and uses the latest final response for that pair if multiple final responses exist. These summary exports avoid full sensitive free-text fields by default: they include final decision length and a notes-present flag, but not full final decision text or notes. Researcher-coded fields such as `decision_appropriateness` and `researcher_code` stay blank unless manually populated later.

## Study Event Names

Event names are defined in `backend/app/schemas.py` and `frontend/lib/types.ts`. The following list includes retained historical/backend events; current Chat does not emit task or trust-checklist events:

- `task_started`
- `question_submitted`
- `answer_received`
- `citation_clicked`
- `evidence_opened`
- `source_checked`
- `feedback_submitted`
- `task_completed`
- `trust_check_updated`
- `transcript_downloaded`
- `conversation_cleared`

## AI Provider Configuration

`/api/chat` always uses the backend OpenAI provider. API keys are never exposed to the frontend.

```env
AI_PROVIDER=openai
OPENAI_API_KEY=your_key_here
AI_MODEL=gpt-5.4-mini-2026-03-17
GENERATION_REASONING_EFFORT=none
AI_TIMEOUT_SECONDS=30
```

Put these values in `backend/.env`. Do not commit real API keys. Development, self-testing, technical evaluation, and participant chat all use the same live RAG pipeline. A missing key, provider error, retrieval error, or invalid citation fails closed and does not create a successful interaction record.

`/api/chat` now retrieves policy chunks before answer generation. Retrieved chunks are passed to the AI provider as bounded context, and only those chunks can become citation objects. The answer remains prototype guidance and must not be treated as official university advice.

## Policy Corpus and Vector Store

The retrieval foundation is separate from the SQLite research logging database. SQLite stores study and interaction logs. The vector store stores policy chunks and embeddings for later source-aware RAG.

Corpus files live under:

```text
data/corpus/
```

The loader supports `.md`, `.txt`, and `.json` files. Markdown files can include simple front matter:

```md
---
source_id: uq-assessment-procedure
title: Assessment Procedure
document_name: Assessment Procedure
section: Extensions
url: https://example.edu/policy
source_type: official_policy
updated_at: 2026-01-01
---

# Extensions

Policy text goes here.
```

JSON files should contain a top-level object with a `text` field and optional metadata fields matching the front matter keys above. Plain text files are loaded with filename-derived metadata.

Chunk metadata is structured for later HCI analysis and source verification:

- `chunk_id`
- `source_id`
- `title`
- `document_name`
- `section`
- `url`
- `source_type`
- `chunk_index`
- `chunk_text`

Vector store files live under:

```text
data/vector_store/
```

Default retrieval configuration:

```env
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
RETRIEVAL_SOURCE_MODE=official
VECTOR_STORE_PROVIDER=chroma
VECTOR_STORE_ALLOW_FALLBACK=false
VECTOR_STORE_PATH=data/vector_store/chroma
VECTOR_STORE_COLLECTION=uni_navigator_policy_chunks_openai
CORPUS_PATH=data/corpus
```

Application chat selects only active `official_policy` and `official_student_guidance` chunks. `EMBEDDING_PROVIDER=openai` calls the OpenAI embeddings endpoint using `OPENAI_API_KEY` and never mixes test vectors into the live collection. Unit tests inject local provider doubles without creating an alternate application mode.

## Research Modes

Use `EXECUTION_CONTEXT=development|participant_study|technical_evaluation`. This setting changes provenance and study-data handling only; it does not select an answer implementation. The current `/chat` UI supports unbound self-testing; the existing `participant_study` backend still requires session/task context that this UI does not send. See [pilot_runbook.md](pilot_runbook.md) before enabling formal recording.

Batch technical runs use the versioned 50-question dataset through `app.scripts.run_technical_evaluation`, write to the separate technical-run repository, and produce a manual semantic-review CSV; never attach a participant session ID. See [technical_evaluation.md](technical_evaluation.md) for partition selection, repetitions, and reviewer responsibilities.

For strict local Chroma verification, set `VECTOR_STORE_PROVIDER=chroma`, `VECTOR_STORE_ALLOW_FALLBACK=false`, and `VECTOR_STORE_PATH=data/vector_store/chroma`, then rebuild the vector store.

Run corpus ingestion from the backend folder:

```bash
cd backend
.venv/bin/python -m app.scripts.ingest_corpus --source-type official --rebuild
```

This is a billable index rebuild for an intentional official-corpus update, not a startup step. Prepared fixtures are handled separately as described in [rag_testing.md](rag_testing.md).

The retrieval service can be called from backend code with:

```python
retrieve_policy_chunks("assessment extension evidence", top_k=5)
```

The admin status endpoint reports corpus and vector-store status:

```text
GET /api/admin/corpus/status
```

## Chat Retrieval and Citations

When `/api/chat` receives a question, the backend:

1. retrieves the frozen `top_k` number of official policy chunks
2. assigns answer-local citation labels such as `[1]`, `[2]`, and `[3]`
3. passes only those retrieved excerpts to the AI provider
4. returns the existing `AssistantAnswer` shape with `answer`, `basedOn`, `citations`, `retrievalStatus`, `limitations`, `uncertainty`, and `escalationGuidance`
5. stores the complete answer, citations, ranked retrieval trace, token usage, response time, and frozen runtime provenance in `InteractionLog` and the research CSV export

Each citation maps one retrieved chunk into both the existing frontend fields and the newer research fields:

- `id` / `citationId`: stable within one answer, such as `c1`
- `label`: inline answer label, such as `[1]`
- `sourceId`
- `chunkId`
- `title`
- `documentName` / `documentTitle`
- `section` / `sectionHeading`
- `url` / `sourceUrl`
- `passage` / `quotedText`
- `score` / `relevanceScore`
- `sourceType`

Retrieval status values:

- `grounded`: retrieved evidence appears useful enough for a source-aware answer
- `partial_evidence`: some relevant evidence exists, but it is narrow or incomplete
- `insufficient_evidence`: retrieval ran but returned no chunks
- `individual_assessment`: official evidence supports a general rule, but the participant's personal outcome needs confirmation by authorised staff
- `ambiguous`: retrieved evidence supports only one part of a mixed or unresolved question

To debug empty citations:

- Confirm OpenAI embeddings and Chroma are configured and the corpus has been ingested.
- Validate official PDFs and their sidecar metadata under `data/corpus/official/` and `data/corpus/metadata/` as described in [corpus_management.md](corpus_management.md).
- Run ingestion again after changing corpus files.
- Check `GET /api/admin/corpus/status` and confirm `chunkCount` is greater than zero.
- Ask a question that overlaps with terms in the corpus.
- Require `vectorStoreProviderActive=chroma` and `fallbackUsed=false` in `GET /api/admin/corpus/status` for application chat.
- If `VECTOR_STORE_PROVIDER=chroma` is configured and `VECTOR_STORE_ALLOW_FALLBACK=false`, missing or broken ChromaDB setup fails loudly instead of falling back.

Example local RAG workflow:

```bash
cd backend
.venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Use the existing official index, then ask a synthetic question within its supported scope. The answer should include inline labels such as `[1]`, and the evidence panel should show the retrieved passage for each citation. Rebuild the index only when deliberately changing the corpus or embedding configuration.

Application chat requires Chroma and real embeddings. Local JSON and mock embeddings remain isolated test/ingestion utilities, not alternate Chat runtime modes. In all modes, the answer is research prototype guidance, not official university advice.

## Real Embedding Development

Development chat uses `EMBEDDING_PROVIDER=openai` and the `uni_navigator_policy_chunks_openai` collection. The backend reads `OPENAI_API_KEY`; the frontend must never receive it. `.gitignore` excludes `backend/.env`, and `.env.example` must keep `OPENAI_API_KEY=` empty.

The OpenAI provider batches inputs, enforces timeout and bounded retries, validates every response, and fails closed. It never silently mixes mock and OpenAI vectors. A full rebuild uses a verified staging collection before promotion, while collection-specific manifests retain provider, model, dimension, count, and build time.

Useful non-secret settings:

```env
EMBEDDING_BATCH_SIZE=32
EMBEDDING_TIMEOUT_SECONDS=60
EMBEDDING_MAX_RETRIES=3
EMBEDDING_RETRY_BASE_SECONDS=1
```

Run `.venv/bin/pytest` without API access first. Real API ingestion and evaluation are separate, billable checks. Inspect `GET /api/admin/corpus/status` and require the intended provider, model, collection, dimension, source/chunk counts, and `fallbackUsed=false` before activating a new index.

## Scope Guard and Retained Backend Pilot Contracts

The contracts below describe the existing backend. The current Chat frontend does not create the required participant context; see the integration boundary in [pilot_runbook.md](pilot_runbook.md).

`STUDY_MODE=development|pilot` and `EXECUTION_CONTEXT` are server-owned settings. Client requests cannot promote a development interaction into formal research data. Every chat context fails closed; participant mode additionally requires a frozen release and writes formal study events. Pilot validation rejects mock embeddings, fallback-enabled vector storage, provider/model/collection/count mismatch, and empty Chroma. Run:

```bash
cd backend
.venv/bin/python -m app.scripts.pilot_preflight
```

The command exits non-zero for an invalid pilot configuration and reports no secrets. It checks answer/embedding/vector settings, thresholds, scope registry, collection and manifest, a real Chroma query, task definitions, database writability, and synthetic-session warnings.

Chat scope is decided by `corpus_scope_service.py` from the versioned JSON registry plus retrieval signals. `out_of_scope` forces `insufficient_evidence` and removes citations; `ambiguous` does not claim grounded advice; `possibly_in_scope` is limited to partial evidence. The raw retrieval status is never allowed to overrule an explicit unsupported-topic rule.

Pilot interaction rows add nullable provenance columns so old SQLite rows remain readable. Raw CSV exposes these columns without changing existing names: embedding provider/model/dimension, vector collection, thresholds, top-k, retrieval mode, scope decision/version/topics, corpus manifest SHA-256 fingerprint, AI provider/model, answer mode, task version, and app version. The experimental condition remains in the existing `condition` field.

When a pilot failure occurs, `/api/chat` returns HTTP 503 with the standard participant message and writes a privacy-safe `system_failure`. The study endpoints reject trust, final response, and task completion for that failed task run. The frontend must not catch this response and manufacture an assistant message.
