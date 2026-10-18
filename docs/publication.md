# Showcase Publication Record

Prepared: 18 October 2026. This repository intentionally has two newly created
commits. Commit times reflect showcase preparation, not original development.

## Provenance

- Snapshot 1: archived frontend, archive SHA-256
  `8933bf8a6e4164a9fd4b34240d497d7885a99bf1f0346a0f9551029a9a3cb2cd`.
- Snapshot 2: tracked application source at private revision
  `4eb799c8882caa59bd2c2cf1ded148db4a77c30f`.
- Application runtime source is unchanged. Three test files use isolated fixture
  data instead of relying on local vector manifests, downloaded PDFs or a local
  Node wrapper. Publication documentation, ignores and policy download metadata
  are adjusted for a separate public checkout.
- The original private repository, its 20 commits and all local research data
  remain untouched. Local working copies and original `.git` objects are not
  copied into this repository.

## Excluded From Both Snapshots

Real environment files and keys, participant databases and exports, recordings,
questionnaires, completed evaluation output files, embeddings, machine-specific
editor settings and downloaded third-party policy PDFs are not published.
The old archive is represented by its extracted first snapshot, not redistributed
as an opaque archive. The internal ethics application guide is omitted.

Technical evaluation inputs and their reviewed expected policy labels are
included. They are not participant records. A historical development evaluation
note is retained with its date and limitations; its AI-assisted review is not
human assessment and is not a new result from this publication process.

## Checks And Limits

Text-pattern scans covered the original 20 published commits, the archived
frontend, and both showcase snapshots. Credential-pattern matches were reviewed
as test keys or documentation placeholders. This is not a guarantee that an
automated scan can detect every kind of sensitive content. Original binary
policy files are excluded rather than treated as cleared for redistribution.

The old frontend-only snapshot has 19 passing tests and one failing test due to
an unavailable historical answer-package fixture. Its backend is not recreated.
Current-snapshot checks on 18 October 2026:

- Backend: 209 passed; 1 optional gateway integration test skipped because the
  Caddy executable is not installed in the showcase checkout.
- Frontend: 27 tests passed; lint, TypeScript checking and production build passed.
- Tests used the existing local Python and Node dependency installations; this
  was not a clean dependency installation on another computer.
- No live model or embedding requests were made.

No API calls, embedding rebuilds or participant sessions are needed to publish
this source. A public source link is not a publicly hosted running prototype.
The included draft pilot manifest is historical configuration, not an active
study approval or a valid release for this newly created checkout.
