# P0B Retrieval Failure Review

This review uses the July 17, 2026 OpenAI evaluation result and the five downloaded official PDFs. Labels were not changed merely to improve the pass count.

## Page and Keyword Cases

### `academic_progression_student_visa`

The labelled progression clause is on PDF page 6, but top-five retrieval returned Enrolment page 11 and Academic Progression pages 1-2, followed by other enrolment pages. The source family was plausible and no PDF page offset or malformed page metadata was found. One-page chunk boundaries preserved page 6, so this is primarily ranking and evidence insufficiency: the query's CoE/visa terms favoured the Enrolment procedure. Academic Progression page 6 remains the required supporting page; adjacent pages 1-2 are not enough for the labelled condition.

### `assessment_extension_appeal`

The labelled appeal clause is on Assessment page 8. Retrieval preferred Assessment pages 7, 6, 17, and 5 plus an Examinations result. Page extraction and numbering were intact and page 8 was a separate retrievable chunk. This is a ranking/terminology problem: general extension content outranked the short grievance clause. Page 7 is useful adjacent context but does not contain the appeal pathway, so the evidence is insufficient for the labelled question.

### `ambiguous_failure_exclusion`

Top-five retrieval was dominated by course-removal and enrolment pages; no Academic Progression page 2-5 chunk appeared and the expected phrase was absent. PDF page numbering and chunk boundaries were intact. The broad wording mixes failure, exclusion, and multiple possible processes, so this is ranking plus genuine evidence insufficiency rather than an annotation offset. The case remains in-corpus because the progression procedure directly covers exclusion, but the system should not claim that the retrieved adjacent documents answer it.

No chunking change or OpenAI collection rebuild was justified by these three reviews.

## Escalation Cases

### `academic_progression_intervention_plan`

Expected escalation was correct. The synonym list omitted `progression intervention`, `intervention notice`, and `Progression Improvement Plan`; these terms were added to the transparent safety vocabulary.

### `removal_special_circumstances_test`

Expected escalation was correct. The vocabulary recognised `special consideration` but not `special circumstance(s)`; both forms were added.

### `enrolment_prerequisite_rules`

The question itself is general and its no-escalation label remains reasonable when grounded evidence is available. The observed system escalated because retrieval was only partial, not because an escalation synonym was missing. This is a retrieval-status issue and should not be repaired by changing escalation wording or the ground-truth label.

Escalation is now evaluated by structured category separately from retrieval correctness, so an exact phrase mismatch cannot fail an otherwise correct retrieval result.
