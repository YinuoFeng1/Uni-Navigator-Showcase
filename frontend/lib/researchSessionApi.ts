import type { ChatStudySession, ResearchSessionSummary } from "@/lib/types";

const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ResearchRequestError extends Error {
  constructor(message: string, public status: number) { super(message); }
}

async function request<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${base}${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: { "Content-Type": "application/json" },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    cache: "no-store",
  });
  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    const data = await response.json().catch(() => null);
    if (typeof data?.detail === "string") message = data.detail;
    throw new ResearchRequestError(message, response.status);
  }
  return response.json() as Promise<T>;
}

export type StartChatSession = {
  sessionId: string;
  roundId: string;
  participantLabel: string;
  prototypeNoticeAcknowledged: boolean;
};
export const startChatSession = (input: StartChatSession) =>
  request<ChatStudySession>("/api/study/session/start", input);
export const getChatSession = (id: string) =>
  request<ChatStudySession>(`/api/study/session/${encodeURIComponent(id)}`);
export const endChatSession = (sessionId: string) =>
  request<ChatStudySession>("/api/study/session/complete", { sessionId });

export type ResearchWriteKind = "log-event" | "evidence-use" | "feedback";
export const saveResearchWrite = (kind: ResearchWriteKind, payload: Record<string, unknown>) =>
  request<unknown>(`/api/study/${kind}`, payload);

export type ResearchFilters = { round_id?: string; participant?: string };
function query(filters: ResearchFilters) {
  return new URLSearchParams(Object.entries(filters).filter((entry): entry is [string, string] => Boolean(entry[1]))).toString();
}
export const listResearchSessions = (filters: ResearchFilters = {}) =>
  request<{ items: ResearchSessionSummary[] }>(`/api/admin/research/sessions?${query(filters)}`);
export async function exportResearch(kind: "participants" | "timeline" | "answers", filters: ResearchFilters) {
  const response = await fetch(`${base}/api/admin/research/export/${kind}.csv?${query(filters)}`, { cache: "no-store" });
  if (!response.ok) throw new Error("Export failed. Check the backend and retry.");
  return response.blob();
}
