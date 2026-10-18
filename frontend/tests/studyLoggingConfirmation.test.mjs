import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("study event and feedback writes reject non-success responses", async () => {
  const apiSource = await readFile(new URL("../lib/researchSessionApi.ts", import.meta.url), "utf8");
  assert.match(apiSource, /if \(!response\.ok\)/);
  assert.match(apiSource, /throw new ResearchRequestError\(message, response\.status\)/);
  assert.match(apiSource, /\/api\/study\/\$\{kind\}/);
});

test("feedback UI reports saved only after the backend confirms the write", async () => {
  const widgetSource = await readFile(
    new URL("../components/chat/FeedbackWidget.tsx", import.meta.url),
    "utf8",
  );

  assert.match(widgetSource, /await onFeedbackSubmit/);
  assert.match(widgetSource, /setSubmitted\(true\)/);
  assert.match(widgetSource, /Feedback was not saved/);
  assert.match(widgetSource, /Retry feedback/);
});

test("logging failures are shown without claiming the activity was saved", async () => {
  const chatSource = await readFile(
    new URL("../components/chat/ChatShell.tsx", import.meta.url),
    "utf8",
  );

  const sessionBar = await readFile(new URL("../components/chat/ResearchSessionBar.tsx", import.meta.url), "utf8");
  const sessionHook = await readFile(new URL("../components/chat/useResearchSession.ts", import.meta.url), "utf8");
  assert.match(chatSource, /ResearchSessionBar research=\{research\}/);
  assert.match(sessionBar, /research\.pending > 0/);
  assert.match(sessionBar, /Retry saves/);
  assert.match(sessionBar, /active && research\.pending === 0/);
  assert.match(sessionHook, /Activity could not be saved/);
});
