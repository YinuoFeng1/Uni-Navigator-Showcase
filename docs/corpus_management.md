# Corpus Management

> This public showcase distributes metadata, not the 12 policy PDFs. Obtain them
> using the [download manifest](../data/corpus/policy_download_manifest.json).
> Counts and mock-provider setup instructions in historical sections below are
> earlier development records, not current Chat configuration instructions.

Uni-Navigator uses retrieval-augmented generation (RAG). Corpus ingestion extracts and chunks documents, creates embeddings, and stores those chunks in the configured vector store. It does not train or fine-tune the language model.

The corpus currently includes twelve checksum-tracked UQ policy and procedure PDFs with evidence-based metadata sidecars. The existing prepared Markdown corpus remains separate prototype-only material. Inclusion in this research prototype does not make Uni-Navigator an official UQ advice service.

## Corpus Structure

```text
data/corpus/
├── prepared/          # New prepared Markdown, text, or JSON sources
├── official/          # Official PDF files added by the researcher later
├── metadata/          # Required JSON sidecars for official PDFs
└── prepared-*.md      # Existing legacy prepared corpus, still supported
```

Official PDFs and metadata sidecars must have the same relative path and filename stem. For example:

```text
data/corpus/official/assessment/assessment-policy.pdf
data/corpus/metadata/assessment/assessment-policy.json
```

Do not place participant data, study logs, transcripts, or exported CSV files in the corpus folders. Chroma stores policy chunks and embeddings only. SQLite remains the study logging database.

## Official Metadata

Every official PDF requires a sidecar JSON object. Missing values are rejected rather than inferred.

```json
{
  "source_id": "example-assessment-policy",
  "title": "Example Assessment Policy",
  "document_name": "Example Assessment Policy PDF",
  "institution": "Example University",
  "source_url": "https://example.edu/policy/assessment",
  "access_date": "2026-07-10",
  "source_type": "official_policy",
  "prototype_only": false,
  "active": true,
  "version": "1.0",
  "effective_date": "2026-01-01",
  "superseded_date": "",
  "notes": "Optional researcher note"
}
```

Required fields:

- `source_id`
- `title`
- `document_name`
- `institution`
- `source_url`
- `access_date`
- `source_type`
- `prototype_only`
- `active`

`source_type` must be `official_policy` or `official_student_guidance`. Official sources must use `prototype_only: false`. `active` and `prototype_only` must be JSON booleans, not strings. Dates use `YYYY-MM-DD`, and `source_url` must be an absolute HTTP or HTTPS URL. Source IDs must be unique across the selected corpus.

Optional fields are `version`, `effective_date`, `superseded_date`, and `notes`. A source with `active: false` or a non-empty `superseded_date` is excluded from chunking and retrieval. If it was previously ingested, its obsolete chunks are removed during the next official ingestion.

## PDF Extraction

The backend uses `pypdf` and extracts text one page at a time. Page numbers are preserved as `page_start` and `page_end` on chunks. A conservative text heuristic records a section heading when practical.

The extractor reports:

- pages with no extractable text
- PDFs with no meaningful extractable text
- image-only or scanned PDFs that require OCR
- invalid PDFs
- password-protected PDFs

OCR is never run automatically. If an active PDF requires OCR, validation fails and the vector store is left unchanged. Obtain an approved searchable PDF or run an authorised OCR workflow outside Uni-Navigator, then validate the replacement file again.

## Chunking And Metadata

PDF chunks target approximately 700 tokens, within the requested 500-900 token range, with limited paragraph-level overlap. Prepared text remains backward-compatible with the existing chunker. Chunk IDs remain deterministic:

```text
<normalised-source-id>_chunk_<four-digit-index>
```

Each PDF-aware chunk preserves:

- `source_id`
- `chunk_id`
- `page_start` and `page_end`
- `section`
- `source_url`
- `source_type`
- `version`
- `effective_date`
- `document_checksum`
- `chunk_index`
- `chunk_text`
- `active` and `prototype_only`

Chroma metadata is restricted to scalar-compatible string, integer, float, and boolean values.

## Validation Workflow

From `backend/`, validate official PDFs without changing Chroma:

```bash
.venv/bin/python -m app.scripts.ingest_corpus \
  --source-type official \
  --validate-only
```

Review `invalid files`, `invalid file details`, `warnings`, `pdfs requiring ocr`, and `metadata files validated`. A validation error exits with a non-zero status.

Preview checksum, deduplication, replacement, and chunk actions without writing:

```bash
.venv/bin/python -m app.scripts.ingest_corpus \
  --source-type official \
  --dry-run
```

## Ingestion Workflow

After validation and dry-run both pass:

```bash
.venv/bin/python -m app.scripts.ingest_corpus \
  --source-type official
```

Repeated ingestion compares deterministic chunk IDs, the PDF SHA-256 checksum, version, effective date, title, source URL, and active state. Unchanged sources are skipped. When a source changes, all chunks for that source ID are deleted before the replacement chunks are upserted, preventing stale trailing chunks.

The local ingestion manifest is stored next to the configured vector store. The default collection uses `ingestion_manifest.json`; additional collections use a collection-specific filename such as `ingestion_manifest.uni_navigator_policy_chunks_openai.json`. This prevents a real-embedding build from overwriting mock-index metadata. Manifests support status reporting for inactive and OCR-required sources and never contain participant data.

## Safe Rebuilds

Rebuild prepared sources only:

```bash
.venv/bin/python -m app.scripts.ingest_corpus \
  --source-type prepared \
  --rebuild
```

Rebuild official sources only while preserving prepared chunks:

```bash
.venv/bin/python -m app.scripts.ingest_corpus \
  --source-type official \
  --rebuild
```

Rebuild every corpus type:

```bash
.venv/bin/python -m app.scripts.ingest_corpus \
  --source-type all \
  --rebuild
```

Scoped rebuild uses `source_type` deletion and never calls a whole-collection clear for `prepared` or `official`. A full collection clear is used only for the explicit `--source-type all --rebuild` combination. None of these commands deletes `data/logs/uni_navigator.db`.

## Retrieval Source Modes

Configure `RETRIEVAL_SOURCE_MODE` in `backend/.env`:

```env
RETRIEVAL_SOURCE_MODE=official
```

Supported values:

- `all`: retrieve active prepared and official sources by score
- `prepared`: retrieve only `prepared_policy`
- `official`: retrieve only active official policy and official student guidance
- `prefer_official`: formal testing mode that ranks active official sources before prepared sources

Corpus scripts can use all four modes for ingestion and evaluation. Application chat always requests `official` and rejects prepared chunks before answer generation.

## Status Check

With the backend running, inspect:

```text
GET http://127.0.0.1:8001/api/admin/corpus/status
```

In addition to provider and collection status, the endpoint reports prepared, official-policy, and official-guidance source/chunk counts, inactive source count, OCR-required PDF count, latest ingestion timestamp, and embedding provider.

Mock embeddings are deterministic and suitable for infrastructure tests. They are not suitable for final retrieval-quality evaluation on a real policy corpus. Run a separately designed retrieval evaluation before making research claims about official-source performance.

## Official Retrieval Smoke Test

The official test set contains one question for each imported PDF plus an out-of-corpus probe:

```bash
cd backend
.venv/bin/python -m app.scripts.rag_smoke_test \
  --question-file ../data/evaluation/official_rag_smoke_questions.json
```

The report includes top-k source IDs and types, pages, scores, source URLs, citation passages, source labels, expected-source top-1/top-k checks, escalation guidance, and citation metadata checks. The prepared baseline remains available through the command without `--question-file`.

Retrieval applies a conservative lexical-overlap guard after vector search. This prevents isolated hash collisions in the mock embedding fixture from turning clearly out-of-corpus questions into source-backed answers. It is a safety guard, not a substitute for semantic retrieval evaluation.

## Switching To Real Embeddings

Do not write OpenAI embeddings into the current mock collection because their dimensions differ. Preserve the validated mock index and use a new collection:

```env
OPENAI_API_KEY=<researcher-managed-key>
EMBEDDING_PROVIDER=openai
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_BATCH_SIZE=32
EMBEDDING_BATCH_DELAY_SECONDS=0
EMBEDDING_TIMEOUT_SECONDS=60
EMBEDDING_MAX_RETRIES=3
VECTOR_STORE_COLLECTION=uni_navigator_policy_chunks_openai
```

`backend/.env` is ignored and `backend/.env.example` contains an empty key placeholder only. Never put the key in frontend variables, terminal output, screenshots, logs, evaluation results, or documentation. OpenAI accepts multiple embedding inputs in one request; Uni-Navigator uses configurable batches and validates response order, count, numeric values, and vector dimensions. Provider errors are retried with bounded exponential backoff and never fall back to mock in `openai` mode. Low token-per-minute tiers can reduce `EMBEDDING_BATCH_SIZE` and set `EMBEDDING_BATCH_DELAY_SECONDS` to spread a rebuild across the rate-limit window without changing the resulting vectors. See the [OpenAI embeddings API reference](https://platform.openai.com/docs/api-reference/embeddings).

Build before activation. Keep the application on the mock collection, supply the key only to the backend process, and use environment overrides for validation and rebuild:

```bash
cd backend
export OPENAI_API_KEY='<researcher-managed-key>'
export AI_PROVIDER=openai
export EMBEDDING_PROVIDER=openai
export EMBEDDING_MODEL=text-embedding-3-small
export VECTOR_STORE_PROVIDER=chroma
export VECTOR_STORE_ALLOW_FALLBACK=false
export VECTOR_STORE_PATH=data/vector_store/chroma
export VECTOR_STORE_COLLECTION=uni_navigator_policy_chunks_openai

.venv/bin/python -m app.scripts.ingest_corpus --source-type all --validate-only
.venv/bin/python -m app.scripts.ingest_corpus --source-type all --dry-run
.venv/bin/python -m app.scripts.ingest_corpus --source-type all --rebuild
.venv/bin/python -m app.scripts.evaluate_retrieval
```

Full rebuilds generate and validate all embeddings before writing them to a uniquely named staging collection. The staging collection is count- and dimension-checked, then promoted to the target name. If embedding or staging fails, the prior target is retained. The separate `uni_navigator_policy_chunks` mock collection is never renamed or deleted.

Activate only after corpus status reports 10 sources, 77 chunks, the configured OpenAI model, a non-null embedding dimension, and `fallbackUsed=false`. Then update local `backend/.env` to the OpenAI provider and collection and restart the backend. This creates a new RAG index; it does not train or fine-tune a model.

For isolated, non-chat embedding tests only, use:

```env
AI_PROVIDER=openai
EMBEDDING_PROVIDER=mock
VECTOR_STORE_COLLECTION=uni_navigator_policy_chunks_test
RETRIEVAL_PARTIAL_SCORE_THRESHOLD=0.15
RETRIEVAL_GROUNDED_SCORE_THRESHOLD=0.35
```

Do not start `/api/chat` with this isolated test configuration. OpenAI usage is billable. Review input volume before rebuilds, avoid unnecessary repeated indexing, and use provider usage controls without logging secrets. Mock and OpenAI cosine scores are not directly comparable.

## Real Retrieval Evaluation

The 60-question dataset is `data/evaluation/official_retrieval_evaluation.json`. It contains PDF-grounded source IDs, page ranges, and keywords for all five documents, plus cross-document, ambiguous, paraphrased, terminology-shift, out-of-corpus, and adversarial near-scope cases.

```bash
cd backend
.venv/bin/python -m app.scripts.evaluate_retrieval
```

Timestamped JSON results are written under `data/evaluation/results/` without overwriting mock baselines. Reports include Hit@1, Hit@3, Hit@5, MRR, out-of-corpus accuracy, relevant-source precision, prepared leakage, inactive retrieval, page-range match, per-question ranks and scores, and relevant/out-of-corpus score distributions.

Thresholds are configured with `RETRIEVAL_PARTIAL_SCORE_THRESHOLD` and `RETRIEVAL_GROUNDED_SCORE_THRESHOLD`. Inspect score overlap and failure cases before changing them. A suggested midpoint is reported only when all labelled relevant first-hit scores separate from all out-of-corpus top scores. Do not tune thresholds solely to make this small dataset pass, and do not treat the dataset as final retrieval-quality evidence.

The July 2026 OpenAI baseline uses `0.35` for partial evidence and `0.55` for grounded evidence. All 28 labelled in-corpus questions scored above the partial threshold, while one of the two out-of-corpus questions overlapped the relevant score range. The overlap means score thresholds alone cannot provide reliable scope detection; expand the out-of-corpus set and evaluate a separately governed scope guard before pilot deployment.

## Scope Registry Governance

`data/corpus/corpus_scope.json` is the researcher-reviewable contract for what the active official corpus supports. It names the eight topics, source IDs, supported intents, representative terms, student paraphrases, unsupported adjacent topics, and escalation category. `registry_version` must change whenever a meaning-bearing scope rule changes.

Do not place `corpus_scope.json` in the vector index. Corpus loading explicitly excludes it from prepared policy ingestion. A registry update does not require an embedding rebuild unless policy documents or chunking also changed, but it does require unit tests and the 60-question scope evaluation.

Use these definitions consistently:

- `out_of_domain`: not a university administrative policy question, such as weather or shopping advice.
- `university_admin_but_out_of_corpus`: a plausible UQ administrative topic, such as parking or library fines, absent from the five documents.
- `ambiguous_scope`: combines covered and uncovered issues, depends on an unprovided local rule, or asks for a personal decision the corpus cannot make.
- `in_corpus`: a general question supported by one or more documents in the reviewed official policy corpus.

Semantic similarity alone is insufficient because administrative documents share words such as student, application, approval, deadline, and eligibility. A high cosine score can therefore rank a nearby but non-covering clause.
