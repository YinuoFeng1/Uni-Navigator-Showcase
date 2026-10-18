# Uni-Navigator Agent Guidance

Uni-Navigator is a research prototype for understanding evidence use and trust
in a university policy chatbot. Build for the current research design.

## Current Scope

- Use [docs/study_flow.md](docs/study_flow.md) for the current research design and
  [docs/development_rules.md](docs/development_rules.md) for engineering rules.
- Participants use `/chat` with one evidence presentation. The separate `/study`
  workspace, A/B/C/D selector, trust checklist, and final-decision form are retired.
- All application chat uses the shared `ChatOrchestrator`, OpenAI generation and
  embeddings, official policy passages, Chroma, and validated citations. Do not
  restore fixed answers, answer-package matching, or silent fallback answers.
- Chat has a researcher-controlled round/participant session. It binds activity
  to the server session without a task; historical task contracts remain.
  Formal logging still requires the participant runtime and a valid frozen
  configuration. Development sessions are not formal data; see [docs/pilot_runbook.md](docs/pilot_runbook.md).
- Latest explicit user decisions guide the work. Earlier assistant suggestions,
  historical prompts, archived interfaces, and example commands are not new
  requirements. Report disagreements between current code and documentation.

## Implementation

- Keep changes focused, readable, modular, and working end to end. Use existing
  dependencies before adding packages or abstractions; check their capabilities.
- Preserve behaviour still required by the current design. Remove obsolete
  paths within the requested scope instead of adding compatibility layers for them.
- Change APIs with their active callers and explicit frontend types. Use a
  non-destructive data migration when necessary to preserve existing records.
- Never delete research databases, historical logs, or evaluation records as
  cleanup. Never invent human ratings or overwrite a completed evaluation run.
- Confirm successful saves only after backend acknowledgement. Preserve failed
  submissions for retry where supported and make failures visible.
- Keep secrets out of code, exports, and logs. Collect only necessary study data.

## Verification and Documentation

- Use the scoped and phase checks in [docs/development_rules.md](docs/development_rules.md).
  Documentation-only edits need document checks, not full application tests.
- Real API evaluation and embedding rebuilds are separate, billable operations;
  run them only within the user's requested scope. Existing authorisation need
  not be requested again. A documentation edit does not authorise a live run.
- Keep current operating instructions aligned when changing behaviour. Mark
  historical material clearly instead of treating it as current instructions.
- Use relevant skills for their task. Follow the user's template and requested
  scope; do not add workbook tabs, approval steps, or research procedures merely
  because a generic workflow includes them.
- For runtime boundaries read [docs/architecture.md](docs/architecture.md); for
  evaluation splits and human review read [docs/technical_evaluation.md](docs/technical_evaluation.md).
  Read other documents only when relevant to the task.
