export const designLabFixture = Object.freeze({
  fixtureOnly: true,
  participantCode: "P-DEMO-017",
  sessionId: "synthetic-session-design-lab",
  taskId: "synthetic-task-special-consideration",
  taskTitle: "Illness during an assessment",
  scenario:
    "A fictional student became unwell during an assessment period and wants to understand which university process may apply.",
  question: "What should the student check before submitting an application?",
  answer:
    "The student should first identify the relevant assessment process, check the stated eligibility and evidence requirements, and compare the applicable deadline with the fictional scenario dates.",
  longAnswer:
    "The available policy evidence describes the general process, but it does not determine the outcome for every circumstance. The student should verify the current policy version, review the cited clause in context, and avoid treating this prototype response as an approval or an individual decision.",
  limitation:
    "The policy extract cannot confirm whether a particular document will be accepted or whether an exception applies.",
  escalation:
    "Contact the authorised university team before acting when timing, enrolment, visa, financial, progression, appeal, or health consequences could materially affect the student.",
  citation: Object.freeze({
    citationId: "citation-demo-01",
    sourceId: "uq-assessment-procedure",
    chunkId: "uq_assessment_procedure_chunk_0012",
    title:
      "Assessment Procedure: Special Consideration, Extensions and Deferred Assessment",
    version: "Synthetic preview version",
    page: "Page 13",
    passage:
      "Applications should be supported by evidence appropriate to the stated circumstances and submitted within the timeframe described by the applicable procedure.",
  }),
});

export const designDirections = Object.freeze([
  {
    id: "obsidian",
    name: "Obsidian Workbench",
    className: "direction-obsidian",
    rationale:
      "A compact dark operations surface for researchers. It emphasises status, rapid scanning, and selected-record inspection without adopting terminal conventions.",
  },
  {
    id: "research",
    name: "Research Workbench",
    className: "direction-research",
    rationale:
      "The recommended participant direction. Neutral surfaces, persistent progress, a readable answer column, and a focused evidence inspector keep the study task calm and legible.",
  },
  {
    id: "paper",
    name: "Paper and Ink",
    className: "direction-paper",
    rationale:
      "A document-led academic direction. It gives policy passages a familiar reading hierarchy while keeping interaction controls restrained.",
  },
]);

