export type Citation = {
  id: string;
  citationId?: string;
  label?: string;
  sourceId?: string;
  chunkId?: string;
  title?: string;
  documentName?: string;
  documentTitle: string;
  section?: string;
  sectionHeading?: string;
  pageNumber?: number;
  pageStart?: number;
  pageEnd?: number;
  passage?: string;
  quotedText: string;
  surroundingText?: string;
  url?: string;
  sourceUrl?: string;
  score?: number;
  sourceType?: string;
  version?: string;
  effectiveDate?: string;
  relevanceScore?: number;
};

export type AssistantAnswer = {
  id: string;
  interactionId?: string;
  answer?: string;
  shortAnswer: string;
  basedOn?: string;
  evidenceSummary: string;
  nextStep: string;
  limitations: string;
  uncertainty?: string;
  uncertaintyLevel: "low" | "medium" | "high";
  escalationRecommended: boolean;
  escalationCategory: string;
  escalationReasons: string[];
  highStakesDetected?: boolean;
  citations: Citation[];
  retrievalStatus?: string;
  escalationGuidance?: string;
  scopeDecision?: {
    decision: "in_scope" | "possibly_in_scope" | "out_of_scope" | "ambiguous";
    matchedTopics: string[];
    supportingSourceIds: string[];
    reasons: string[];
    ruleSignals: string[];
    retrievalSignals: Record<string, unknown>;
    confidenceCategory: "low" | "medium" | "high";
    registryVersion: string;
    escalationCategory: string;
  };
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  answer?: AssistantAnswer;
  createdAt: string;
};

export type FeedbackPayload = {
  requestId?: string;
  timestamp?: string;
  sessionId?: string;
  participantLabel?: string;
  participantId?: string;
  taskId?: string;
  interactionId?: string;
  answerId: string;
  rating: "up" | "down";
  comment?: string;
};

export type EvidenceUseAction =
  | "source_opened"
  | "evidence_panel_opened"
  | "citation_clicked"
  | "source_checked"
  | "passage_viewed"
  | "evidence_rating_submitted"
  | "source_marked_helpful"
  | "source_marked_confusing";

export type StudyEventType =
  | "source_opened"
  | "task_started"
  | "question_submitted"
  | "answer_received"
  | "citation_clicked"
  | "evidence_opened"
  | "source_checked"
  | "feedback_submitted"
  | "task_completed"
  | "trust_check_updated"
  | "transcript_downloaded"
  | "conversation_cleared"
  | "final_response_submitted"
  | "evidence_rating_submitted"
  | "source_marked_helpful"
  | "source_marked_confusing"
  | "passage_viewed"
  | "system_failure";

export type AdminLogItem = {
  id: string;
  sessionId?: string;
  participantLabel?: string;
  studyCondition?: string;
  participantId?: string;
  taskId?: string;
  taskTitle?: string;
  taskType?: string;
  taskDifficulty?: string;
  escalationExpected?: boolean;
  condition: string;
  question: string;
  answerId: string;
  shortAnswer: string;
  fullAnswer?: string;
  basedOn?: string;
  limitations?: string;
  uncertainty?: string;
  escalationGuidance?: string;
  highStakesDetected?: boolean;
  uncertaintyLevel: "low" | "medium" | "high" | string;
  escalationRecommended: boolean;
  escalationCategory?: string;
  escalationReasons?: string[];
  citationCount: number;
  retrievalStatus?: string;
  citationIds: string[];
  citations?: Array<Record<string, unknown>>;
  sourceIds: string[];
  retrievedChunkIds: string[];
  retrievalTrace?: Array<Record<string, unknown>>;
  retrievedContextCount?: number;
  escalationGuidancePresent?: boolean;
  sensitiveWarningShown?: boolean;
  createdAt: string;
  timeToFirstAnswerMs?: number;
  responseTimeMs?: number;
  errorType?: string;
  embeddingProvider?: string;
  embeddingModel?: string;
  embeddingDimension?: number;
  vectorCollection?: string;
  retrievalPartialThreshold?: number;
  retrievalGroundedThreshold?: number;
  retrievalTopK?: number;
  retrievalMode?: string;
  scopeDecision?: string;
  scopeRegistryVersion?: string;
  scopeRegistryFingerprint?: string;
  scopeMatchedTopics?: string[];
  corpusManifestFingerprint?: string;
  aiProvider?: string;
  aiModel?: string;
  aiModelRequested?: string;
  providerResponseModel?: string;
  providerResponseId?: string;
  inputTokens?: number;
  outputTokens?: number;
  totalTokens?: number;
  tokenUsage?: Record<string, unknown>;
  answerMode?: string;
  taskVersion?: string;
  appVersion?: string;
  appRevision?: string;
  executionContext?: string;
  answerStrategyVersion?: string;
  releaseId?: string;
  releaseVersion?: string;
  conditionId?: string;
  conditionVersion?: string;
  taskManifestVersion?: string;
  runtimeConfigFingerprint?: string;
  runtimeConfig?: Record<string, unknown>;
  promptTemplateVersion?: string;
  generationTemperature?: number;
  generationMaxTokens?: number;
  finalResponseId?: string;
  finalResponseSubmitted?: boolean;
  finalDecisionLength?: number;
  confidenceRating?: number;
  wouldContactStaff?: string;
  perceivedAnswerSupported?: number;
  finalResponseCreatedAt?: string;
  evidenceUseCount?: number;
  sourceCheckedCount?: number;
  latestTrustAnswerClear?: boolean;
  latestTrustEvidenceChecked?: boolean;
  latestTrustSourceSupportsAnswer?: boolean;
  latestTrustUncertaintyNoticed?: boolean;
  latestTrustWouldContactStaffIfNeeded?: boolean;
};

export type AdminLogsResponse = {
  items: AdminLogItem[];
};

export type AdminTrustChecklistSummary = {
  trustSnapshotId?: string | null;
  answerClear?: boolean | null;
  evidenceChecked?: boolean | null;
  sourceSupportsAnswer?: boolean | null;
  uncertaintyNoticed?: boolean | null;
  wouldContactStaffIfNeeded?: boolean | null;
  createdAt?: string | null;
};

export type AdminSessionSummary = {
  sessionId: string;
  participantLabel: string;
  studyCondition?: string | null;
  startedAt: string;
  completedAt?: string | null;
  currentTaskId?: string | null;
  prototypeNoticeAcknowledged?: boolean | null;
  tasksStartedCount: number;
  tasksCompletedCount: number;
  interactionCount: number;
  evidenceUseCount: number;
  sourceCheckedCount: number;
  feedbackCount: number;
  finalResponseCount: number;
  sensitiveWarningShownCount?: number;
  latestTrustChecklistSummary?: AdminTrustChecklistSummary | null;
  lastActivityAt: string;
};

export type AdminSessionsResponse = {
  items: AdminSessionSummary[];
};

export type AdminInteractionSummary = {
  interactionId: string;
  taskId?: string | null;
  questionPreview: string;
  answerPreview: string;
  retrievalStatus?: string | null;
  highStakesDetected?: boolean | null;
  sensitiveWarningShown?: boolean | null;
  citationCount: number;
  evidenceUseCount: number;
  sourceCheckedCount: number;
  createdAt: string;
};

export type AdminEvidenceUseSummary = {
  evidenceAction: string;
  count: number;
};

export type AdminFinalResponseSummary = {
  responseId: string;
  taskId: string;
  interactionId?: string | null;
  finalDecisionLength: number;
  finalDecisionPreview: string;
  confidenceRating: number;
  wouldContactStaff: string;
  perceivedAnswerSupported: number;
  createdAt: string;
};

export type AdminFeedbackSummary = {
  feedbackId: string;
  taskId?: string | null;
  interactionId?: string | null;
  rating: string;
  commentLength: number;
  createdAt: string;
};

export type AdminEventTimelineItem = {
  eventId: string;
  eventType: string;
  taskId?: string | null;
  interactionId?: string | null;
  metadataKeys: string[];
  createdAt: string;
};

export type AdminSessionDetail = {
  summary: AdminSessionSummary;
  taskProgress: {
    startedTaskIds: string[];
    completedTaskIds: string[];
  };
  interactions: AdminInteractionSummary[];
  evidenceUseSummary: AdminEvidenceUseSummary[];
  latestTrustChecklist?: AdminTrustChecklistSummary | null;
  finalResponses: AdminFinalResponseSummary[];
  feedback: AdminFeedbackSummary[];
  eventTimeline: AdminEventTimelineItem[];
};

export type AdminTaskSummary = {
  taskId: string;
  title: string;
  taskType: string;
  difficulty: string;
  escalationExpected: boolean;
  sessionsStartedCount: number;
  sessionsCompletedCount: number;
  finalResponseCount: number;
  averageConfidence?: number | null;
  contactStaffYesCount: number;
  contactStaffNoCount: number;
  contactStaffUnsureCount: number;
  evidenceUseCount: number;
  trustChecklistCount: number;
  trustSnapshotCount: number;
};

export type AdminTasksResponse = {
  items: AdminTaskSummary[];
};

export type AdminCorpusStatus = {
  vectorStoreProviderRequested?: string;
  vectorStoreProviderActive?: string;
  vectorStoreCollection?: string;
  fallbackUsed?: boolean;
  chromaAvailable?: boolean;
  embeddingProvider?: string;
  embeddingModel?: string;
  sourceCount?: number;
  chunkCount?: number;
};

export type AdminPreflightCheck = {
  check_id?: string;
  checkId?: string;
  check?: string;
  status: string;
  severity?: string;
  message?: string;
  detail?: string;
  safe_detail?: string;
  safeDetail?: string;
  researcher_action?: string;
  researcherAction?: string;
};

export type AdminPilotPreflight = {
  ok: boolean;
  checks: AdminPreflightCheck[];
};

export type EvidenceUsePayload = {
  sessionId?: string;
  requestId?: string;
  timestamp?: string;
  interactionId?: string;
  citationId?: string;
  sourceId?: string;
  chunkId?: string;
  evidenceAction: EvidenceUseAction;
};

export type EvidenceUseResult = {
  evidenceUseId: string;
  createdAt: string;
};

export type ChatStudySession = {
  sessionId: string;
  participantLabel: string;
  roundId: string | null;
  executionContext: string | null;
  startedAt: string;
  completedAt: string | null;
  state: string;
};

export type ResearchSessionSummary = {
  round_id: string;
  participant_code: string;
  session_id: string;
  execution_context: string;
  started_at: string;
  completed_at: string;
  state: string;
  duration_seconds: number | "";
  question_count: number;
  answer_count: number;
  citation_click_count: number;
  evidence_open_count: number;
  source_open_count: number;
  source_checked_count: number;
  feedback_count: number;
  error_count: number;
};
