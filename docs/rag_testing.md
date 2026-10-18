# RAG Smoke Testing

Uni-Navigator is a research prototype, not official university advice. Application chat uses official sources, OpenAI embeddings, and Chroma. The prepared seed corpus and isolated storage checks below are test utilities, not an alternate Chat mode. For the current 35/15 live evaluation and supervisor review, start with [technical_evaluation.md](technical_evaluation.md).

## Seed Corpus

Seed documents live in:

```text
data/corpus/
```

Current seed documents:

- `prepared-special-consideration.md`
- `prepared-course-withdrawal-census.md`
- `prepared-study-load-overload.md`
- `prepared-academic-progression.md`
- `prepared-fees-refunds-appeals.md`

These documents are synthetic prepared materials. They are marked with:

```yaml
source_type: prepared_policy
prototype_only: true
```

They are designed to test retrieval, citation mapping, evidence inspection, escalation guidance, logging, and CSV export. They should not be presented as official UQ or university policy.

The legacy root-level Markdown files remain supported. New prepared sources may be placed in `data/corpus/prepared/`. Validated official PDFs and required metadata sidecars use `data/corpus/official/` and `data/corpus/metadata/`; see [corpus_management.md](corpus_management.md).

## Ingest Corpus

From the backend folder:

```bash
.venv/bin/python -m app.scripts.ingest_corpus --source-type prepared
```

To clear and rebuild only the policy vector store:

```bash
.venv/bin/python -m app.scripts.ingest_corpus --source-type prepared --rebuild
```

The scoped rebuild deletes and replaces prepared chunks only. It preserves official chunks and does not delete SQLite study logs or `data/logs/uni_navigator.db`. Use `--source-type all --rebuild` only for an intentional full corpus rebuild.

The ingestion summary prints the number of documents loaded, chunks created, chunks stored, vector store path, requested provider, active provider, collection name, fallback status, Chroma availability, and stored chunk/source counts.

## Vector Store Providers

SQLite and the vector store have different responsibilities:

- SQLite stores research/study logs, participant session records, interactions, feedback, final responses, evidence-use rows, and trust checklist snapshots.
- ChromaDB or local JSON stores policy chunks, embeddings, and source metadata used for retrieval/citation.

Do not store participant/session/task research logs in ChromaDB.

Application chat settings:

```env
VECTOR_STORE_PROVIDER=chroma
VECTOR_STORE_ALLOW_FALLBACK=false
VECTOR_STORE_PATH=data/vector_store/chroma
VECTOR_STORE_COLLECTION=uni_navigator_policy_chunks_openai
```

Provider behaviour:

- `VECTOR_STORE_PROVIDER=chroma`: use ChromaDB `PersistentClient`.
- `VECTOR_STORE_PROVIDER=local_json`: use the local JSON vector store.
- `VECTOR_STORE_PROVIDER=auto` and `local_json` remain available to isolated ingestion and unit tests, not application chat configuration.

Install ChromaDB locally inside the backend virtual environment:

```bash
cd backend
.venv/bin/python -m pip install chromadb
```

For strict local Chroma verification, use:

```env
VECTOR_STORE_PROVIDER=chroma
VECTOR_STORE_ALLOW_FALLBACK=false
VECTOR_STORE_PATH=data/vector_store/chroma
VECTOR_STORE_COLLECTION=uni_navigator_policy_chunks_test
AI_PROVIDER=openai
EMBEDDING_PROVIDER=mock
```

`VECTOR_STORE_ALLOW_FALLBACK=false` makes Chroma setup fail loudly instead of silently using local JSON. This is useful when verifying that ChromaDB is really active.

Mock embeddings are deterministic test doubles for isolated tests and setup verification. They are not a selectable application chat mode and are not a retrieval-quality evaluation for a real university policy corpus.

OpenAI embedding integration uses the same retrieval and citation contracts but a separate Chroma collection. Normal `pytest` runs never require an API key or network access; real API checks are run explicitly after deterministic tests pass.

Corpus ingestion creates a RAG index; it does not train or fine-tune the language model.

## Run Smoke Test

Smoke questions live in:

```text
data/evaluation/rag_smoke_questions.json
```

Run:

```bash
.venv/bin/python -m app.scripts.rag_smoke_test
```

The script loads each question, calls `retrieve_policy_chunks`, prints the top retrieved source/chunk IDs, checks whether expected source IDs appear in the top results, and prints `PASS` or `WARN`.

Run the official corpus checks separately:

```bash
.venv/bin/python -m app.scripts.rag_smoke_test \
  --question-file ../data/evaluation/official_rag_smoke_questions.json
```

The official report also checks source type, source label, page metadata, source URL, expected keywords, escalation behaviour, citation labels, and out-of-corpus handling.

## Retrieval Metrics

Run the larger official evaluation only against the intended collection:

```bash
cd backend
.venv/bin/python -m app.scripts.evaluate_retrieval
```

The dataset has 30 labelled questions. Hit@k and MRR use the first expected or acceptable source rank. Out-of-corpus accuracy uses `insufficient_evidence`; page match requires an overlapping labelled PDF range. Prepared-source and inactive-source retrieval are counted as explicit safety failures in official mode.

Result files include provider, model, collection, dimension, thresholds, corpus status, per-question scores/pages, and distribution summaries. They do not contain the API key. Mock and OpenAI scores must be analysed separately.

Threshold calibration is a research decision, not an automatic pass-making step. Review relevant and out-of-corpus distributions, false positives, missed paraphrases, page failures, and cross-document errors. Retain a written rationale for any threshold change and rerun the complete dataset.

The 2026-07-17 `text-embedding-3-small` baseline on `uni_navigator_policy_chunks_openai` produced Hit@1 `0.9643`, Hit@3/5 `1.0`, MRR `0.9821`, page-range match `0.8929`, no prepared-source leakage, and no inactive-source retrieval. Relevant and out-of-corpus score ranges overlapped (`0.464-0.705` versus `0.331-0.539`), so the calibrated local thresholds are `0.35` for partial evidence and `0.55` for grounded evidence. Out-of-corpus accuracy improved to `0.5`, but the parking-permit question remained partial evidence. Treat this as an explicit scope-detection limitation, expand the out-of-corpus evaluation set, and do not report Hit@k alone as end-to-end safety performance.

`PASS` means the expected source/status check was met. `WARN` means retrieval should be inspected manually; it does not necessarily mean the application is broken.

## Retrieval Status

- `grounded`: retrieved evidence appears useful enough for a source-aware answer
- `partial_evidence`: some relevant evidence exists, but it is narrow or incomplete
- `insufficient_evidence`: retrieval returned no chunks or the strongest result was below the partial-evidence threshold; citations are withheld
- `individual_assessment`: retrieved official evidence supports a general rule, but a personal outcome needs confirmation by authorised staff
- `ambiguous`: retrieved evidence supports only part of a mixed or unresolved question

## Standard Answer Structure

`/api/chat` returns both backward-compatible fields and clearer research-facing fields:

- `answer` / `shortAnswer`: concise plain-language answer
- `basedOn` / `evidenceSummary`: what retrieved evidence the answer is based on
- `limitations`: what is not covered and why this is not official advice
- `uncertainty`: uncertainty or trust-calibration notice
- `escalationGuidance` / `nextStep`: when to contact authorised staff
- `citations`: retrieved evidence passages only

The frontend displays these as:

- Plain-language answer
- What this is based on
- Citations
- Limitations
- Uncertainty
- Contact staff when needed

## High-Stakes Escalation

The backend uses a small keyword helper for high-stakes or personal policy questions. It checks for areas such as visa conditions, enrolment overload, withdrawal deadlines, census date, academic progression, exclusion/show cause, fees/refunds, appeals, special consideration, personal eligibility, failed courses, graduation, and academic penalty.

If a high-stakes indicator is found and evidence exists, `retrievalStatus` becomes `individual_assessment`. The answer gives the supported general rule with citations, then separates that evidence from the participant's personal outcome and recommends staff confirmation. If no useful evidence is found, citations are removed and the answer explicitly reports insufficient evidence.

## Citation Quality Checks

Backend tests check these guardrails:

- no citation object without `chunkId`
- no citation object without `passage`
- no answer label such as `[3]` unless a returned citation has label `[3]`
- no citations when `retrievalStatus` is `insufficient_evidence`
- escalation guidance is present for insufficient, partial, individual-assessment, ambiguous, or high-stakes questions
- InteractionLog and CSV export include citation/source/chunk metadata after RAG chat

## Manual Browser Checklist

1. Start the backend:

```bash
cd backend
.venv/bin/python -m app.scripts.ingest_corpus --source-type prepared --rebuild
uvicorn main:app --reload --port 8001
```

2. Start the frontend:

```bash
cd frontend
pnpm dev --port 3000
```

3. Open the chat UI and ask a clear seed-corpus question, for example:

```text
Can I apply for special consideration if I was sick during an exam?
```

4. Confirm the answer includes a citation label such as `[1]`.
5. Open the citation/evidence panel.
6. Confirm the passage matches the citation card.
7. Mark the source as checked.
8. Submit feedback.
9. Export the CSV from `/api/admin/logs/export.csv`.
10. Confirm the CSV includes `interaction_id`, `retrieval_status`, `citation_ids`, `source_ids`, and `chunk_ids`.

To check which vector store is active, call:

```text
GET http://127.0.0.1:8001/api/admin/corpus/status
```

Important status fields:

- `vectorStoreProviderRequested`
- `vectorStoreProviderActive`
- `vectorStorePath`
- `vectorStoreCollection`
- `fallbackUsed`
- `chromaAvailable`
- `sourceCount`
- `chunkCount`
- `preparedSourceCount`
- `officialPolicySourceCount`
- `officialGuidanceSourceCount`
- `pdfFilesRequiringOcr`
- `latestIngestionAt`
- `embeddingProvider`

To manually test insufficient evidence, ask:

```text
Where can I book a xylophone practice room?
```

Expected behaviour: no citations, `insufficient_evidence`, visible limitations, visible uncertainty, and guidance to check authorised sources or contact staff.

## Limitations

The local JSON vector store and mock embeddings are isolated test utilities. All application chat, including development chat, requires Chroma and OpenAI embeddings. The prepared seed corpus is intentionally small and synthetic, so it does not prove real-world university policy coverage or answer quality.

The 60-question official dataset is still small and researcher-authored. A strong score is a pilot-readiness signal, not proof of coverage, fairness, policy correctness, or generated-answer quality.

## Scope Guard Evaluation

`data/evaluation/official_retrieval_evaluation.json` contains 28 in-corpus questions, 14 university-administration questions outside the five-document corpus, 6 questions outside the university-administration domain, and 12 ambiguous or adversarial near-scope questions. Every row records a `scope_label`, expected retrieval status, applicable source/page labels, expected escalation, and researcher notes.

The scope guard reads the versioned `data/corpus/corpus_scope.json` registry. It combines explicit topic and unsupported-adjacent matches with source-topic consistency, top score, score margin, retrieved-source consistency, and issue-concept overlap. Cosine similarity is evidence-ranking input, not proof of corpus coverage.

The evaluation reports retrieval, scope, page/keyword support, and escalation category separately. An escalation synonym mismatch does not turn a correct retrieval into a retrieval failure. Review these pilot safety metrics before aggregate pass count:

- false-grounded rate on out-of-corpus questions
- out-of-corpus and university-admin-out-of-corpus rejection accuracy
- ambiguous-scope accuracy
- false-insufficient rate on in-corpus questions
- page-support and escalation-category accuracy
- scope confusion matrix

For each scope failure, first inspect `rule_signals`, `retrieval_signals`, matched topics, supporting sources, and registry version. Change a registry label only after a researcher reviews the actual five-document corpus; never lower retrieval thresholds merely to improve PASS count.

## End-to-End Live Answer Evaluation

`data/evaluation/end_to_end_technical_evaluation.json` contains 50 synthetic questions derived from the seven original study task categories. The primary question types are:

- 6 standard questions
- 19 paraphrases
- 8 ambiguous or mixed-scope questions
- 6 out-of-scope questions
- 11 high-risk questions

Each question has expected source, page, scope, retrieval-status and escalation labels, plus case-specific manual review guidance. The dataset contains no prepared answers and is not used to answer participant questions.

Choose the partition and repetitions for the intended evaluation before running it. Configure `EXECUTION_CONTEXT=technical_evaluation`, the intended OpenAI model and embedding model, the intended Chroma collection, and stable evaluation settings. The example below runs the 35 development questions three times (105 billable attempts). The current runner requires at least two repetitions to calculate answer variation; three is its default, not a universal research requirement. See [technical_evaluation.md](technical_evaluation.md) before running the 15-question holdout.

```bash
cd backend
.venv/bin/python -m app.scripts.run_technical_evaluation \
  --partition dev \
  --run-id pilot-tech-v1 \
  --repetitions 3 \
  --confirm-live-run
```

The command writes:

- append-only attempt records to `data/evaluation/technical_runs.jsonl`
- a timestamped JSON report under `data/evaluation/results/`
- a matching manual review CSV under `data/evaluation/results/`

Use a new `run-id` for every execution. The runner rejects an ID already present in the append-only technical log or an existing report, so an interrupted or completed run cannot be silently overwritten.

The report automatically calculates expected-source Top K, expected page retrieval, cited source/page match, scope and retrieval-status accuracy, citation-label validity, out-of-scope rejection, escalation accuracy, requested/returned model agreement, token-usage completeness, errors and latency. It also verifies that the runtime fingerprint and returned model stay consistent within the run. Repeated-run analysis reports unique answer, retrieval and citation counts; exact consistency; and mean pairwise answer similarity for each question.

Human review is needed for semantic judgements that deterministic checks cannot establish reliably. The current supervisor workbook asks for correctness and optional comments on the first response for each question. The full CSV supports the following additional dimensions when they are actually reviewed; leave unreviewed fields blank:

- `answers_question`: `yes`, `partial`, or `no`
- `citations_support_conclusions`: `yes`, `partial`, `no`, or `not_applicable`
- `unsupported_rule_present`: `yes`, `no`, or `unclear`
- `uncertainty_appropriate`: `yes`, `partial`, or `no`
- `escalation_appropriate`: `yes`, `partial`, or `no`

After review, summarize the completed coding sheet:

```bash
.venv/bin/python -m app.scripts.summarize_technical_review \
  --review-csv ../data/evaluation/results/technical_evaluation_pilot-tech-v1_dev_manual_review.csv
```

Do not run this batch against participant mode, attach participant session IDs, or import technical records into participant exports. Keep the dataset, model, prompt, corpus fingerprint, embedding model, Chroma collection, `top_k`, thresholds, scope registry, app revision and generation settings unchanged within one comparison run.
