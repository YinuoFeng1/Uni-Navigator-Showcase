"use client";

import { useEffect, useRef, useState } from "react";
import { ResearchWriteQueue } from "@/lib/researchWriteQueue.mjs";
import {
  endChatSession, getChatSession, saveResearchWrite, startChatSession, ResearchRequestError,
  type ResearchWriteKind, type StartChatSession,
} from "@/lib/researchSessionApi";
import type { ChatStudySession } from "@/lib/types";

const sessionKey = "uni-navigator-chat-session";
const startKey = "uni-navigator-session-start";

export function useResearchSession() {
  const [session, setSession] = useState<ChatStudySession | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(0);
  const [failed, setFailed] = useState(false);
  const queue = useRef<ResearchWriteQueue | null>(null);
  const feedbackWrites = useRef(new Map<string, { requestId: string; timestamp: string }>());

  async function restore() {
    setError("");
    if (process.env.NEXT_PUBLIC_CLOUD_DEMO === "true") {
      setReady(true);
      return;
    }
    try {
      const id = sessionStorage.getItem(sessionKey);
      const pendingStart = sessionStorage.getItem(startKey);
      const current = pendingStart ? await startChatSession(JSON.parse(pendingStart))
        : id ? await getChatSession(id) : null;
      if (current) {
        sessionStorage.setItem(sessionKey, current.sessionId);
        sessionStorage.removeItem(startKey);
      }
      setSession(current);
      setReady(true);
    } catch (cause) {
      if (cause instanceof ResearchRequestError && cause.status >= 400 && cause.status < 500 && !sessionStorage.getItem(sessionKey)) {
        sessionStorage.removeItem(startKey);
        setReady(true);
      }
      setError("Unable to restore the test session. Reconnect and retry.");
    }
  }

  useEffect(() => {
    try {
      queue.current = new ResearchWriteQueue({
        storage: sessionStorage,
        send: (item) => saveResearchWrite(item.kind, item.payload),
        onChange: (count, hasFailed) => { setPending(count); setFailed(hasFailed); },
      });
      setPending(queue.current.items.length);
      setFailed(queue.current.items.length > 0);
      void restore();
    } catch {
      setError("Browser storage is unavailable. Test recording cannot start.");
    }
  }, []);

  useEffect(() => {
    function warnBeforeLeaving(event: BeforeUnloadEvent) {
      if (pending || busy) event.preventDefault();
    }
    window.addEventListener("beforeunload", warnBeforeLeaving);
    return () => window.removeEventListener("beforeunload", warnBeforeLeaving);
  }, [pending, busy]);

  async function start(roundId: string, participantLabel: string, acknowledged: boolean) {
    if (busy || pending || session?.state === "active") return false;
    setBusy(true);
    setError("");
    try {
      const saved = sessionStorage.getItem(startKey);
      const input: StartChatSession = saved ? JSON.parse(saved) : {
        sessionId: crypto.randomUUID(), roundId, participantLabel,
        prototypeNoticeAcknowledged: acknowledged,
      };
      sessionStorage.setItem(startKey, JSON.stringify(input));
      const current = await startChatSession(input);
      sessionStorage.setItem(sessionKey, current.sessionId);
      sessionStorage.removeItem(startKey);
      setSession(current);
      feedbackWrites.current.clear();
      return true;
    } catch (cause) {
      if (cause instanceof ResearchRequestError && cause.status >= 400 && cause.status < 500) {
        sessionStorage.removeItem(startKey);
      } else {
        setReady(false);
      }
      setError(cause instanceof Error ? cause.message : "Test could not start. Retry.");
      return false;
    } finally { setBusy(false); }
  }

  async function end() {
    if (!session || busy) return;
    setBusy(true);
    setError("");
    try {
      await queue.current?.flush();
      if (queue.current?.items.length) throw new Error("Save pending activity before ending the test.");
      setSession(await endChatSession(session.sessionId));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Test could not end. Retry.");
    } finally { setBusy(false); }
  }

  async function write(kind: ResearchWriteKind, payload: Record<string, unknown>) {
    if (!queue.current || !ready || busy || session?.completedAt) {
      throw new Error("Test recording is not ready.");
    }
    const scoped = { ...payload, sessionId: session?.sessionId };
    const key = JSON.stringify(scoped);
    const receipt = (kind === "feedback" && feedbackWrites.current.get(key)) || {
      requestId: crypto.randomUUID(), timestamp: new Date().toISOString(),
    };
    if (kind === "feedback") feedbackWrites.current.set(key, receipt);
    try {
      await queue.current.enqueue({ kind, payload: { ...scoped, ...receipt } });
    } catch (cause) {
      setError("Activity could not be saved. Keep this tab open and retry saves before continuing.");
      throw cause;
    }
  }

  async function retry() {
    try {
      await queue.current?.flush();
      if (!queue.current?.items.length) setError("");
    } catch {
      setError("Browser storage is unavailable. Keep this tab open and restore storage before retrying.");
    }
  }

  return {
    session, ready, busy, error, pending, failed, start, end, write, restore,
    retry,
    blocked: !ready || busy || Boolean(session?.completedAt),
  };
}
