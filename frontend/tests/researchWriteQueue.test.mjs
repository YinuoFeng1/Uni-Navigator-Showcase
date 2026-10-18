import assert from "node:assert/strict";
import test from "node:test";
import { ResearchWriteQueue } from "../lib/researchWriteQueue.mjs";

function storage() {
  const values = new Map();
  return { getItem: key => values.get(key), setItem: (key, value) => values.set(key, value) };
}
const item = (id) => ({ kind: "log-event", payload: { requestId: id, timestamp: "2026-09-22T10:00:00Z", sessionId: "session-1" } });

test("failed writes persist and retry with identical IDs, timestamps and session", async () => {
  const store = storage();
  const queue = new ResearchWriteQueue({ storage: store, send: async () => { throw Error("offline"); } });
  await assert.rejects(queue.enqueue(item("request1")));
  assert.equal(queue.items.length, 1);
  const sent = [];
  const restored = new ResearchWriteQueue({ storage: store, send: async value => sent.push(value) });
  await restored.flush();
  assert.deepEqual(sent, [item("request1")]);
  assert.equal(restored.items.length, 0);
  assert.equal(store.getItem(restored.key), "[]");
});

test("acknowledgement is required before saved state and concurrent writes drain in order", async () => {
  let release;
  const sent = [];
  const gate = new Promise(resolve => { release = resolve; });
  const queue = new ResearchWriteQueue({ storage: storage(), send: async value => { await gate; sent.push(value); } });
  const a = queue.enqueue(item("first"));
  const b = queue.enqueue(item("second"));
  assert.equal(queue.items.length, 2);
  release();
  await Promise.all([a, b]);
  assert.deepEqual(sent, [item("first"), item("second")]);
  assert.equal(queue.items.length, 0);
});

test("response loss retains the same operation for backend deduplication", async () => {
  let fail = true;
  const saved = new Set();
  const queue = new ResearchWriteQueue({ storage: storage(), send: async value => {
    saved.add(value.payload.requestId);
    if (fail) throw Error("response lost");
  } });
  await assert.rejects(queue.enqueue(item("same-id")));
  fail = false;
  await queue.enqueue(item("same-id"));
  assert.equal(saved.size, 1);
  assert.equal(queue.items.length, 0);
});

test("storage failure is visible and preserves in-memory data for retry", async () => {
  let storageFailed = true;
  let status;
  const sent = [];
  const queue = new ResearchWriteQueue({
    storage: { getItem: () => null, setItem: () => { if (storageFailed) throw Error("quota"); } },
    send: async value => sent.push(value),
    onChange: (count, failed) => { status = { count, failed }; },
  });
  await assert.rejects(queue.enqueue(item("quota-id")));
  assert.deepEqual(status, { count: 1, failed: true });
  assert.equal(sent.length, 0);
  storageFailed = false;
  await queue.flush();
  assert.deepEqual(sent, [item("quota-id")]);
  assert.deepEqual(status, { count: 0, failed: false });
});
