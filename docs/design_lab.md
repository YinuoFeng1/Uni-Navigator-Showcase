# Design Lab

This is a development fixture gallery. Some examples preserve the earlier task-based workbench for visual reference. The current participant flow is [study_flow.md](study_flow.md); fixture controls do not imply that `/chat` has a session wizard, task rail, trust checklist, or final-response form.

## Access boundary

`/design-lab` is available only when both conditions are true:

- `NODE_ENV=development`
- `NEXT_PUBLIC_STUDY_MODE=development`

Production builds and pilot-mode development return the application not-found surface. The route is absent from navigation.

The Design Lab's data source is only `frontend/lib/designLabFixtures.ts`. Its reusable drawer demo uses the production Evidence Inspector component with local state, but it does not import `frontend/lib/api.ts`, issue `fetch` requests, create sessions, read SQLite, or write study events. All participant, task, answer, citation, source, chunk, page, status, admin, and failure values are synthetic.

## Directions

### Obsidian Workbench

A dark, dense researcher/admin direction with compact status and selected-detail hierarchy. It uses normal sans-serif for narrative content and monospace only for metadata.

### Research Workbench

A preserved design direction with a progress rail, central answer workspace, optional evidence inspector, and responsive reading layout. The progress rail belongs to the earlier task workflow and is not a current participant requirement.

### Paper and Ink

A light document-reading direction with policy-inspired headings, restrained rules, and annotated-source presentation.

Every direction includes synthetic examples of session start, active task, empty/loading/grounded/partial/insufficient answer states, evidence, trust reflection, final response, fail-closed system failure, admin summary, and mobile behavior.

## Visual review

Required review viewports are 1440x900, 1024x768, and 390x844. Inspect long titles, long answers, escalation text, drawer focus, sticky elements, horizontal overflow, light/dark/system appearance, and reduced motion. Store privacy-safe screenshots in `frontend/tests/visual/screenshots/`.

At tablet and mobile widths, the **Open interactive evidence inspector** fixture verifies focus entry, focus return, Escape dismissal, and background scroll locking without any API or research logging.
