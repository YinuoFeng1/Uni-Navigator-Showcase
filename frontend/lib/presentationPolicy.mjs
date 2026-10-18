const PRESENTATION_POLICIES = Object.freeze({
  A_SIMPLE_LINK: Object.freeze({
    citationVisibility: "simple_link",
    showSection: false,
    showHighlightedPassage: false,
    evidencePanelAvailable: true,
    showLimitations: true,
    showUncertainty: true,
    showEscalation: true,
    showNextStep: false,
    sourceInteractionControls: Object.freeze([
      "open_source",
      "open_evidence_panel",
    ]),
  }),
  B_SECTION: Object.freeze({
    citationVisibility: "section_reference",
    showSection: true,
    showHighlightedPassage: false,
    evidencePanelAvailable: true,
    showLimitations: true,
    showUncertainty: true,
    showEscalation: true,
    showNextStep: false,
    sourceInteractionControls: Object.freeze([
      "open_source",
      "open_evidence_panel",
    ]),
  }),
  C_HIGHLIGHT: Object.freeze({
    citationVisibility: "highlighted_passage",
    showSection: true,
    showHighlightedPassage: true,
    evidencePanelAvailable: true,
    showLimitations: true,
    showUncertainty: true,
    showEscalation: true,
    showNextStep: false,
    sourceInteractionControls: Object.freeze([
      "open_source",
      "open_evidence_panel",
      "highlight_passage",
    ]),
  }),
  D_NEXT_STEP: Object.freeze({
    citationVisibility: "highlighted_passage",
    showSection: true,
    showHighlightedPassage: true,
    evidencePanelAvailable: true,
    showLimitations: true,
    showUncertainty: true,
    showEscalation: true,
    showNextStep: true,
    sourceInteractionControls: Object.freeze([
      "open_source",
      "open_evidence_panel",
      "highlight_passage",
    ]),
  }),
});

export const APPROVED_PRESENTATION_FIELDS = Object.freeze([
  "citationVisibility",
  "showSection",
  "showHighlightedPassage",
  "evidencePanelAvailable",
  "showLimitations",
  "showUncertainty",
  "showEscalation",
  "showNextStep",
  "sourceInteractionControls",
]);

export function getPresentationPolicy(condition) {
  const policy = PRESENTATION_POLICIES[condition];
  if (!policy) {
    throw new Error(`Unknown study condition: ${String(condition)}`);
  }
  return policy;
}

export function listPresentationPolicies() {
  return PRESENTATION_POLICIES;
}

