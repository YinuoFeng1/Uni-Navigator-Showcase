from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

StudyCondition = Literal[
    "A_SIMPLE_LINK",
    "B_SECTION",
    "C_HIGHLIGHT",
    "D_NEXT_STEP",
]

StudyEventType = Literal[
    "source_opened",
    "task_started",
    "question_submitted",
    "answer_received",
    "citation_clicked",
    "evidence_opened",
    "source_checked",
    "feedback_submitted",
    "task_completed",
    "trust_check_updated",
    "transcript_downloaded",
    "conversation_cleared",
    "final_response_submitted",
    "evidence_rating_submitted",
    "source_marked_helpful",
    "source_marked_confusing",
    "passage_viewed",
    "system_failure",
]

WouldContactStaff = Literal["yes", "no", "not_sure"]

EvidenceAction = Literal[
    "source_opened",
    "evidence_panel_opened",
    "citation_clicked",
    "source_checked",
    "passage_viewed",
    "evidence_rating_submitted",
    "source_marked_helpful",
    "source_marked_confusing",
]

RetrievalStatus = Literal[
    "grounded",
    "partial_evidence",
    "insufficient_evidence",
    "individual_assessment",
    "ambiguous",
]

ScopeDecisionValue = Literal[
    "in_scope",
    "possibly_in_scope",
    "out_of_scope",
    "ambiguous",
]


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=2000)
    sessionId: str | None = None
    participantLabel: str | None = None
    participantId: str | None = None
    taskId: str | None = None
    condition: StudyCondition = "C_HIGHLIGHT"
    sensitiveWarningShown: bool | None = None


class Citation(BaseModel):
    id: str
    citationId: str | None = None
    label: str | None = None
    sourceId: str | None = None
    chunkId: str
    title: str | None = None
    documentName: str | None = None
    documentTitle: str
    section: str | None = None
    sectionHeading: str | None = None
    pageNumber: int | None = None
    pageStart: int | None = None
    pageEnd: int | None = None
    passage: str | None = None
    quotedText: str
    surroundingText: str | None = None
    url: str | None = None
    sourceUrl: str | None = None
    score: float | None = None
    sourceType: str | None = None
    version: str | None = None
    effectiveDate: str | None = None
    relevanceScore: float | None = None


class ScopeDecisionResponse(BaseModel):
    decision: ScopeDecisionValue
    matchedTopics: list[str] = []
    supportingSourceIds: list[str] = []
    reasons: list[str] = []
    ruleSignals: list[str] = []
    retrievalSignals: dict[str, Any] = {}
    confidenceCategory: Literal["low", "medium", "high"]
    registryVersion: str
    escalationCategory: str


class AssistantAnswer(BaseModel):
    id: str
    interactionId: str | None = None
    answer: str
    shortAnswer: str
    basedOn: str
    evidenceSummary: str
    nextStep: str
    limitations: str
    uncertainty: str
    uncertaintyLevel: Literal["low", "medium", "high"]
    escalationRecommended: bool
    escalationCategory: str = "none"
    escalationReasons: list[str] = Field(default_factory=list)
    highStakesDetected: bool = False
    citations: list[Citation]
    retrievalStatus: RetrievalStatus | None = None
    escalationGuidance: str | None = None
    scopeDecision: ScopeDecisionResponse | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


class RetryableWrite(BaseModel):
    requestId: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{8,80}$")
    timestamp: str | None = None


class StudyEventRequest(RetryableWrite):
    sessionId: str | None = None
    participantLabel: str | None = None
    interactionId: str | None = None
    participantId: str | None = None
    taskId: str | None = None
    condition: StudyCondition | None = None
    eventType: StudyEventType
    timestamp: str | None = None
    metadata: dict[str, Any] | None = None


class StudyEventResponse(BaseModel):
    status: str
    eventId: str


class FeedbackRequest(RetryableWrite):
    sessionId: str | None = None
    participantLabel: str | None = None
    participantId: str | None = None
    taskId: str | None = None
    interactionId: str | None = None
    answerId: str
    rating: Literal["up", "down"]
    comment: str | None = None


class FeedbackResponse(BaseModel):
    status: str
    feedbackId: str


class StudySessionStartRequest(BaseModel):
    sessionId: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{8,80}$")
    roundId: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,39}$")
    participantLabel: str = Field(..., min_length=1, max_length=80)
    studyCondition: StudyCondition | None = None
    metadata: dict[str, Any] | None = None
    prototypeNoticeAcknowledged: bool | None = None


class StudySessionCompleteRequest(BaseModel):
    sessionId: str


class StudySessionResponse(BaseModel):
    roundId: str | None = None
    executionContext: str | None = None
    sessionId: str
    participantLabel: str
    studyCondition: str | None = None
    startedAt: str
    completedAt: str | None = None
    currentTaskId: str | None = None
    taskProgress: dict[str, Any] | None = None
    prototypeNoticeAcknowledged: bool | None = None
    prototypeNoticeAcknowledgedAt: str | None = None
    state: str | None = None
    releaseId: str | None = None
    releaseVersion: str | None = None
    conditionVersion: str | None = None


class StudyTaskResponse(BaseModel):
    taskId: str
    title: str
    scenario: str
    taskType: str
    difficulty: str
    expectedSafeBehaviour: str
    escalationExpected: bool
    active: bool
    notesForResearcher: str | None = None


class StudyTasksResponse(BaseModel):
    items: list[StudyTaskResponse]


class StudySessionTaskRequest(BaseModel):
    sessionId: str
    taskId: str
    preConfidence: int | None = Field(default=None, ge=1, le=5)


class StudySessionTaskResponse(BaseModel):
    sessionId: str
    taskId: str
    status: str
    eventId: str | None = None
    currentTaskId: str | None = None


class FinalTaskResponseRequest(BaseModel):
    sessionId: str
    taskId: str
    interactionId: str | None = None
    finalDecisionText: str = Field(..., min_length=1, max_length=4000)
    confidenceRating: int = Field(..., ge=1, le=5)
    wouldContactStaff: WouldContactStaff
    perceivedAnswerSupported: int = Field(..., ge=1, le=5)
    perceivedTaskDifficulty: int | None = Field(default=None, ge=1, le=5)
    notes: str | None = Field(default=None, max_length=2000)

    @field_validator("finalDecisionText")
    @classmethod
    def final_decision_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("finalDecisionText is required")
        return stripped

    @field_validator("notes")
    @classmethod
    def blank_notes_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class FinalTaskResponseResponse(BaseModel):
    responseId: str
    sessionId: str
    taskId: str
    createdAt: str


class EvidenceUseRequest(RetryableWrite):
    sessionId: str | None = None
    participantLabel: str | None = None
    taskId: str | None = None
    interactionId: str | None = None
    citationId: str | None = None
    sourceId: str | None = None
    chunkId: str | None = None
    evidenceAction: EvidenceAction
    evidenceRelevanceRating: int | None = Field(default=None, ge=1, le=5)
    evidenceSupportRating: int | None = Field(default=None, ge=1, le=5)
    userMarkedHelpful: bool | None = None
    userMarkedConfusing: bool | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("notes")
    @classmethod
    def blank_evidence_notes_to_none(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class EvidenceUseResponse(BaseModel):
    evidenceUseId: str
    createdAt: str


class TrustChecklistSnapshotRequest(BaseModel):
    sessionId: str | None = None
    participantLabel: str | None = None
    taskId: str | None = None
    interactionId: str | None = None
    answerClear: bool | None = None
    evidenceChecked: bool | None = None
    sourceSupportsAnswer: bool | None = None
    uncertaintyNoticed: bool | None = None
    wouldContactStaffIfNeeded: bool | None = None


class TrustChecklistSnapshotResponse(BaseModel):
    trustSnapshotId: str
    createdAt: str


class AdminLogItem(BaseModel):
    id: str
    sessionId: str | None = None
    participantLabel: str | None = None
    studyCondition: str | None = None
    participantId: str | None = None
    taskId: str | None = None
    taskTitle: str | None = None
    taskType: str | None = None
    taskDifficulty: str | None = None
    escalationExpected: bool | None = None
    condition: str
    question: str
    answerId: str
    shortAnswer: str
    fullAnswer: str | None = None
    basedOn: str | None = None
    limitations: str | None = None
    uncertainty: str | None = None
    escalationGuidance: str | None = None
    highStakesDetected: bool | None = None
    uncertaintyLevel: str
    escalationRecommended: bool
    escalationCategory: str | None = None
    escalationReasons: list[str] = Field(default_factory=list)
    citationCount: int
    retrievalStatus: str | None = None
    citationIds: list[str] = []
    citations: list[dict[str, Any]] = []
    sourceIds: list[str] = []
    retrievedChunkIds: list[str] = []
    retrievalTrace: list[dict[str, Any]] = []
    retrievedContextCount: int | None = None
    escalationGuidancePresent: bool | None = None
    sensitiveWarningShown: bool | None = None
    createdAt: str
    timeToFirstAnswerMs: int | None = None
    responseTimeMs: int | None = None
    errorType: str | None = None
    embeddingProvider: str | None = None
    embeddingModel: str | None = None
    embeddingDimension: int | None = None
    vectorCollection: str | None = None
    retrievalPartialThreshold: float | None = None
    retrievalGroundedThreshold: float | None = None
    retrievalTopK: int | None = None
    retrievalMode: str | None = None
    scopeDecision: str | None = None
    scopeRegistryVersion: str | None = None
    scopeRegistryFingerprint: str | None = None
    scopeMatchedTopics: list[str] = []
    corpusManifestFingerprint: str | None = None
    aiProvider: str | None = None
    aiModel: str | None = None
    aiModelRequested: str | None = None
    providerResponseModel: str | None = None
    providerResponseId: str | None = None
    inputTokens: int | None = None
    outputTokens: int | None = None
    totalTokens: int | None = None
    tokenUsage: dict[str, Any] = {}
    answerMode: str | None = None
    taskVersion: str | None = None
    appVersion: str | None = None
    appRevision: str | None = None
    executionContext: str | None = None
    answerStrategyVersion: str | None = None
    releaseId: str | None = None
    releaseVersion: str | None = None
    conditionId: str | None = None
    conditionVersion: str | None = None
    taskManifestVersion: str | None = None
    runtimeConfigFingerprint: str | None = None
    runtimeConfig: dict[str, Any] = {}
    promptTemplateVersion: str | None = None
    generationTemperature: float | None = None
    generationMaxTokens: int | None = None
    finalResponseId: str | None = None
    finalResponseSubmitted: bool = False
    finalDecisionLength: int | None = None
    confidenceRating: int | None = None
    wouldContactStaff: str | None = None
    perceivedAnswerSupported: int | None = None
    finalResponseCreatedAt: str | None = None
    evidenceUseCount: int = 0
    sourceCheckedCount: int = 0
    latestTrustAnswerClear: bool | None = None
    latestTrustEvidenceChecked: bool | None = None
    latestTrustSourceSupportsAnswer: bool | None = None
    latestTrustUncertaintyNoticed: bool | None = None
    latestTrustWouldContactStaffIfNeeded: bool | None = None


class AdminLogsResponse(BaseModel):
    items: list[AdminLogItem]


class AdminTrustChecklistSummary(BaseModel):
    trustSnapshotId: str | None = None
    answerClear: bool | None = None
    evidenceChecked: bool | None = None
    sourceSupportsAnswer: bool | None = None
    uncertaintyNoticed: bool | None = None
    wouldContactStaffIfNeeded: bool | None = None
    createdAt: str | None = None


class AdminSessionSummary(BaseModel):
    sessionId: str
    participantLabel: str
    studyCondition: str | None = None
    startedAt: str
    completedAt: str | None = None
    currentTaskId: str | None = None
    prototypeNoticeAcknowledged: bool | None = None
    tasksStartedCount: int
    tasksCompletedCount: int
    interactionCount: int
    evidenceUseCount: int
    sourceCheckedCount: int
    feedbackCount: int
    finalResponseCount: int
    sensitiveWarningShownCount: int = 0
    latestTrustChecklistSummary: AdminTrustChecklistSummary | None = None
    lastActivityAt: str


class AdminSessionsResponse(BaseModel):
    items: list[AdminSessionSummary]


class AdminInteractionSummary(BaseModel):
    interactionId: str
    taskId: str | None = None
    questionPreview: str
    answerPreview: str
    retrievalStatus: str | None = None
    highStakesDetected: bool | None = None
    sensitiveWarningShown: bool | None = None
    citationCount: int
    evidenceUseCount: int = 0
    sourceCheckedCount: int = 0
    createdAt: str


class AdminEvidenceUseSummary(BaseModel):
    evidenceAction: str
    count: int


class AdminFinalResponseSummary(BaseModel):
    responseId: str
    taskId: str
    interactionId: str | None = None
    finalDecisionLength: int
    finalDecisionPreview: str
    confidenceRating: int
    wouldContactStaff: str
    perceivedAnswerSupported: int
    createdAt: str


class AdminFeedbackSummary(BaseModel):
    feedbackId: str
    taskId: str | None = None
    interactionId: str | None = None
    rating: str
    commentLength: int
    createdAt: str


class AdminEventTimelineItem(BaseModel):
    eventId: str
    eventType: str
    taskId: str | None = None
    interactionId: str | None = None
    metadataKeys: list[str] = []
    createdAt: str


class AdminSessionDetail(BaseModel):
    summary: AdminSessionSummary
    taskProgress: dict[str, list[str]]
    interactions: list[AdminInteractionSummary]
    evidenceUseSummary: list[AdminEvidenceUseSummary]
    latestTrustChecklist: AdminTrustChecklistSummary | None = None
    finalResponses: list[AdminFinalResponseSummary]
    feedback: list[AdminFeedbackSummary]
    eventTimeline: list[AdminEventTimelineItem]


class AdminTaskSummary(BaseModel):
    taskId: str
    title: str
    taskType: str
    difficulty: str
    escalationExpected: bool
    sessionsStartedCount: int
    sessionsCompletedCount: int
    finalResponseCount: int
    averageConfidence: float | None = None
    contactStaffYesCount: int
    contactStaffNoCount: int
    contactStaffUnsureCount: int
    evidenceUseCount: int
    trustChecklistCount: int
    trustSnapshotCount: int


class AdminTasksResponse(BaseModel):
    items: list[AdminTaskSummary]
