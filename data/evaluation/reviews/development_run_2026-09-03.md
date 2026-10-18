# Development Set Evaluation Record

## Scope

- Dataset: `end-to-end-live-rag-2026-09-02.3`
- Partition: `dev` only (35 questions)
- Repetitions: 3 per question (105 attempts)
- Model: `gpt-5.4-mini-2026-03-17`
- Full run: `dev-20260903-gpt54mini-groundedv7-r2`
- Holdout status: not inspected or run

## Automated Results Before Tuning

| Measure | Result |
| --- | ---: |
| Successful responses | 101 / 105 (96.19%) |
| Automated pass rate | 94.29% |
| Expected source in Top K | 100.00% |
| Expected page in Top K | 96.67% |
| Expected source cited | 100.00% |
| Expected page cited | 96.67% |
| Scope accuracy | 100.00% |
| Escalation accuracy | 100.00% |
| Mean latency | 1,899.65 ms |
| Median latency | 1,737 ms |
| P95 latency | 3,386 ms |

The four failed attempts were all rejected by the citation validator. Nine of
the 105 attempts used the single permitted citation-format correction request.
Retrieval and citation sets were consistent across all three repetitions. The
mean pairwise answer similarity was 0.6087, and only 14.71% of questions
produced exactly identical answer text across repetitions.

## Preliminary Answer Review

The generated workbook contains an AI-assisted preliminary coding pass. These
figures are not human-coded study results and must not be reported as such.

| Criterion | Yes | Partial or unclear | No | Not applicable |
| --- | ---: | ---: | ---: | ---: |
| Answers the question | 89 | 12 | 4 | 0 |
| Citations support conclusions | 73 | 20 | 0 | 12 |
| Unsupported rule absent | 93 | 5 | 7 | 0 |
| Uncertainty appropriate | 99 | 6 | 0 | 0 |
| Escalation appropriate | 105 | 0 | 0 | 0 |

Twenty-two attempts are flagged for researcher review. The researcher should
confirm every flagged attempt and a sample of unflagged attempts before using
manual quality measures in the thesis.

## Development Findings And Changes

1. Some ambiguity answers treated absence from retrieved passages as evidence
   that a rule or outcome did not exist. `grounded-v9` now forbids conclusions
   based on corpus silence and requires an explicit unresolved-evidence form.
2. Four ambiguity attempts were rejected when safe uncertainty or staff
   confirmation sentences were treated as uncited policy claims. The validator
   now permits only narrowly structured uncertainty and confirmation text;
   uncited deadlines, eligibility rules, outcomes and process claims remain
   blocked.
3. The overload and visa question did not retrieve the reviewed Enrolment
   Procedure page 13. Query expansion `uq-policy-query-v2` adds a general
   concept boost for the semester enrolment-limit approval clause. Page 13 is
   now ranked first for that development question.
4. One generated overload answer selected a broader program-variation process
   instead of the direct semester-limit process. `grounded-v9` instructs the
   model to prefer the most directly relevant ranked passage and not substitute
   a related approval process.

These changes are implemented in code revision
`6608c68a7d7b3eaeed86ac2a73bcc32c8960c614`. The draft Pilot release is version
`0.10.0` with prompt `grounded-v9`.

## Targeted Regression Checks

- The citation-validator refinement passed a 9-attempt development regression.
- A `grounded-v8` ambiguity regression produced 17 successful responses from
  18 attempts; the remaining failure exposed the staff-confirmation validator
  boundary.
- After fixing that boundary, the appeal and correctly worded room ambiguity
  questions passed 6 of 6 attempts with the expected scope and escalation.
- Under `grounded-v9`, the overload and visa question passed 3 of 3 attempts;
  Enrolment Procedure page 13 ranked first each time, the answer identified the
  Associate Dean (Academic) process, and personal approval remained unresolved.

One temporary `grounded-v8` regression run used a deferred-exam room question
under the `room_ambiguous_01` identifier. It is retained in the append-only
technical log but is excluded from all reported metrics; the corrected question
was rerun separately.

## Verification

- Backend: 183 tests passed.
- Frontend: lint passed.
- Frontend: type check passed.
- Frontend: production build passed.
- Study logs and `data/logs/uni_navigator.db` were not deleted or modified by
  evaluation cleanup.
