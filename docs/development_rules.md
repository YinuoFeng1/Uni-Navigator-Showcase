# Uni-Navigator Development Rules

Uni-Navigator is a research prototype for a human-centred source-aware administrative RAG chatbot. Development should prioritise research validity, maintainability, and safe user interaction.

## Core Principles

1. Preserve working behaviour that is still required by the current research design.
2. Keep changes small and reviewable.
3. Do not rewrite working modules without a clear reason.
4. Prefer readable code over clever abstractions.
5. Change backend APIs together with active callers and tests when current requirements need it. Do not retain obsolete API paths solely for compatibility.
6. Keep frontend API types explicit.
7. Every research log should be structured enough for later analysis.
8. Do not collect unnecessary sensitive personal information.
9. Clearly separate prototype functionality from deployment-ready production functionality.
10. Add tests for backend data and logging features.
11. Build the smallest complete implementation, then extend it in working increments. Choose durable boundaries without speculative frameworks or unfinished infrastructure.
12. Prefer established libraries and existing dependencies. Check documentation and types before implementing a replacement or adding a package.
13. Keep components modular and concerns separate. Refactor when it removes demonstrated complexity or enables the requested behaviour.

## Changes and Data Preservation

Remove obsolete execution paths within the requested scope. Protect existing research databases, logs, and evaluation records even when their original interface is retired. In particular, never delete `data/logs/uni_navigator.db` as part of cleanup or index rebuilding.

Necessary schema changes may use a non-destructive migration with a backup, a clear data mapping, and verification that existing records remain readable. Avoid compatibility layers without an active consumer; preserving research records is an active requirement.

Show save confirmation only after the backend acknowledges the write. Keep failed submissions available for retry where supported, and report write failures separately from answer-generation failures.

Treat the latest explicit user decisions and [study_flow.md](study_flow.md) as the current research scope. Earlier assistant recommendations and historical design records do not create additional requirements. Update affected operating documents when behaviour changes. Record implementation gaps rather than describing planned capabilities as complete.

## Research Alignment

The current design uses formative feedback, technical evaluation, and user evaluation through `/chat`, followed by a separate questionnaire. Features should support relevant research goals:

- Student understanding of policy answers
- Evidence checking
- Citation/source verification
- Trust calibration
- Confidence
- Recognition of uncertainty
- Recognition of when to contact human staff
- Feedback and observed use of the Chat interface

These goals do not require restoring the retired task workspace, condition selector, trust checklist, or final-decision form. Keep the technical development and holdout sets separate. Human correctness ratings must remain unfilled until reviewed; automated source/page matches do not establish answer correctness.

Use relevant skills for document, spreadsheet, and other specialist tasks. Preserve supplied templates and keep deliverables appropriate for their audience. A Summary worksheet, a batch-rating control, or three repetitions per question is a task choice, not a universal requirement.

## Checks During Development

- For documentation-only edits, check changed links, referenced paths and commands, consistency with current code, and `git diff --check`.
- For code changes, run checks and meaningful tests for the affected behaviour. Include persistence and failure cases when changing data or logging.
- Run the full phase checks below for application development milestones and changes across shared boundaries. Do not repeat unchanged checks without a new change or unresolved failure.
- Run live API evaluations and embedding rebuilds separately when requested; they can incur costs and write research outputs. Unit tests should not need API access.
- Report checks actually run, their results, and material checks not performed.

## Quality Checks Before Finishing A Development Phase

Run these from the repository root for an application development phase:

```bash
cd backend
.venv/bin/pytest
cd ../frontend
../.tools/bin/pnpm test
../.tools/bin/pnpm lint
../.tools/bin/pnpm typecheck
../.tools/bin/pnpm build
```

If a command fails, fix the issue or clearly report the failure.

The local pnpm wrapper needs Node.js on PATH or `CODEX_NODE_BIN` set to an executable. VS Code supplies this setting; terminal setup is documented in [developer_notes.md](developer_notes.md). Release validation and live retrieval checks are additional checks for work on those components, not prerequisites for editing prose or spreadsheets.
