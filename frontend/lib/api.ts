import { mockAssistantAnswer } from "@/lib/mockData";
import { requiresFailClosed } from "@/lib/chatFailurePolicy.mjs";
import type {
  AdminCorpusStatus,
  AdminLogsResponse,
  AdminPilotPreflight,
  AdminSessionDetail,
  AdminSessionsResponse,
  AdminTasksResponse,
  AssistantAnswer,
  EvidenceUsePayload,
  EvidenceUseResult,
  FinalTaskResponsePayload,
  FinalTaskResponseResult,
  FeedbackPayload,
  StudySession,
  StudyCondition,
  StudyEventType,
  StudyTask,
  TrustChecklistSnapshotPayload,
  TrustChecklistSnapshotResult,
} from "@/lib/types";

export type ChatApiSource = "backend" | "mock-fallback";

export type ChatApiResult = {
  answer: AssistantAnswer;
  source: ChatApiSource;
};

export type SendChatMessageInput = {
  question: string;
  sessionId?: string;
  participantLabel?: string;
  participantId?: string;
  taskId?: string;
  condition: StudyCondition;
  sensitiveWarningShown?: boolean;
  studyMode?: "development" | "pilot";
  failClosed?: boolean;
};

export type LogStudyEventInput = {
  sessionId?: string;
  participantLabel?: string;
  interactionId?: string;
  participantId?: string;
  taskId?: string;
  condition?: StudyCondition;
  eventType: StudyEventType;
  metadata?: Record<string, unknown>;
};

export type StartStudySessionInput = {
  participantLabel: string;
  studyCondition?: StudyCondition;
  metadata?: Record<string, unknown>;
  prototypeNoticeAcknowledged?: boolean;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

const USE_BACKEND = process.env.NEXT_PUBLIC_USE_BACKEND !== "false";

export const STUDY_SYSTEM_UNAVAILABLE_MESSAGE =
  "The study system is temporarily unavailable. Please pause this task and notify the researcher.";

export class ChatSystemFailureError extends Error {
  interactionId?: string;
  failureCategory?: string;
  failureStage?: string;
  systemFailureLogged: boolean;

  constructor(options: {
    interactionId?: string;
    failureCategory?: string;
    failureStage?: string;
    systemFailureLogged?: boolean;
  } = {}) {
    super(STUDY_SYSTEM_UNAVAILABLE_MESSAGE);
    this.name = "ChatSystemFailureError";
    this.interactionId = options.interactionId;
    this.failureCategory = options.failureCategory;
    this.failureStage = options.failureStage;
    this.systemFailureLogged = options.systemFailureLogged ?? false;
  }
}

function createFallbackAnswer(question: string): AssistantAnswer {
  const shortAnswer = question.toLowerCase().includes("contact")
    ? "Mock fallback: the backend is currently unavailable, so this local answer is being shown. For personal, urgent, or unclear cases, contact Student Services."
    : "Mock fallback: the backend is currently unavailable, so this local demo answer is being shown.";

  return {
    ...mockAssistantAnswer,
    id: `mock_fallback_${Date.now()}`,
    answer: shortAnswer,
    shortAnswer,
    basedOn: "This fallback answer is not based on retrieved policy evidence.",
    uncertainty:
      "The backend is unavailable, so this answer should not be treated as source-backed.",
    retrievalStatus: "error_fallback",
    citations: [],
  };
}

export async function sendChatMessage(
  input: SendChatMessageInput,
): Promise<ChatApiResult> {
  const { failClosed = false, ...requestBody } = input;
  const mustFailClosed = requiresFailClosed({
    sessionId: input.sessionId,
    studyMode: input.studyMode,
    explicitFailClosed: failClosed,
  });
  if (!USE_BACKEND) {
    if (mustFailClosed) {
      throw new ChatSystemFailureError({ failureStage: "frontend_configuration" });
    }
    return {
      answer: createFallbackAnswer(input.question),
      source: "mock-fallback",
    };
  }

  try {
    const response = await fetch(`${API_BASE_URL}/api/chat`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      if (mustFailClosed) {
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
        });
      }
      throw new Error(`Backend returned ${response.status}`);
    }

    const answer = (await response.json()) as AssistantAnswer;

    return {
      answer,
      source: "backend",
    };
  } catch (error) {
    if (error instanceof ChatSystemFailureError) {
      throw error;
    }
    if (mustFailClosed) {
      throw new ChatSystemFailureError({ failureStage: "network" });
    }
    console.warn("Backend unavailable. Falling back to mock answer.", error);

    return {
      answer: createFallbackAnswer(input.question),
      source: "mock-fallback",
    };
  }
}

export async function getMockAnswer(question: string): Promise<AssistantAnswer> {
  await new Promise((resolve) => setTimeout(resolve, 650));
  return createFallbackAnswer(question);
}

export async function logStudyEvent(input: LogStudyEventInput) {
  if (!USE_BACKEND) return;

  try {
    await fetch(`${API_BASE_URL}/api/study/log-event`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        ...input,
        timestamp: new Date().toISOString(),
      }),
    });
  } catch (error) {
    console.warn("Failed to log study event", error);
  }
}

export async function startStudySession(
  input: StartStudySessionInput,
): Promise<StudySession> {
  const response = await fetch(`${API_BASE_URL}/api/study/session/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return (await response.json()) as StudySession;
}

export async function completeStudySession(sessionId: string): Promise<StudySession> {
  const response = await fetch(`${API_BASE_URL}/api/study/session/complete`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ sessionId }),
  });

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return (await response.json()) as StudySession;
}

export async function fetchStudyTasks(): Promise<StudyTask[]> {
  const response = await fetch(`${API_BASE_URL}/api/study/tasks`);

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  const data = (await response.json()) as { items: StudyTask[] };
  return data.items;
}

export async function startStudyTask(
  sessionId: string,
  taskId: string,
  preConfidence?: number,
): Promise<{ sessionId: string; taskId: string; status: string; currentTaskId?: string }> {
  const response = await fetch(`${API_BASE_URL}/api/study/session/task/start`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ sessionId, taskId, preConfidence }),
  });

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return response.json();
}

export async function completeStudyTask(
  sessionId: string,
  taskId: string,
): Promise<{ sessionId: string; taskId: string; status: string; currentTaskId?: string | null }> {
  const response = await fetch(`${API_BASE_URL}/api/study/session/task/complete`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ sessionId, taskId }),
  });

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return response.json();
}

export async function submitFinalTaskResponse(
  input: FinalTaskResponsePayload,
): Promise<FinalTaskResponseResult> {
  const response = await fetch(`${API_BASE_URL}/api/study/task/final-response`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return (await response.json()) as FinalTaskResponseResult;
}

export async function submitEvidenceUse(
  input: EvidenceUsePayload,
): Promise<EvidenceUseResult> {
  const response = await fetch(`${API_BASE_URL}/api/study/evidence-use`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return (await response.json()) as EvidenceUseResult;
}

export async function submitTrustChecklistSnapshot(
  input: TrustChecklistSnapshotPayload,
): Promise<TrustChecklistSnapshotResult> {
  const response = await fetch(`${API_BASE_URL}/api/study/trust-checklist`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(input),
  });

  if (!response.ok) {
    throw new Error(`Backend returned ${response.status}`);
  }

  return (await response.json()) as TrustChecklistSnapshotResult;
}

export async function submitFeedback(input: FeedbackPayload) {
  if (!USE_BACKEND) return;

  try {
    await fetch(`${API_BASE_URL}/api/study/feedback`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(input),
    });
  } catch (error) {
    console.warn("Failed to submit feedback", error);
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
  if (!USE_BACKEND) {
    throw new Error("Backend access is disabled");
  }

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
