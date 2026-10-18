# Version Control

> Historical guidance for the private research repository. This public showcase
> has two curated snapshot commits and does not include the original baseline
> tag. See [publication record](publication.md) for the actual public history.

Uni-Navigator uses Git to preserve research baselines and keep development
changes reviewable.

## Repository Baseline

- Default branch: `main`
- Initial baseline tag: `baseline-legacy-ui-2026-08-03`
- Active frontend presentation: `legacy`
- Preserved workbench snapshot: see `docs/frontend_ui_versions.md`

## Suggested Workflow

Create a short-lived branch for each research or development change:

```bash
git switch -c codex/interview-round-1
```

Review and commit only the intended files:

```bash
git status
git diff
git add <files>
git commit -m "fix: improve participant navigation"
```

Return completed work to `main` using GitHub Desktop or the command line after
the change has been reviewed and tested.

## Never Commit

- API keys or real `.env` files
- Participant or study-session databases
- Raw research exports containing participant-entered text
- Chroma or local JSON vector-store output
- Python virtual environments, Node dependencies, or Next.js build output
- Personal cloud credentials or machine-specific history

The repository `.gitignore` excludes the known local paths for these files.
Before every commit, check `git status` and confirm that no new sensitive or
generated path is being added.

## Phase Checks

Use [development_rules.md](development_rules.md) to choose checks for the change. For an application development phase, run from the repository root:

```bash
cd backend
.venv/bin/pytest
cd ../frontend
../.tools/bin/pnpm test
../.tools/bin/pnpm lint
../.tools/bin/pnpm typecheck
../.tools/bin/pnpm build
```

Documentation-only changes need link, command, consistency, and diff checks. Live evaluation and embedding rebuilds are separate billable operations, not automatic commit prerequisites.
