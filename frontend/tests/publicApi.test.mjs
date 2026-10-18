import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

async function loadApi(file, base) {
  const source = await readFile(new URL(`../lib/${file}`, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  });
  const urls = [];
  const exports = {};
  runInNewContext(outputText, {
    exports, process: { env: { NEXT_PUBLIC_API_BASE_URL: base } },
    URLSearchParams,
    fetch: async (url) => {
      urls.push(url);
      return { ok: true, json: async () => ({}), blob: async () => ({}) };
    },
  });
  return { api: exports, urls };
}

for (const base of ["", undefined, "https://api.example.test"]) {
  test(`chat and research requests use the configured origin: ${String(base)}`, async () => {
    const prefix = base ?? "http://localhost:8000";
    const chat = await loadApi("api.ts", base);
    await chat.api.sendChatMessage({ question: "How do I defer an exam?" });
    await chat.api.fetchAdminLogs();
    assert.deepEqual(chat.urls, [`${prefix}/api/chat`, `${prefix}/api/admin/logs`]);
    const research = await loadApi("researchSessionApi.ts", base);
    await research.api.startChatSession({ roundId: "test", participantLabel: "P01" });
    await research.api.exportResearch("answers", {});
    assert.deepEqual(research.urls, [
      `${prefix}/api/study/session/start`, `${prefix}/api/admin/research/export/answers.csv?`,
    ]);
  });
}
