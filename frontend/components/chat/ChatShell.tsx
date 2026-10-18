"use client";

import { useMemo, useState } from "react";
import { CheckCircle2, Info, Loader2, ShieldCheck } from "lucide-react";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { EvidencePanel } from "@/components/chat/EvidencePanel";
import { QuestionInput } from "@/components/chat/QuestionInput";
import { SuggestedQuestions } from "@/components/chat/SuggestedQuestions";
import { TranscriptActions } from "@/components/chat/TranscriptActions";
import {
  TrustCheckPanel,
  type TrustChecklistState,
} from "@/components/chat/TrustCheckPanel";
import { StudyConditionSwitcher } from "@/components/study/StudyConditionSwitcher";
import { Badge } from "@/components/ui/badge";
import {
  BlockingFailurePanel,
  LoadingIndicator,
  SystemStatusBar,
} from "@/components/ui/status";
import {
  ChatSystemFailureError,
  STUDY_SYSTEM_UNAVAILABLE_MESSAGE,
  logStudyEvent,
  sendChatMessage,
  submitEvidenceUse,
  submitFeedback as submitFeedbackToBackend,
  submitTrustChecklistSnapshot,
  type ChatApiSource,
} from "@/lib/api";
import { defaultCondition } from "@/lib/constants";
import { createEvidenceUsePayload } from "@/lib/evidencePayload.mjs";
import { getPresentationPolicy } from "@/lib/presentationPolicy.mjs";
import type {
  ChatMessage as ChatMessageType,
  Citation,
  EvidenceUseAction,
  FeedbackPayload,
  StudyCondition,
  StudyEvent,
} from "@/lib/types";
import { cn } from "@/lib/utils";

type ChatShellProps = {
  condition?: StudyCondition;
  onConditionChange?: (condition: StudyCondition) => void;
  onEvent?: (event: Omit<StudyEvent, "timestamp" | "condition">) => void;
  sessionId?: string;
  participantLabel?: string;
  participantId?: string;
  taskId?: string;
  showSidebar?: boolean;
  showSuggestedQuestions?: boolean;
  showTranscriptActions?: boolean;
  interactionDisabled?: boolean;
  failClosed?: boolean;
  disabledReason?: string;
  className?: string;
  workbench?: boolean;
  taskTitle?: string;
};

type StudyEventInput = Omit<StudyEvent, "timestamp" | "condition">;

const assistantIntro: ChatMessageType = {
  id: "assistant_intro",
  role: "assistant",
  content:
    "Ask one university policy question at a time. I will show the evidence used and suggest when staff contact is safer.",
  createdAt: new Date().toISOString(),
};

export function ChatShell({
  condition,
  onConditionChange,
  onEvent,
  sessionId,
  participantLabel,
  participantId,
  taskId,
  showSidebar = true,
  showSuggestedQuestions = true,
  showTranscriptActions = true,
  interactionDisabled = false,
  failClosed = false,
  disabledReason,
  className,
  workbench = false,
  taskTitle,
}: ChatShellProps) {
  const [internalCondition, setInternalCondition] =
    useState<StudyCondition>(defaultCondition);
  const [messages, setMessages] = useState<ChatMessageType[]>([assistantIntro]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [checkedCitationIds, setCheckedCitationIds] = useState<string[]>([]);
  const [evidenceSupportRatings, setEvidenceSupportRatings] = useState<
    Record<string, number>
  >({});
  const [helpfulCitationIds, setHelpfulCitationIds] = useState<string[]>([]);
  const [confusingCitationIds, setConfusingCitationIds] = useState<string[]>([]);
  const [apiSource, setApiSource] = useState<ChatApiSource | null>(null);
  const [lastInteractionId, setLastInteractionId] = useState<string | undefined>();
  const [systemFailure, setSystemFailure] = useState(false);
  const [failureCorrelationId, setFailureCorrelationId] = useState<string>();

  const activeCondition = condition ?? internalCondition;
  const presentationPolicy = getPresentationPolicy(activeCondition);

  const allCitations = useMemo(
    () => messages.flatMap((message) => message.answer?.citations ?? []),
    [messages],
  );
  const visibleMessages = useMemo(() => [...messages].reverse(), [messages]);

  function emit(event: StudyEventInput, options: { remote?: boolean } = {}) {
    const normalized = {
      ...event,
      sessionId: event.sessionId ?? sessionId,
      participantLabel: event.participantLabel ?? participantLabel,
      participantId: event.participantId ?? participantId,
      taskId: event.taskId ?? taskId,
    };
    const shouldLogRemote = options.remote ?? true;

    onEvent?.(normalized);
    if (shouldLogRemote) {
      void logStudyEvent({
        ...normalized,
        condition: activeCondition,
      });
    }
  }

  function getCitationContext(citationId: string) {
    for (const message of messages) {
      const citation = message.answer?.citations.find((item) => item.id === citationId);
      if (citation && message.answer) {
        return { citation, answer: message.answer };
      }
    }
    return null;
  }

  function getCitationKey(citation: Citation) {
    return citation.citationId || citation.id;
  }

  function recordEvidenceUse(
    evidenceAction: EvidenceUseAction,
    citation: Citation | null,
    interactionId?: string,
    extras: {
      evidenceSupportRating?: number;
      evidenceRelevanceRating?: number;
      userMarkedHelpful?: boolean;
      userMarkedConfusing?: boolean;
      notes?: string;
    } = {},
  ) {
    if (!presentationPolicy.evidencePanelAvailable) return;
    void submitEvidenceUse(createEvidenceUsePayload({
      sessionId,
      participantLabel,
      taskId,
      interactionId,
      citation,
      evidenceAction,
      extras,
    })).catch((error) => {
      console.warn("Failed to log evidence-use event", error);
    });
  }

  function handleConditionChange(nextCondition: StudyCondition) {
    setInternalCondition(nextCondition);
    onConditionChange?.(nextCondition);
  }

  async function submitQuestion(question: string, sensitiveWarningShown = false) {
    if (interactionDisabled || systemFailure || isLoading) return;

    const userMessage: ChatMessageType = {
      id: `user_${Date.now()}`,
      role: "user",
      content: question,
      createdAt: new Date().toISOString(),
    };

    setMessages((current) => [...current, userMessage]);
    setIsLoading(true);
    emit({
      participantId,
      taskId,
      eventType: "question_submitted",
      metadata: { questionLength: question.length, sensitiveWarningShown },
    });

    try {
      const result = await sendChatMessage({
        question,
        sessionId,
        participantLabel,
        participantId,
        taskId,
        condition: activeCondition,
        sensitiveWarningShown,
        studyMode: failClosed ? "pilot" : "development",
        failClosed,
      });
      const answer = result.answer;
      setApiSource(result.source);
      setLastInteractionId(answer.interactionId);

      const assistantMessage: ChatMessageType = {
        id: `assistant_${Date.now()}`,
        role: "assistant",
        content: answer.shortAnswer,
        answer,
        createdAt: new Date().toISOString(),
      };

      setMessages((current) => [...current, assistantMessage]);
      emit({
        interactionId: answer.interactionId,
        participantId,
        taskId,
        eventType: "answer_received",
        metadata: {
          answerId: answer.id,
          citationCount: answer.citations.length,
          uncertaintyLevel: answer.uncertaintyLevel,
          escalationRecommended: answer.escalationRecommended,
          scopeDecision: answer.scopeDecision?.decision,
          apiSource: result.source,
        },
      });
    } catch (error) {
      const failure =
        error instanceof ChatSystemFailureError
          ? error
          : new ChatSystemFailureError({ failureStage: "frontend" });
      setSystemFailure(true);
      setLastInteractionId(undefined);
      setFailureCorrelationId(failure.interactionId);
      emit(
        {
          interactionId: failure.interactionId,
          participantId,
          taskId,
          eventType: "system_failure",
          metadata: {
            failureCategory: failure.failureCategory ?? "frontend_unavailable",
            failureStage: failure.failureStage ?? "frontend",
            participantVisibleActionTaken:
              "task_paused_researcher_notification_requested",
          },
        },
        { remote: !failure.systemFailureLogged },
      );
    } finally {
      setIsLoading(false);
    }
  }

  function openEvidence(citationId: string) {
    if (!presentationPolicy.evidencePanelAvailable) return;
    const citation = allCitations.find((item) => item.id === citationId) ?? null;
    const context = getCitationContext(citationId);
    setActiveCitation(citation);
    setEvidenceOpen(true);
    emit({
      interactionId: context?.answer.interactionId,
      participantId,
      taskId,
      eventType: "evidence_opened",
      metadata: {
        citationId,
        chunkId: context?.citation.chunkId,
        answerId: context?.answer.id,
      },
    }, { remote: false });
    recordEvidenceUse(
      "evidence_panel_opened",
      context?.citation ?? citation,
      context?.answer.interactionId,
    );
  }

  function clickCitation(citationId: string) {
    const context = getCitationContext(citationId);
    emit({
      interactionId: context?.answer.interactionId,
      participantId,
      taskId,
      eventType: "citation_clicked",
      metadata: {
        citationId,
        chunkId: context?.citation.chunkId,
        answerId: context?.answer.id,
      },
    }, { remote: false });
    recordEvidenceUse(
      "citation_clicked",
      context?.citation ?? null,
      context?.answer.interactionId,
    );
  }

  function markChecked() {
    if (!activeCitation) return;
    const context = getCitationContext(activeCitation.id);
    const citationKey = getCitationKey(activeCitation);
    setCheckedCitationIds((current) =>
      current.includes(citationKey) ? current : [...current, citationKey],
    );
    emit({
      interactionId: context?.answer.interactionId,
      participantId,
      taskId,
      eventType: "source_checked",
      metadata: {
        citationId: citationKey,
        chunkId: activeCitation.chunkId,
        answerId: context?.answer.id,
      },
    }, { remote: false });
    recordEvidenceUse("source_checked", activeCitation, context?.answer.interactionId);
  }

  function rateActiveEvidence(rating: number) {
    if (!activeCitation) return;
    const citationKey = getCitationKey(activeCitation);
    const context = getCitationContext(activeCitation.id);
    setEvidenceSupportRatings((current) => ({
      ...current,
      [citationKey]: rating,
    }));
    recordEvidenceUse(
      "evidence_rating_submitted",
      activeCitation,
      context?.answer.interactionId,
      { evidenceSupportRating: rating },
    );
    emit(
      {
        interactionId: context?.answer.interactionId,
        participantId,
        taskId,
        eventType: "evidence_rating_submitted",
        metadata: {
          citationId: citationKey,
          chunkId: activeCitation.chunkId,
          evidenceSupportRating: rating,
          answerId: context?.answer.id,
        },
      },
      { remote: false },
    );
  }

  function markActiveEvidenceHelpful(value: boolean) {
    if (!activeCitation) return;
    const citationKey = getCitationKey(activeCitation);
    const context = getCitationContext(activeCitation.id);
    setHelpfulCitationIds((current) =>
      value
        ? current.includes(citationKey)
          ? current
          : [...current, citationKey]
        : current.filter((item) => item !== citationKey),
    );
    recordEvidenceUse(
      "source_marked_helpful",
      activeCitation,
      context?.answer.interactionId,
      { userMarkedHelpful: value },
    );
    emit(
      {
        interactionId: context?.answer.interactionId,
        participantId,
        taskId,
        eventType: "source_marked_helpful",
        metadata: {
          citationId: citationKey,
          chunkId: activeCitation.chunkId,
          userMarkedHelpful: value,
          answerId: context?.answer.id,
        },
      },
      { remote: false },
    );
  }

  function markActiveEvidenceConfusing(value: boolean) {
    if (!activeCitation) return;
    const citationKey = getCitationKey(activeCitation);
    const context = getCitationContext(activeCitation.id);
    setConfusingCitationIds((current) =>
      value
        ? current.includes(citationKey)
          ? current
          : [...current, citationKey]
        : current.filter((item) => item !== citationKey),
    );
    recordEvidenceUse(
      "source_marked_confusing",
      activeCitation,
      context?.answer.interactionId,
      { userMarkedConfusing: value },
    );
    emit(
      {
        interactionId: context?.answer.interactionId,
        participantId,
        taskId,
        eventType: "source_marked_confusing",
        metadata: {
          citationId: citationKey,
          chunkId: activeCitation.chunkId,
          userMarkedConfusing: value,
          answerId: context?.answer.id,
        },
      },
      { remote: false },
    );
  }

  function submitFeedback(feedback: FeedbackPayload) {
    void submitFeedbackToBackend({
      ...feedback,
      sessionId,
      participantLabel,
      participantId,
      taskId,
    });
    emit({
      interactionId: feedback.interactionId,
      participantId,
      taskId,
      eventType: "feedback_submitted",
      metadata: {
        answerId: feedback.answerId,
        rating: feedback.rating,
        commentLength: feedback.comment?.length ?? 0,
      },
    });
  }

  function clearConversation() {
    emit({
      participantId,
      taskId,
      eventType: "conversation_cleared",
      metadata: { messageCount: messages.length },
    });
    setMessages([assistantIntro]);
    setActiveCitation(null);
    setEvidenceOpen(false);
    setCheckedCitationIds([]);
    setEvidenceSupportRatings({});
    setHelpfulCitationIds([]);
    setConfusingCitationIds([]);
    setApiSource(null);
    setLastInteractionId(undefined);
    setSystemFailure(false);
    setFailureCorrelationId(undefined);
  }

  function handleTrustChecklistChange(state: TrustChecklistState) {
    emit(
      {
        interactionId: lastInteractionId,
        participantId,
        taskId,
        eventType: "trust_check_updated",
        metadata: state,
      },
      { remote: false },
    );
    void submitTrustChecklistSnapshot({
      sessionId,
      participantLabel,
      taskId,
      interactionId: lastInteractionId,
      answerClear: state.answerClear,
      evidenceChecked: state.evidenceChecked,
      sourceSupportsAnswer: state.sourceSupportsAnswer,
      uncertaintyNoticed: state.uncertaintyNoticed,
      wouldContactStaffIfNeeded: state.wouldContactStaffIfNeeded,
    }).catch((error) => {
      console.warn("Failed to log trust checklist snapshot", error);
    });
  }

  const conversation = (
    <div className="grid gap-5">
      {workbench && (taskId || sessionId) ? (
        <SystemStatusBar
          items={[
            ...(sessionId
              ? [{ label: "Session active", tone: "success" as const, icon: CheckCircle2 }]
              : []),
            ...(taskId
              ? [{ label: "Task active", tone: "accent" as const, icon: ShieldCheck }]
              : []),
            ...(apiSource
              ? [{ label: "Policy service connected", tone: "neutral" as const }]
              : []),
          ]}
        />
      ) : taskId || sessionId ? (
        <div className="rounded-lg border border-[var(--border-light)] bg-white p-4">
          <div className="flex flex-wrap gap-2">
            {taskId ? <Badge tone="purple">Study task active</Badge> : null}
            {sessionId ? <Badge tone="gold">Session logging active</Badge> : null}
          </div>
        </div>
      ) : null}

      <QuestionInput
        onSubmit={submitQuestion}
        disabled={isLoading || interactionDisabled || systemFailure}
        disabledMessage={
          systemFailure
            ? STUDY_SYSTEM_UNAVAILABLE_MESSAGE
            : interactionDisabled
              ? disabledReason
              : undefined
        }
        contextLabel={taskTitle ?? taskId}
        workbench={workbench}
      />

      {systemFailure ? (
        <BlockingFailurePanel
          message={STUDY_SYSTEM_UNAVAILABLE_MESSAGE}
          correlationId={failureCorrelationId}
        />
      ) : null}

      <div className="rounded-lg border border-[var(--border-light)] bg-[var(--background-soft)] p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="flex gap-3">
            <Info className="mt-1 shrink-0 text-[var(--uq-purple)]" size={20} />
            <p className="text-sm leading-6 text-[var(--text-secondary)]">
              This prototype gives general policy guidance only. Use the synthetic
              scenario and check cited evidence before making a decision.
            </p>
          </div>
          {apiSource && !workbench ? (
            <Badge tone={apiSource === "backend" ? "green" : "gold"} className="shrink-0">
              Response source:{" "}
              {apiSource === "backend" ? "FastAPI backend" : "Mock fallback"}
            </Badge>
          ) : null}
        </div>
      </div>

      {apiSource === "mock-fallback" ? (
        <div
          className="rounded-lg border border-[#b42318] bg-[var(--danger-soft)] p-4 text-sm leading-6 text-[#7a271a]"
          role="alert"
        >
          The policy service is unavailable. This fallback response is not
          source-backed. Pause the study task and ask the researcher for help.
        </div>
      ) : null}

      {showSuggestedQuestions ? (
        <SuggestedQuestions
          onSelect={submitQuestion}
          disabled={isLoading || interactionDisabled || systemFailure}
        />
      ) : null}
      {showTranscriptActions ? (
        <TranscriptActions messages={messages} onClear={clearConversation} />
      ) : null}

      <div
        className={cn(
          "grid min-h-[520px] content-start gap-5 rounded-lg border border-[var(--border-light)] bg-[var(--background-soft)] p-4",
          workbench && "min-h-[560px] border-0 bg-transparent p-0",
        )}
      >
        <div className="flex flex-col gap-1">
          <p className="text-sm font-black text-[var(--text-primary)]">Latest answers</p>
          <p className="text-xs text-[var(--text-secondary)]">
            New questions and answers appear first.
          </p>
        </div>

        {isLoading ? (
          workbench ? (
            <div className="answer-surface px-4 py-3">
              <LoadingIndicator label="Searching policy evidence..." />
            </div>
          ) : (
            <div className="flex items-center gap-2 rounded-lg border border-[var(--border-light)] bg-white px-4 py-3 text-sm font-bold text-[var(--text-secondary)]">
              <Loader2 className="animate-spin text-[var(--uq-purple)]" size={18} />
              Searching policy evidence...
            </div>
          )
        ) : null}

        {visibleMessages.map((message) => (
          <ChatMessage
            key={message.id}
            message={message}
            condition={activeCondition}
            onCitationClick={clickCitation}
            onEvidenceOpen={openEvidence}
            onFeedbackSubmit={submitFeedback}
            workbench={workbench}
          />
        ))}
      </div>
    </div>
  );

  const activeCitationKey = activeCitation ? getCitationKey(activeCitation) : undefined;
  const activeCitationIndex = activeCitation
    ? allCitations.findIndex((citation) => citation.id === activeCitation.id)
    : -1;

  const sidebar = (
    <div className="grid content-start gap-5">
      <div className="rounded-lg border border-[var(--border-light)] bg-white p-5">
        <div className="mb-4 flex flex-wrap gap-2">
          <Badge tone="purple">Research prototype</Badge>
          <Badge tone="gold">Not an official decision tool</Badge>
        </div>
        <StudyConditionSwitcher
          value={activeCondition}
          onChange={handleConditionChange}
        />
      </div>
      <EvidencePanel
        citation={activeCitation}
        isOpen={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
        onMarkChecked={markChecked}
        onSupportRatingChange={rateActiveEvidence}
        onHelpfulChange={markActiveEvidenceHelpful}
        onConfusingChange={markActiveEvidenceConfusing}
        checked={
          activeCitationKey ? checkedCitationIds.includes(activeCitationKey) : false
        }
        supportRating={
          activeCitationKey ? evidenceSupportRatings[activeCitationKey] : undefined
        }
        helpful={
          activeCitationKey ? helpfulCitationIds.includes(activeCitationKey) : false
        }
        confusing={
          activeCitationKey ? confusingCitationIds.includes(activeCitationKey) : false
        }
        variant={workbench ? "inspector" : "panel"}
        citationPosition={
          activeCitationIndex >= 0
            ? { current: activeCitationIndex + 1, total: allCitations.length }
            : undefined
        }
      />
      <TrustCheckPanel
        onChange={handleTrustChecklistChange}
        disabled={interactionDisabled || systemFailure || !lastInteractionId}
      />
    </div>
  );

  return (
    <div
      className={cn(
        workbench
          ? "answer-workspace-grid"
          : showSidebar
            ? "grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]"
            : "grid gap-6",
        className,
      )}
    >
      <div className="grid min-w-0 content-start gap-5">
        {conversation}
        {workbench ? (
          <TrustCheckPanel
            onChange={handleTrustChecklistChange}
            disabled={interactionDisabled || systemFailure || !lastInteractionId}
            workbench
          />
        ) : null}
      </div>
      {workbench ? (
        <div className="workbench-inspector-sticky">
          <EvidencePanel
            citation={activeCitation}
            isOpen={evidenceOpen}
            onClose={() => setEvidenceOpen(false)}
            onMarkChecked={markChecked}
            onSupportRatingChange={rateActiveEvidence}
            onHelpfulChange={markActiveEvidenceHelpful}
            onConfusingChange={markActiveEvidenceConfusing}
            checked={
              activeCitationKey ? checkedCitationIds.includes(activeCitationKey) : false
            }
            supportRating={
              activeCitationKey ? evidenceSupportRatings[activeCitationKey] : undefined
            }
            helpful={
              activeCitationKey ? helpfulCitationIds.includes(activeCitationKey) : false
            }
            confusing={
              activeCitationKey ? confusingCitationIds.includes(activeCitationKey) : false
            }
            variant="inspector"
            citationPosition={
              activeCitationIndex >= 0
                ? { current: activeCitationIndex + 1, total: allCitations.length }
                : undefined
            }
          />
        </div>
      ) : showSidebar ? (
        sidebar
      ) : (
        <div className="grid gap-5">
          <EvidencePanel
            citation={activeCitation}
            isOpen={evidenceOpen || Boolean(activeCitation)}
            onClose={() => setEvidenceOpen(false)}
            onMarkChecked={markChecked}
            onSupportRatingChange={rateActiveEvidence}
            onHelpfulChange={markActiveEvidenceHelpful}
            onConfusingChange={markActiveEvidenceConfusing}
            checked={
              activeCitationKey ? checkedCitationIds.includes(activeCitationKey) : false
            }
            supportRating={
              activeCitationKey ? evidenceSupportRatings[activeCitationKey] : undefined
            }
            helpful={
              activeCitationKey ? helpfulCitationIds.includes(activeCitationKey) : false
            }
            confusing={
              activeCitationKey
                ? confusingCitationIds.includes(activeCitationKey)
                : false
            }
          />
          <TrustCheckPanel
            onChange={handleTrustChecklistChange}
            disabled={interactionDisabled || systemFailure || !lastInteractionId}
          />
        </div>
      )}
    </div>
  );
}
