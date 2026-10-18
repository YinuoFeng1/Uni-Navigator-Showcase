import type { StudyCondition } from "@/lib/types";

export const studyConditionLabels: Record<StudyCondition, string> = {
  A_SIMPLE_LINK: "A - Simple source link",
  B_SECTION: "B - Section and page",
  C_HIGHLIGHT: "C - Highlighted evidence",
  D_NEXT_STEP: "D - Evidence plus next step",
};

export const studyConditionDescriptions: Record<StudyCondition, string> = {
  A_SIMPLE_LINK: "Shows a compact source card with an open-source action.",
  B_SECTION: "Adds document section and page metadata.",
  C_HIGHLIGHT: "Adds a highlighted quote for verification.",
  D_NEXT_STEP: "Adds evidence, limitation, and action guidance.",
};

export const defaultCondition: StudyCondition = "C_HIGHLIGHT";
