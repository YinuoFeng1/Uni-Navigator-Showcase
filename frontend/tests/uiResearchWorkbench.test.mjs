import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

import { createEvidenceUsePayload } from "../lib/evidencePayload.mjs";
import {
  createCitationAnchorId,
  createCitationSegments,
} from "../lib/citationText.mjs";
import { isDesignLabEnabled, resolveUiTheme } from "../lib/uiThemePolicy.mjs";

test("UI theme is presentation-only and defaults safely to legacy", () => {
  assert.equal(resolveUiTheme(undefined), "legacy");
  assert.equal(resolveUiTheme("unexpected"), "legacy");
  assert.equal(resolveUiTheme("research_workbench"), "research_workbench");
});

test("evidence payload preserves stable citation and retrieval IDs", () => {
  const payload = createEvidenceUsePayload({
    interactionId: "interaction-1",
    citation: {
      id: "display-id",
      citationId: "citation-1",
      sourceId: "source-1",
      chunkId: "chunk-1",
    },
    evidenceAction: "source_checked",
  });
  assert.equal(payload.citationId, "citation-1");
  assert.equal(payload.sourceId, "source-1");
  assert.equal(payload.chunkId, "chunk-1");
  assert.equal(payload.interactionId, "interaction-1");
});

test("answer citation labels link only to citations that exist", () => {
  assert.deepEqual(createCitationSegments("Apply within five days [2]. [9]", ["[1]", "[2]"]), [
    { text: "Apply within five days ", citationLabel: null },
    { text: "[2]", citationLabel: "[2]" },
    { text: ". ", citationLabel: null },
    { text: "[9]", citationLabel: null },
  ]);
  assert.equal(
    createCitationAnchorId("answer:one", "[2]"),
    "answer-answer-one-citation-2",
  );
});

test("Design Lab is development-only and has no study API path", async () => {
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
    assert.doesNotMatch(fixtureSource, /logStudyEvent|submitEvidenceUse/);
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

test("participant navigation exposes chat without study or admin entry points", async () => {
  const headerSource = await readFile(
    new URL("../components/layout/Header.tsx", import.meta.url),
    "utf8",
  );
  const footerSource = await readFile(
    new URL("../components/layout/Footer.tsx", import.meta.url),
    "utf8",
  );
  const heroSource = await readFile(
    new URL("../components/home/HeroSection.tsx", import.meta.url),
    "utf8",
  );
  for (const source of [headerSource, footerSource, heroSource]) {
    assert.doesNotMatch(source, /href="\/study"/);
    assert.doesNotMatch(source, /Study mode/);
  }
  assert.doesNotMatch(headerSource, /href: "\/admin"/);
  assert.doesNotMatch(footerSource, /href="\/admin"/);
  await assert.rejects(
    readFile(new URL("../app/study/page.tsx", import.meta.url), "utf8"),
    /ENOENT/,
  );
});

test("chat uses one full evidence presentation without experiment controls", async () => {
  const chatSource = await readFile(
    new URL("../components/chat/ChatShell.tsx", import.meta.url),
    "utf8",
  );
  const citationSource = await readFile(
    new URL("../components/chat/CitationCard.tsx", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(chatSource, /StudyConditionSwitcher|TrustCheckPanel/);
  assert.doesNotMatch(chatSource, /activeCondition|presentationPolicy/);
  assert.match(citationSource, /Section:/);
  assert.match(citationSource, /citation\.quotedText/);
  assert.doesNotMatch(citationSource, /Research score|relevanceScore/);
});

test("failed chat requests retain the question and expose retry", async () => {
  const chatSource = await readFile(
    new URL("../components/chat/ChatShell.tsx", import.meta.url),
    "utf8",
  );
  const inputSource = await readFile(
    new URL("../components/chat/QuestionInput.tsx", import.meta.url),
    "utf8",
  );
  assert.match(chatSource, /setFailedRequest\(\{ question, sensitiveWarningShown \}\)/);
  assert.match(chatSource, /failure\.retryable/);
  assert.match(chatSource, /retryFailedRequest/);
  assert.match(chatSource, />\s*Retry\s*</);
  assert.match(inputSource, /const completed = await onSubmit/);
  assert.match(inputSource, /if \(completed\)/);
  assert.doesNotMatch(chatSource, /setMessages\([^)]*mock/i);
});

test("answer statuses, counts, and section order remain explicit", async () => {
  const statusSource = await readFile(
    new URL("../components/ui/status.tsx", import.meta.url),
    "utf8",
  );
  const answerSource = await readFile(
    new URL("../components/chat/AnswerCard.tsx", import.meta.url),
    "utf8",
  );
  assert.match(statusSource, /Evidence found, personal review may be needed/);
  assert.match(
    statusSource,
    /normalized === "insufficient_evidence"[\s\S]+Insufficient evidence/,
  );
  assert.match(answerSource, /new Set\(/);
  assert.match(answerSource, /"evidence passage"/);
  assert.match(answerSource, /"policy file"/);
  assert.match(answerSource, /answer\.escalationRecommended/);
  assert.match(answerSource, /href={`#\${entry\.anchorId}`}/);
  assert.match(answerSource, /Jump to citation/);

  const sectionOrder = [
    "Direct answer",
    "Action steps",
    "Citations",
    "Limitations",
    "Contact university staff",
  ].map((heading) => answerSource.indexOf(heading));
  assert.ok(sectionOrder.every((index) => index >= 0));
  assert.deepEqual(sectionOrder, [...sectionOrder].sort((a, b) => a - b));
});

test("composer shows live AI and privacy boundaries beside the input", async () => {
  const chatSource = await readFile(
    new URL("../components/chat/ChatShell.tsx", import.meta.url),
    "utf8",
  );
  const inputSource = await readFile(
    new URL("../components/chat/QuestionInput.tsx", import.meta.url),
    "utf8",
  );
  assert.match(chatSource, /Answers are generated live by AI/);
  assert.match(chatSource, /not official university advice/);
  assert.match(inputSource, /Do not enter names, student numbers/);
  assert.match(inputSource, /general or researcher-provided policy question/);
  assert.doesNotMatch(inputSource, /study scenario/);
});

test("evidence viewer keeps source checking without embedded survey controls", async () => {
  const source = await readFile(
    new URL("../components/chat/EvidencePanel.tsx", import.meta.url),
    "utf8",
  );
  assert.match(source, /Mark as checked/);
  assert.match(source, /Open official source/);
  assert.doesNotMatch(source, /Evidence support rating/);
  assert.doesNotMatch(source, /Mark helpful|Mark confusing/);
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
  assert.match(cssSource, /prefers-reduced-motion: reduce/);
});

test("admin summaries hide full final decisions by default", async () => {
  const source = await readFile(
    new URL("../components/admin/AdminDashboard.tsx", import.meta.url),
    "utf8",
  );
  assert.match(source, /Show truncated decision preview/);
  assert.match(source, /response\.finalDecisionPreview/);
  assert.doesNotMatch(source, /response\.finalDecisionText/);
});

test("admin workbench exposes actionable preflight failures", async () => {
  const source = await readFile(
    new URL("../components/admin/AdminDashboard.tsx", import.meta.url),
    "utf8",
  );
  assert.match(source, /Pilot readiness/);
  assert.match(source, /failedChecks/);
  assert.match(source, /researcher_action/);
  assert.match(source, /Preflight unavailable/);
});

test("admin exports do not synthesize fallback research data", async () => {
  const source = await readFile(
    new URL("../components/admin/ExportButton.tsx", import.meta.url),
    "utf8",
  );
  assert.doesNotMatch(source, /mock|fallback/i);
  assert.match(source, /No file was created/);
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
  assert.match(cssSource, /\.admin-workbench \.admin-table-frame/);
  assert.match(cssSource, /max-width: 100%/);
});

test("admin route keeps legacy and workbench presentations", async () => {
  const source = await readFile(
    new URL("../app/admin/page.tsx", import.meta.url),
    "utf8",
  );
  assert.match(source, /<AdminDashboard workbench \/>/);
  assert.match(source, /<AdminDashboard \/>/);
});
