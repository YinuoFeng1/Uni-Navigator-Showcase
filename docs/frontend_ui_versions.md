# White Frontend To Current Prototype

These are two presentation snapshots, not a reconstruction of every development
step or proof that a particular change resulted from a particular interview.
The original development history remains in the private research repository.

## Snapshot 1: Preserved White Interface

[Browse snapshot 1](../../../tree/5ee58079b6c3355d891430d738dec33dd8f0eacc).
It was extracted from the frontend archive preserved on 3 August 2026, not from
a complete historical backend release. Select `research_workbench` and light
appearance, then open `/study` for the white version. See its README for a
deliberately disconnected visual preview.

## Snapshot 2: Current Prototype

Application code is copied from private source revision
`4eb799c8882caa59bd2c2cf1ded148db4a77c30f`. The current participant route is
`/chat`, with the `legacy` presentation setting. The setting name is historical;
it does not mean that the application logic is the old implementation.

| Area | White snapshot | Current snapshot |
| --- | --- | --- |
| Primary flow | Dedicated six-step `/study` workspace | Chat with researcher-controlled test session |
| Task controls | Scenario selection, confidence and final-decision forms | No in-app task assignment or final-decision form |
| Evidence conditions | A/B/C/D presentation selector | One evidence presentation |
| Layout | White/grey workbench and multiple study panels | Chat-focused interface with purple accents |
| Answers | Historical frontend contracts; matching backend not included | Shared live RAG backend with validated citation labels |
| Citation navigation | Citation cards and an evidence inspector | Numbered inline citations link to corresponding evidence |
| Evidence labelling | Historical source labels and score display | Evidence-passage and distinct-policy-file counts |
| Data collection | Task-based study controls | Round/participant sessions, question/answer and activity logging |
| Failure handling | Historical controls | Acknowledged saves, preserved failed submissions and retry |
| Research exports | Historical administration view | Filtered participants, timeline and answer exports |

An evidence inspector, source links and input above the answers already existed
in the white interface; they are not claimed as entirely new additions.
Questionnaires and interviews are conducted separately from the current app.

## Viewing Versions

The first commit preserves the white frontend in Git; the latest commit opens
the current source. Use GitHub's commit comparison to inspect actual changes.
The current `/study` route cannot be restored merely by changing a theme setting.
Use a separate checkout of snapshot 1 so historical controls never write into
the current research database.
