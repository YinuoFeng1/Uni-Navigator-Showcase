# Frontend Accessibility Notes

## Implemented baseline

- Semantic main, header, navigation, section, article, aside, form, and table landmarks.
- Visible labels for input fields and accessible names for icon-only commands.
- Global focus ring token with `focus-visible` states.
- Approximately 44px primary touch targets; evidence rating buttons remain compact but keyboard reachable.
- Statuses combine icon and text and do not rely on color alone.
- Loading, saved, and failure messages use status/alert semantics and live regions where state changes.
- The multiline question composer submits only through its explicit Send command, avoiding accidental Enter submission.
- Evidence drawers move focus inside, trap Tab navigation, close on Escape or backdrop, restore prior focus, and lock background scrolling.
- `prefers-reduced-motion: reduce` disables meaningful transition and animation duration.
- Long answer, source title, metadata, and escalation content wrap without viewport-scaled font sizes.

## Responsive behavior

Verify the current `/chat` interface at desktop, tablet, and mobile sizes. Evidence viewing, citation navigation, question entry, and error messages must remain usable without text overlap or lost keyboard focus. The old study rail, progress sequence, and condition policy are retired; historical Design Lab examples do not establish accessibility of the current page.

## Remaining manual checks

Before formal pilot approval, complete keyboard-only testing with VoiceOver on macOS, confirm contrast against the final UQ-approved palette, test 200% browser zoom, and conduct researcher-observed mobile usability checks. Accessibility implementation is not equivalent to an independent WCAG audit.
