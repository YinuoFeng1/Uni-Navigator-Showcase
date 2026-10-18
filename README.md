# Uni-Navigator

A research prototype exploring evidence use and trust in a university policy
chatbot. It retrieves official policy passages, generates a live answer, and
lets users inspect the citations and original sources. It is not an official
university advice service or a production deployment.

## Two Snapshots

This repository is a curated showcase prepared on 18 October 2026, **not the
original development history**. It contains exactly two commits:

1. [White frontend snapshot](../../tree/5ee58079b6c3355d891430d738dec33dd8f0eacc):
   the preserved Research Workbench interface, frontend only.
2. Current prototype: the current frontend, backend, tests and documentation.

The original private repository, full commit history and research records are
unchanged. See [version comparison](docs/frontend_ui_versions.md) and
[publication boundaries](docs/publication.md).

## Current Workflow

- `/chat`: one evidence presentation, live answers, clickable numbered citations,
  evidence inspection, original-source links, uncertainty and staff guidance.
- Researcher setup: participant code and round, acknowledged session start/end,
  activity logging and visible retryable save failures.
- `/admin`: session monitoring and filtered participant summaries, activity
  timelines and question/answer exports.
- Shared backend: scope checking, OpenAI embeddings, Chroma retrieval, official
  passages, live generation, citation validation and provenance logging.
- Technical evaluation inputs: 50 questions, with 35 development and 15 holdout
  items. Expected labels are not human ratings of generated answer correctness.

The separate `/study` workspace, A/B/C/D selector and in-app final-decision form
are retired. Archived screenshots show the old interface, not the current UI.

## Local Setup

Use Python 3.11+ and Node.js 22+ with pnpm 11.2.2. Dependencies are installed
locally; no global Python installation or credentials are included.

```bash
git clone https://github.com/YinuoFeng1/Uni-Navigator-Showcase.git
cd Uni-Navigator-Showcase
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
cd frontend
pnpm install --frozen-lockfile
```

Set `OPENAI_API_KEY` privately in `backend/.env`. The model identifiers in the
example reproduce the source configuration; verify availability in your account
before running. Changing models changes the research configuration.

Policy PDFs and vectors are deliberately not distributed. Download the listed
versions from their official URLs into `data/corpus/official/`, using the exact
filenames in [the download manifest](data/corpus/policy_download_manifest.json).
Check each SHA-256 against the manifest. A different version must be treated as
a new corpus, not as a reproduction of the original evaluation.

From the repository root, validate and build the corpus:

```bash
cd backend
.venv/bin/python -m app.scripts.ingest_corpus --source-type official --validate-only
# The following rebuild calls the embedding API and incurs usage charges.
.venv/bin/python -m app.scripts.ingest_corpus --source-type official --rebuild
.venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

In a second terminal, from the repository root:

```bash
cd frontend
pnpm dev --port 3000
```

Open `http://localhost:3000/chat`; the local researcher dashboard is
`http://localhost:3000/admin`. Do not expose the backend or Admin directly to the
internet. The included Mac sharing helper additionally needs local pnpm, Caddy
and cloudflared executables under `.tools/bin`; they are not included. See
[public testing](docs/public_testing.md) before attempting remote access.

The default configuration is development-only. A fresh clone is not authorised
for collecting formal participant data. Formal logging requires participant
runtime settings, consent and a valid frozen system configuration; see
[study flow](docs/study_flow.md) and [pilot runbook](docs/pilot_runbook.md).

## Checks

```bash
cd backend
.venv/bin/pytest
cd ../frontend
pnpm test
pnpm lint
pnpm typecheck
pnpm build
```

Unit tests use synthetic fixtures, not participant databases or paid live API
runs. See [architecture](docs/architecture.md) and
[technical evaluation](docs/technical_evaluation.md) for implementation detail.
Older engineering notes are retained as context and may describe superseded
phases; use this README for portable startup instructions.

## Data And Rights

No participant records, recordings, questionnaires, research databases, model
keys, vector stores or completed evaluation outputs are published. Official
policy documents remain with their publishers; metadata links do not grant
redistribution rights. No open-source licence has been selected for this code.
Public visibility alone does not grant a general reuse licence. Third-party
dependencies retain their own licences.
