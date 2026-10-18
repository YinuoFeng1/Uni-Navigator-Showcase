import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { createEvidenceUsePayload } from "../lib/evidencePayload.mjs";
import {
  APPROVED_PRESENTATION_FIELDS,
  getPresentationPolicy,
  listPresentationPolicies,
} from "../lib/presentationPolicy.mjs";
import {
  isDesignLabEnabled,
  resolveUiTheme,
} from "../lib/uiThemePolicy.mjs";

const conditionManifestUrl = new URL(
  "../../data/study/experimental_conditions.json",
  import.meta.url,
);

test("UI theme is presentation-only and defaults safely to legacy", () => {
  const answer = Object.freeze({
    answer: "Frozen substantive answer",
    citations: Object.freeze(["citation-1"]),
  });
  assert.equal(resolveUiTheme(undefined), "legacy");
  assert.equal(resolveUiTheme("unexpected"), "legacy");
  assert.equal(resolveUiTheme("research_workbench"), "research_workbench");
  assert.equal(answer.answer, "Frozen substantive answer");
  assert.deepEqual(answer.citations, ["citation-1"]);
});

test("A/B/C/D policies vary only approved presentation fields", () => {
  const policies = listPresentationPolicies();
  for (const policy of Object.values(policies)) {
    assert.deepEqual(
      Object.keys(policy).sort(),
      [...APPROVED_PRESENTATION_FIELDS].sort(),
    );
  }
  assert.equal(getPresentationPolicy("A_SIMPLE_LINK").showSection, false);
  assert.equal(
    getPresentationPolicy("A_SIMPLE_LINK").showHighlightedPassage,
    false,
  );
  assert.equal(getPresentationPolicy("B_SECTION").showSection, true);
  assert.equal(
    getPresentationPolicy("B_SECTION").showHighlightedPassage,
    false,
  );
  assert.equal(
    getPresentationPolicy("C_HIGHLIGHT").showHighlightedPassage,
    true,
  );
  assert.equal(getPresentationPolicy("D_NEXT_STEP").showNextStep, true);
});

test("A/B/C/D retain the same task answer package bindings", async () => {
  const manifest = JSON.parse(await readFile(conditionManifestUrl, "utf8"));
  const [baseline, ...others] = manifest.conditions;
  for (const condition of others) {
    assert.deepEqual(
      condition.task_answer_packages,
      baseline.task_answer_packages,
    );
  }
});

test("evidence payload preserves citation, source, chunk, page-independent IDs", () => {
  const payload = createEvidenceUsePayload({
    sessionId: "session-1",
    participantLabel: "P-001",
    taskId: "task-1",
    interactionId: "interaction-1",
    citation: {
      id: "display-id",
      citationId: "citation-1",
      sourceId: "source-1",
      chunkId: "chunk-1",
      pageStart: 7,
      pageEnd: 8,
    },
    evidenceAction: "source_checked",
    extras: { evidenceSupportRating: 4 },
  });
  assert.equal(payload.citationId, "citation-1");
  assert.equal(payload.sourceId, "source-1");
  assert.equal(payload.chunkId, "chunk-1");
  assert.equal(payload.interactionId, "interaction-1");
  assert.equal(payload.evidenceSupportRating, 4);
});

test("Design Lab is development-only and its component has no study API path", async () => {
  assert.equal(
    isDesignLabEnabled({ nodeEnv: "development", studyMode: "development" }),
    true,
  );
  assert.equal(
    isDesignLabEnabled({ nodeEnv: "production", studyMode: "development" }),
    false,
  );
  assert.equal(
    isDesignLabEnabled({ nodeEnv: "development", studyMode: "pilot" }),
    false,
  );

  const source = await readFile(
    new URL("../components/design-lab/DesignLab.tsx", import.meta.url),
    "utf8",
  );
  const drawerSource = await readFile(
    new URL("../components/design-lab/EvidenceInspectorDemo.tsx", import.meta.url),
    "utf8",
  );
  for (const fixtureSource of [source, drawerSource]) {
    assert.doesNotMatch(fixtureSource, /@\/lib\/api/);
    assert.doesNotMatch(fixtureSource, /fetch\s*\(/);
    assert.doesNotMatch(
      fixtureSource,
      /logStudyEvent|submitEvidenceUse|startStudySession/,
    );
  }
});

test("Evidence inspector implements Escape, focus return, and scroll lock", async () => {
  const source = await readFile(
    new URL("../components/chat/EvidencePanel.tsx", import.meta.url),
    "utf8",
  );
  assert.match(source, /event\.key === "Escape"/);
  assert.match(source, /previouslyFocused\?\.focus\(\)/);
  assert.match(source, /document\.body\.style\.overflow = "hidden"/);
});

test("responsive presentation policy is viewport-independent", () => {
  const desktop = getPresentationPolicy("C_HIGHLIGHT");
  const mobile = getPresentationPolicy("C_HIGHLIGHT");
  assert.equal(desktop, mobile);
  assert.equal(desktop.evidencePanelAvailable, true);
});

test("condition policy gates evidence APIs and condition-visible content", async () => {
  const chatSource = await readFile(
    new URL("../components/chat/ChatShell.tsx", import.meta.url),
    "utf8",
  );
  const citationSource = await readFile(
    new URL("../components/chat/CitationCard.tsx", import.meta.url),
    "utf8",
  );
  assert.match(chatSource, /getPresentationPolicy\(activeCondition\)/);
  assert.match(
    chatSource,
    /if \(!presentationPolicy\.evidencePanelAvailable\) return/,
  );
  assert.match(citationSource, /policy\.showSection/);
  assert.match(citationSource, /policy\.showHighlightedPassage/);
});

test("failed interactions lock participant controls without a local answer", async () => {
  const chatSource = await readFile(
    new URL("../components/chat/ChatShell.tsx", import.meta.url),
    "utf8",
  );
  assert.match(chatSource, /interactionDisabled \|\| systemFailure \|\| isLoading/);
  assert.match(
    chatSource,
    /disabled=\{interactionDisabled \|\| systemFailure \|\| !lastInteractionId\}/,
  );
  assert.doesNotMatch(chatSource, /setMessages\([^)]*mock/i);
});

test("trust and final-response payload field names remain stable", async () => {
  const studySource = await readFile(
    new URL("../components/study/StudyWorkspace.tsx", import.meta.url),
    "utf8",
  );
  const chatSource = await readFile(
    new URL("../components/chat/ChatShell.tsx", import.meta.url),
    "utf8",
  );
  for (const field of [
    "finalDecisionText",
    "confidenceRating",
    "wouldContactStaff",
    "perceivedAnswerSupported",
  ]) {
    assert.match(studySource, new RegExp(`\\b${field}\\b`));
  }
  for (const field of [
    "answerClear",
    "evidenceChecked",
    "sourceSupportsAnswer",
    "uncertaintyNoticed",
    "wouldContactStaffIfNeeded",
  ]) {
    assert.match(chatSource, new RegExp(`\\b${field}\\b`));
  }
});

test("status semantics and reduced-motion support remain accessible", async () => {
  const statusSource = await readFile(
    new URL("../components/ui/status.tsx", import.meta.url),
    "utf8",
  );
  const cssSource = await readFile(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );
  assert.match(statusSource, /role="status"/);
  assert.match(statusSource, /aria-live="polite"/);
  assert.match(statusSource, /role=\{tone === "danger" \? "alert" : "status"\}/);
  assert.match(cssSource, /prefers-reduced-motion: reduce/);
  assert.match(cssSource, /transition-duration: 0\.01ms !important/);
});

test("admin summaries hide full final decisions by default", async () => {
  const adminSource = await readFile(
    new URL("../components/admin/AdminDashboard.tsx", import.meta.url),
    "utf8",
  );
  assert.match(adminSource, /Show truncated decision preview/);
  assert.match(adminSource, /response\.finalDecisionPreview/);
  assert.doesNotMatch(adminSource, /response\.finalDecisionText/);
});

test("admin workbench exposes actionable preflight failures", async () => {
  const adminSource = await readFile(
    new URL("../components/admin/AdminDashboard.tsx", import.meta.url),
    "utf8",
  );
  assert.match(adminSource, /Pilot readiness/);
  assert.match(adminSource, /failedChecks/);
  assert.match(adminSource, /researcher_action/);
  assert.match(adminSource, /Action: \{action\}/);
  assert.match(adminSource, /Preflight unavailable/);
});

test("admin exports never synthesize an empty dashboard export", async () => {
  const exportSource = await readFile(
    new URL("../components/admin/ExportButton.tsx", import.meta.url),
    "utf8",
  );
  const adminSource = await readFile(
    new URL("../components/admin/AdminDashboard.tsx", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(exportSource, /logs = \[\]/);
  assert.match(exportSource, /No file was created/);
  assert.match(exportSource, /role=\{status\.tone === "danger" \? "alert" : "status"\}/);
  assert.match(adminSource, /<ExportButton \/>/);
});

test("admin workbench constrains wide tables to local scroll frames", async () => {
  const adminSource = await readFile(
    new URL("../components/admin/AdminDashboard.tsx", import.meta.url),
    "utf8",
  );
  const cssSource = await readFile(
    new URL("../app/globals.css", import.meta.url),
    "utf8",
  );
  assert.match(adminSource, /admin-split-panel grid min-w-0/);
  assert.match(adminSource, /grid min-w-0 gap-6/);
  assert.match(cssSource, /\.admin-workbench > \*/);
  assert.match(cssSource, /\.admin-workbench \.admin-table-frame/);
  assert.match(cssSource, /max-width: 100%/);
});

test("task trust summary distinguishes checklists from snapshots", async () => {
  const adminSource = await readFile(
    new URL("../components/admin/AdminDashboard.tsx", import.meta.url),
    "utf8",
  );
  const typesSource = await readFile(
    new URL("../lib/types.ts", import.meta.url),
    "utf8",
  );
  assert.match(adminSource, /task\.trustChecklistCount/);
  assert.match(adminSource, /task\.trustSnapshotCount/);
  assert.match(typesSource, /trustSnapshotCount: number/);
});

test("legacy and workbench routes share the same study and admin logic", async () => {
  const studyRoute = await readFile(
    new URL("../app/study/page.tsx", import.meta.url),
    "utf8",
  );
  const adminRoute = await readFile(
    new URL("../app/admin/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(studyRoute, /<StudyWorkspace workbench \/>/);
  assert.match(studyRoute, /<StudyWorkspace \/>/);
  assert.match(adminRoute, /<AdminDashboard workbench \/>/);
  assert.match(adminRoute, /<AdminDashboard \/>/);
});
