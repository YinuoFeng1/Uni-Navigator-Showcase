# Supervisor-Aligned Research Evaluation Flow

Uni-Navigator uses one student-facing Chat interface rather than a separate task workspace or multiple evidence-display conditions. The current research design has three connected phases.

## 1. Formative Interviews

Recruit approximately 3-5 people to identify policy information-seeking problems and useful interface features. Use a short interview guide and record the resulting design requirements. Follow the approved consent and data collection procedure. If audio recording is not included in the approved materials, collect written responses and researcher notes instead.

## 2. Technical Evaluation

Use the versioned 50-question dataset to evaluate the live RAG pipeline. Record retrieval results and generated answers in the technical evaluation output, then conduct human review of:

- whether the expected source appears in the retrieved passages
- whether page references are correct
- whether the answer addresses the question
- whether citations support the policy claims
- whether unsupported rules are introduced
- whether uncertainty and staff escalation are appropriate

Development and holdout partitions remain separate. Do not tune the system using holdout results.

For the completed grounded-v9 evaluation, each of the 50 questions was run three times to examine answer variation. The supervisor review uses the first answer for each question, selected consistently, and asks for correctness plus optional comments. Existing researcher checks of expected sources and pages should not be presented as semantic validation of every generated claim. Additional manual dimensions remain unjudged unless reviewed.

Three repetitions are not mandatory for every future evaluation. Record the intended repetition count and review scope for each run; current runner constraints and commands are in [technical_evaluation.md](technical_evaluation.md).

## 3. User Evaluation

Recruit approximately 13-15 participants. After the approved information and consent process, participants use `/chat` to try the prototype. They then complete a short questionnaire with closed and written open-response items covering:

- overall experience
- useful or liked features
- confusing or disliked features
- problems with buttons, layout, navigation, and evidence presentation
- suggested future improvements

The questionnaire includes one overall 1-5 trust rating after the Chat session. There is no per-task trust rating or added in-app decision form. A short post-use interview may then explore one answer selected by the participant and why they trusted or doubted it; connect that explanation to the answer and recorded evidence actions without treating clicks as proof of understanding.

The previous six-step `/study` workspace, assigned task controls, A/B/C/D condition selector, in-app final decision form, and trust checklist are not part of this evaluation design.

## Participant-Facing Interface

The Chat interface always shows the same source-aware presentation:

- a direct live AI answer
- action steps
- official source title, section, and page
- highlighted evidence passages
- limitations and uncertainty
- staff-contact guidance when recommended

Raw vector similarity scores are not shown because they are technical retrieval signals, not probabilities that an answer is correct.

## Retained Research Logging

The frontend continues to request confirmed backend writes for:

- submitted questions and received answers
- full answer and citation provenance
- inline citation clicks, evidence panel opens, original source opens, and source checks
- response time, failures, and model/retrieval configuration
- optional answer feedback

The researcher enters a test round and participant code (such as `pilot-01` and `P01`) in Chat after obtaining consent separately, starts the session, and ends it after activity is saved. Questions, answers, evidence activity, and feedback share that session. No real name is required. A round cannot mix runtime fingerprints.

Admin's **Chat study exports** filters by round and participant and exports participant-session summaries, activity timelines, and questions with complete answers and citations. Historical exports and SQLite records remain intact. The current interface creates no tasks, trust checklists, or final decisions. One internal presentation identifier is retained for provenance, not an A/B/C/D experiment.

The session is labelled with the actual backend execution context. Formal `participant_study` operation still requires the frozen configuration and preflight checks; development tests must not be relabelled. See [pilot_runbook.md](pilot_runbook.md).

## Ethics and Privacy

The interface is a research prototype, not an official advice service. Participants must not enter real names, student numbers, contact details, medical details, visa identifiers, financial information, academic records, or case documents. Use the approved Participant Information Sheet, Consent Form, withdrawal process, and data management plan before collecting participant data.

Audio and screen recordings are collected separately only when covered by the agreed consent and protocol. Match them to application exports using the round and participant code, not a real name. The application does not record audio or the screen.
