# Ethics, Safety, Privacy, and De-identification Notes

Uni-Navigator is a local research prototype for an HCI-style study of source-aware administrative RAG interactions. It is not an official university advice service and must not be presented as one.

## UQ-Style Ethics Readiness

Human participant evaluation involving people, their responses, or their data requires appropriate ethics approval or formal exemption before recruitment begins. For UQ work, use the MyResearch Ethics process and follow the approved protocol.

The current Chat interface has no consent or study-readiness checkbox. Provide the Participant Information Sheet and record consent through the agreed process outside Chat; viewing the prototype notice does not record consent.

## Data Minimisation

Use synthetic/general scenarios only. Do not ask participants to enter:

- real names
- student IDs or student numbers
- visa or passport details
- health information or diagnoses
- financial account details
- appeal, disciplinary, or complaint case details
- academic transcript or progression records
- addresses, phone numbers, email addresses, TFNs, or other sensitive identifiers

Participant labels should be study codes such as `P-001`, not real names or university identifiers.

## Data Management

SQLite stores current Chat sessions, interactions, feedback, evidence use, and events, plus retained task, final-response, and trust-checklist records from the earlier study workflow. Current Chat creates no task, final-response, or trust-checklist records. Treat SQLite logs and raw CSV exports as research data. Round and participant codes link the new Chat records; formal-runtime prerequisites remain mandatory, as described in [pilot_runbook.md](pilot_runbook.md).

Raw logs CSV may contain participant-entered free text. Store and transfer it only according to the approved ethics and data management process.

Session summary and task summary CSVs avoid full final decision text and notes, exporting counts, ratings, booleans, lengths, and `notes_present`. They describe retained backend records; they do not cover new sessions automatically created by Chat. Choose exports that actually contain the intended records and minimise unnecessary text disclosure.

ChromaDB and the local JSON vector store store only policy chunks, embeddings, and source metadata for retrieval/citation. They must not store participant/session/task research logs.

## Admin and Export Safety

The admin dashboard and CSV endpoints are local prototype tools. Protect them before any deployment and do not expose them publicly.

Admin screens should show counts, previews, lengths, ratings, and booleans by default. Full final decision text and notes should not be displayed by default.

## Researcher Checklist Before Pilot

- Confirm ethics approval or formal exemption.
- Confirm Participant Information Sheet and Consent Form process.
- Confirm participants will use synthetic/general scenarios only.
- Confirm participant labels are study codes.
- Confirm no real personal cases will be entered.
- Confirm data export and storage location.
- Confirm raw CSV handling and access control.
- Confirm the selected exports cover the intended records and minimise unnecessary text disclosure.
- Confirm deletion/withdrawal handling according to the approved ethics process.
- Confirm admin/export endpoints are not publicly exposed.

## Scope and Technical Failure Safety

An `out_of_domain` question is outside university administration. A `university_admin_but_out_of_corpus` question may be a legitimate university matter but is unsupported by the frozen official corpus. Both must avoid source-backed advice; ambiguous mixed questions must expose uncertainty and a suitable staff-contact category.

The principal pilot retrieval harm is a false-grounded answer for an out-of-corpus question. Shared administrative language makes cosine score alone unsafe for scope decisions, so the versioned scope registry and expanded evaluation must be reviewed as research instruments.

Chat technical failures do not generate substitute answers. The UI distinguishes retryable failures from blocking failures, and separately reports unconfirmed log writes. The retained task backend also rejects trust/final/task-completion operations for a failed task run; those controls are not part of the current Chat UI. Failure metadata excludes the question, API keys, secret-bearing traces, and other participant text.

Successful interaction provenance includes provider/model/dimension, collection, retrieval thresholds and mode, scope decision and registry version, frozen corpus fingerprint, answer mode, task version, condition, and app revision. These fields support validity checks across sessions; they are operational metadata, not a reason to collect additional personal information.

## Participant and Technical Evaluation Separation

Both the current Chat and the backend participant runtime use live RAG and OpenAI generation. The retained backend release contract freezes the model, prompt template, generation parameters, embedding model, vector collection, retrieval settings, corpus fingerprint, scope registry, task manifest, condition manifest, and application revision. Chat supplies a session ID; the backend derives its participant and presentation without requiring an assigned task. Development records must not be relabelled as formal participant data. Technical runs have run IDs, cannot carry participant session IDs, and are excluded from participant exports.

Generated wording can vary even under a frozen configuration. Analysis must treat this as part of the study rather than assuming identical answers across participants. Human reviewers remain responsible for corpus currentness, retrieval quality, prompt safety, participant-facing uncertainty, escalation behaviour, and the approved external-processing disclosure.
