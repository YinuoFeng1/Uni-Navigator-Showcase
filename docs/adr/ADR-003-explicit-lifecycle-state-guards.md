# ADR-003: Explicit Study Lifecycle State Guards

Status: historical scope; retained backend contracts, not the current UI workflow

The earlier task-based study design introduced pure enums and guard functions for session, task, interaction, and final-response transitions. It used nullable session-state fields to preserve older records. Its backend activation contract requires notice acknowledgement, a frozen release, and passing preflight; failed interactions cannot complete the old task flow.

The current [research design](../study_flow.md) has retired the task workspace. Do not restore its UI or duplicate its lifecycle in the new interface merely to follow this record. Chat now uses simple researcher-controlled sessions without assigned tasks; see [pilot_runbook.md](../pilot_runbook.md).

Future schema work follows [development_rules.md](../development_rules.md): use necessary non-destructive migrations and verify historical records remain readable. The original nullable-field approach is an implementation history, not a rule against migrations.
