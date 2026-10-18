import type {
  AdminCorpusStatus,
  AdminLogsResponse,
  AdminPilotPreflight,
  AdminSessionDetail,
  AdminSessionsResponse,
  AdminTasksResponse,
  AssistantAnswer,
} from "@/lib/types";

export type SendChatMessageInput = {
  sessionId?: string;
  question: string;
  sensitiveWarningShown?: boolean;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const CHAT_SYSTEM_UNAVAILABLE_MESSAGE =
  "The system is temporarily unavailable. Please try again or notify the researcher.";
export const CHAT_REQUEST_RETRY_MESSAGE =
  "The request did not complete. Your question has been kept so you can try again.";

export class ChatSystemFailureError extends Error {
  interactionId?: string;
  failureCategory?: string;
  failureStage?: string;
  systemFailureLogged: boolean;
  retryable: boolean;
  taskBlocked: boolean;

  constructor(options: {
    interactionId?: string;
    failureCategory?: string;
    failureStage?: string;
    systemFailureLogged?: boolean;
    retryable?: boolean;
    taskBlocked?: boolean;
  } = {}) {
    super(CHAT_SYSTEM_UNAVAILABLE_MESSAGE);
    this.name = "ChatSystemFailureError";
    this.interactionId = options.interactionId;
    this.failureCategory = options.failureCategory;
    this.failureStage = options.failureStage;
    this.systemFailureLogged = options.systemFailureLogged ?? false;
    this.retryable = options.retryable ?? false;
    this.taskBlocked = options.taskBlocked ?? false;
  }
}

export async function sendChatMessage(
  input: SendChatMessageInput,
): Promise<AssistantAnswer> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(input),
    });

    if (!response.ok) {
      let detail: Record<string, unknown> = {};
      try {
        const payload = (await response.json()) as {
          detail?: Record<string, unknown>;
        };
        detail = payload.detail ?? {};
      } catch {
        detail = {};
      }
      throw new ChatSystemFailureError({
        interactionId:
          typeof detail.interactionId === "string"
            ? detail.interactionId
            : undefined,
        failureCategory:
          typeof detail.failureCategory === "string"
            ? detail.failureCategory
            : undefined,
        failureStage:
          typeof detail.failureStage === "string"
            ? detail.failureStage
            : undefined,
        systemFailureLogged: detail.systemFailureLogged === true,
        retryable: detail.retryable === true,
        taskBlocked: detail.taskBlocked === true,
      });
    }

    return (await response.json()) as AssistantAnswer;
  } catch (error) {
    if (error instanceof ChatSystemFailureError) {
      throw error;
    }
    throw new ChatSystemFailureError({
      failureStage: "network",
      retryable: true,
    });
  }
}

export async function fetchAdminLogs(): Promise<AdminLogsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/admin/logs`);

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return (await response.json()) as AdminLogsResponse;
}

export async function fetchAdminSessions(): Promise<AdminSessionsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/admin/sessions`);

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return (await response.json()) as AdminSessionsResponse;
}

export async function fetchAdminSessionDetail(
  sessionId: string,
): Promise<AdminSessionDetail> {
  const response = await fetch(`${API_BASE_URL}/api/admin/sessions/${sessionId}`);

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return (await response.json()) as AdminSessionDetail;
}

export async function fetchAdminTasks(): Promise<AdminTasksResponse> {
  const response = await fetch(`${API_BASE_URL}/api/admin/tasks`);

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return (await response.json()) as AdminTasksResponse;
}

export async function fetchAdminCorpusStatus(): Promise<AdminCorpusStatus> {
  const response = await fetch(`${API_BASE_URL}/api/admin/corpus/status`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Admin corpus request failed with ${response.status}`);
  }
  return (await response.json()) as AdminCorpusStatus;
}

export async function fetchAdminPilotPreflight(): Promise<AdminPilotPreflight> {
  const response = await fetch(`${API_BASE_URL}/api/admin/pilot/preflight`, {
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Admin preflight request failed with ${response.status}`);
  }
  return (await response.json()) as AdminPilotPreflight;
}

async function downloadAdminCsv(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`);

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return response.blob();
}

export async function downloadAdminLogsCsv(): Promise<Blob> {
  return downloadAdminCsv("/api/admin/logs/export.csv");
}

export async function downloadAdminSessionSummaryCsv(): Promise<Blob> {
  return downloadAdminCsv("/api/admin/export/session-summary.csv");
}

export async function downloadAdminTaskSummaryCsv(): Promise<Blob> {
  return downloadAdminCsv("/api/admin/export/task-summary.csv");
}
