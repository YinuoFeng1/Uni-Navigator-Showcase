import assert from "node:assert/strict";
import test from "node:test";

import { requiresFailClosed } from "../lib/chatFailurePolicy.mjs";

test("session-bound development request remains fail-closed", () => {
  assert.equal(
    requiresFailClosed({
      sessionId: "session_formal",
      studyMode: "development",
      explicitFailClosed: false,
    }),
    true,
  );
});

test("pilot request remains fail-closed without a session", () => {
  assert.equal(requiresFailClosed({ studyMode: "pilot" }), true);
});

test("unbound development exploration may retain labelled fallback", () => {
  assert.equal(requiresFailClosed({ studyMode: "development" }), false);
});
