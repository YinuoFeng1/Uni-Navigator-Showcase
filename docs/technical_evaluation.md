# Technical Evaluation

The reviewed 50-question dataset has two fixed, stratified partitions:

- `dev`: 35 questions for repeated development evaluation and tuning.
- `holdout`: 15 questions reserved for milestone or final evaluation.

Both partitions contain standard, paraphrased, ambiguous, out-of-scope, and
high-risk questions. Do not move questions between partitions after comparing
system results unless a new partition version and reason are recorded.

## Run A Partition

Run a live batch only when it is part of the requested work. The examples below use three repetitions to reproduce the completed variation-evaluation design, not as a requirement for every test. The current runner defaults to three and requires at least two repetitions because it calculates answer variation; a single-run CLI mode is not implemented.

Configure the backend for live technical evaluation first:

```text
EXECUTION_CONTEXT=technical_evaluation
AI_PROVIDER=openai
EMBEDDING_PROVIDER=openai
VECTOR_STORE_PROVIDER=chroma
VECTOR_STORE_ALLOW_FALLBACK=false
```

Run the development set during implementation:

```bash
cd backend
.venv/bin/python -m app.scripts.run_technical_evaluation \
  --partition dev \
  --run-id dev-YYYYMMDD-v1 \
  --repetitions 3 \
  --confirm-live-run
```

Run the holdout set only at a planned evaluation checkpoint:

```bash
cd backend
.venv/bin/python -m app.scripts.run_technical_evaluation \
  --partition holdout \
  --run-id holdout-YYYYMMDD-v1 \
  --repetitions 3 \
  --confirm-live-run
```

Each command makes billable OpenAI embedding and answer requests. A run ID
cannot overwrite an existing report or matching partition in the technical
JSONL log.

## Outputs

Each run creates a JSON report and a manual-review CSV under
`data/evaluation/results`. The report includes:

- source hit rates at 1, 3, and the configured Top K, plus reciprocal rank;
- retrieved and cited page accuracy;
- citation source, page, label, and count statistics;
- scope accuracy and a scope confusion matrix;
- escalation accuracy with correct escalation, missed escalation, over
  escalation, and correct non-escalation counts;
- latency distribution and errors by type;
- results for every question type;
- repeated-answer, retrieval, citation, scope, and escalation variation;
- dataset, partition, code, Prompt, corpus, scope registry, and runtime
  configuration fingerprints.

The generated manual-review CSV supports answer correctness, citation support,
unsupported rules, uncertainty, and escalation appropriateness. Fill only the
dimensions that a reviewer actually assesses. Unreviewed fields are missing
judgements, not passes; automated source/page matches do not establish semantic
correctness or citation support.

## Current Supervisor Review

The completed grounded-v9 run contains 150 answers: 35 development questions and
15 holdout questions, each repeated three times under the same configuration.
The supervisor-facing review contains the first answer for each of the 50
questions, selected consistently without choosing the best response.

The supervisor is asked for answer correctness and optional comments. The
researcher has checked the expected policy sources and pages. Those checks do
not replace checking whether a generated claim is supported by the cited text.
Do not report unreviewed dimensions as validated by the supervisor.

Batch entry is optional and may apply one rating to several answers only after
they have been read. A technical Summary worksheet is not required in the
supervisor copy. Preserve source records and identifiers when simplifying a
review workbook. Do not copy the first answer's rating to its two unreviewed
repetitions, or treat 150 responses as 150 independent questions.

For future runs, agree the repetition count and human review scope before
execution. Keep separate reporting for development and holdout results even
when they appear in one workbook. A reused holdout is not a new untouched test
set, and changes informed by holdout failures must be disclosed.
