# Uni-Navigator Frontend Design System

## Scope

The current Chat interface and study procedure are defined in [study_flow.md](study_flow.md). The Research Workbench is a presentation-only frontend option; legacy remains the default. Styling does not alter API payloads, answer content, or logging. The task rail and condition-based layouts described as historical below are not requirements for the current interface.

## Reference study

The UI study used the public `xai-org/grok-build` repository at the exact commit `8adf9013a0929e5c7f1d4e849492d2387837a28d`. The following files were inspected read-only:

- `crates/codegen/xai-grok-pager/docs/user-guide/03-keyboard-shortcuts.md`
- `crates/codegen/xai-grok-pager/docs/user-guide/06-theming.md`
- `crates/codegen/xai-grok-pager/docs/user-guide/23-dashboard.md`
- `crates/codegen/xai-grok-pager/src/app/agent_view/panes.rs`
- `crates/codegen/xai-grok-pager/src/app/agent_view/prompt.rs`
- `crates/codegen/xai-grok-pager/src/app/agent_view/modals.rs`
- `crates/codegen/xai-grok-pager/src/views/status_bar.rs`
- `crates/codegen/xai-grok-pager/src/views/modal_window.rs`
- `crates/codegen/xai-grok-pager/src/views/dashboard/layout.rs`
- `crates/codegen/xai-grok-pager/src/views/dashboard/render.rs`
- `crates/codegen/xai-grok-pager-render/src/theme/mod.rs`
- `crates/codegen/xai-grok-pager-render/src/theme/system_appearance.rs`

Adapted patterns are a persistent working context, separate scrollable content and composer surfaces, compact status information, focused detail viewers, Escape-first overlays, responsive panel thresholds, centralized theme tokens, and system appearance support.

Deliberately rejected patterns are terminal styling, full-interface monospace, keyboard-only navigation, agent terminology, command palettes, shell controls, coding panes, branded palettes, session rewind, tool output, plugins, and Grok/xAI wording or assets.

## Tokens

Tokens live in `frontend/app/globals.css` and use the `--ui-*` namespace.

- Surfaces: background, elevated, recessed, subtle/strong borders.
- Text: primary, secondary, muted, mono metadata.
- Semantic states: accent, success, warning, danger, uncertainty, evidence highlight, focus ring.
- Spacing: `2xs`, `xs`, `sm`, `md`, `lg`, `xl`, `2xl`.
- Radius: 4, 6, and 8px. Cards do not exceed 8px.
- Elevation: none, subtle, overlay.
- Motion: 120, 170, and 200ms; reduced-motion collapses transitions and animation.

Light, dark, and system appearances share the same semantic names. The appearance switch stores only a local presentation preference.

## Historical Workbench Hierarchy

The earlier workbench design used a compact top bar, a 236-268px study rail, an answer workspace, and a 340-390px evidence inspector. Smaller screens collapsed the rail and moved evidence into a drawer. These details describe the preserved design and fixtures; the current Chat interface has no study rail or task progress sequence.

The common status vocabulary is implemented by `StatusChip`, `SystemStatusBar`, `InlineNotice`, `BlockingFailurePanel`, `SavedIndicator`, `LoadingIndicator`, and `RetrievalStatusBadge`.

## Current Evidence Presentation

Chat uses one source-aware presentation with:

- citation visibility
- section/page visibility
- highlighted passage visibility
- evidence inspector availability
- limitations, uncertainty, and escalation visibility
- source interaction controls

The old `presentationPolicy.mjs` and condition selector were removed. Retained backend condition manifests describe the previous study contract, not a current frontend experiment. Theme and viewport choices must preserve answer text, evidence identifiers, and logging behaviour.

## Feature flag and rollback

Set `NEXT_PUBLIC_UI_THEME=research_workbench` and restart/rebuild the frontend to preview the workbench. Missing, invalid, or `legacy` values resolve to the legacy presentation.

Rollback requires only setting `NEXT_PUBLIC_UI_THEME=legacy` and restarting the frontend. No database, API, corpus, release, or migration rollback is involved.
