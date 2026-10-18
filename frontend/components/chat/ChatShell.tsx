"use client";

import { useMemo, useState } from "react";
import { Bot, Loader2, RotateCcw } from "lucide-react";
import { ChatMessage } from "@/components/chat/ChatMessage";
import { EvidencePanel } from "@/components/chat/EvidencePanel";
import { QuestionInput } from "@/components/chat/QuestionInput";
import { SuggestedQuestions } from "@/components/chat/SuggestedQuestions";
import { TranscriptActions } from "@/components/chat/TranscriptActions";
import { ResearchSessionBar } from "@/components/chat/ResearchSessionBar";
import { useResearchSession } from "@/components/chat/useResearchSession";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { BlockingFailurePanel, InlineNotice } from "@/components/ui/status";
import {
  ChatSystemFailureError,
  CHAT_REQUEST_RETRY_MESSAGE,
  CHAT_SYSTEM_UNAVAILABLE_MESSAGE,
  sendChatMessage,
} from "@/lib/api";
import { createEvidenceUsePayload } from "@/lib/evidencePayload.mjs";
import type {
  ChatMessage as ChatMessageType,
  Citation,
  EvidenceUseAction,
  FeedbackPayload,
  StudyEventType,
} from "@/lib/types";

type FailedChatRequest = {
  question: string;
  sensitiveWarningShown: boolean;
};
type ChatEventInput = {
  interactionId?: string;
  eventType: StudyEventType;
  metadata?: Record<string, unknown>;
};

const assistantIntro: ChatMessageType = {
  id: "assistant_intro",
  role: "assistant",
  content:
    "Ask one university policy question at a time. I will show the evidence used and suggest when staff contact is safer.",
  createdAt: new Date().toISOString(),
};

export function ChatShell() {
  const research = useResearchSession();
  const [messages, setMessages] = useState<ChatMessageType[]>([assistantIntro]);
  const [isLoading, setIsLoading] = useState(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [checkedCitationIds, setCheckedCitationIds] = useState<string[]>([]);
  const [systemFailure, setSystemFailure] = useState(false);
  const [failureCorrelationId, setFailureCorrelationId] = useState<string>();
  const [failedRequest, setFailedRequest] = useState<FailedChatRequest>();

  const allCitations = useMemo(
    () => messages.flatMap((message) => message.answer?.citations ?? []),
    [messages],
  );
  const visibleMessages = useMemo(() => [...messages].reverse(), [messages]);

  function emit(event: ChatEventInput) {
    void research.write("log-event", event).catch(() => undefined);
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
  ) {
    return research.write("evidence-use",
        createEvidenceUsePayload({
          interactionId,
          citation,
          evidenceAction,
        }),
    );
  }

  async function submitQuestion(
    question: string,
    sensitiveWarningShown = false,
  ): Promise<boolean> {
    if (systemFailure || isLoading || research.blocked) return false;

    const userMessage: ChatMessageType = {
      id: `user_${Date.now()}`,
      role: "user",
      content: question,
      createdAt: new Date().toISOString(),
    };

    setMessages((current) => [...current, userMessage]);
    setIsLoading(true);
    setFailedRequest(undefined);
    setFailureCorrelationId(undefined);
    emit({
      eventType: "question_submitted",
      metadata: { questionLength: question.length, sensitiveWarningShown },
    });

    try {
      const answer = await sendChatMessage({ question, sensitiveWarningShown, sessionId: research.session?.sessionId });
      const assistantMessage: ChatMessageType = {
        id: `assistant_${Date.now()}`,
        role: "assistant",
        content: answer.shortAnswer,
        answer,
        createdAt: new Date().toISOString(),
      };

      setMessages((current) => [...current, assistantMessage]);
      setSystemFailure(false);
      emit({
        interactionId: answer.interactionId,
        eventType: "answer_received",
        metadata: {
          answerId: answer.id,
          citationCount: answer.citations.length,
          uncertaintyLevel: answer.uncertaintyLevel,
          escalationRecommended: answer.escalationRecommended,
          escalationCategory: answer.escalationCategory,
          escalationReasons: answer.escalationReasons,
          scopeDecision: answer.scopeDecision?.decision,
          apiSource: "backend",
        },
      });
      return true;
    } catch (error) {
      const failure =
        error instanceof ChatSystemFailureError
          ? error
          : new ChatSystemFailureError({ failureStage: "frontend" });
      setMessages((current) =>
        current.filter((message) => message.id !== userMessage.id),
      );
      setSystemFailure(!failure.retryable);
      setFailedRequest({ question, sensitiveWarningShown });
      setFailureCorrelationId(failure.interactionId);
      if (!failure.systemFailureLogged) {
        emit({
          interactionId: failure.interactionId,
          eventType: "system_failure",
          metadata: {
            failureCategory: failure.failureCategory ?? "frontend_unavailable",
            failureStage: failure.failureStage ?? "frontend",
            participantVisibleActionTaken: failure.retryable
              ? "retry_offered"
              : "researcher_notification_requested",
          },
        });
      }
      return false;
    } finally {
      setIsLoading(false);
    }
  }

  async function retryFailedRequest() {
    if (!failedRequest) return;
    await submitQuestion(
      failedRequest.question,
      failedRequest.sensitiveWarningShown,
    );
  }

  function openEvidence(citationId: string) {
    const citation = allCitations.find((item) => item.id === citationId) ?? null;
    const context = getCitationContext(citationId);
    setActiveCitation(citation);
    setEvidenceOpen(true);
    recordEvidenceUse(
      "evidence_panel_opened",
      context?.citation ?? citation,
      context?.answer.interactionId,
    ).catch(() => undefined);
  }

  function clickCitation(citationId: string) {
    const context = getCitationContext(citationId);
    recordEvidenceUse(
      "citation_clicked",
      context?.citation ?? null,
      context?.answer.interactionId,
    ).catch(() => undefined);
  }

  function openSource(citationId: string) {
    const context = getCitationContext(citationId);
    void recordEvidenceUse("source_opened", context?.citation ?? null, context?.answer.interactionId).catch(() => undefined);
  }

  function markChecked() {
    if (!activeCitation) return;
    const context = getCitationContext(activeCitation.id);
    const citationKey = getCitationKey(activeCitation);
    void recordEvidenceUse("source_checked", activeCitation, context?.answer.interactionId).then(() => {
      setCheckedCitationIds((current) => current.includes(citationKey) ? current : [...current, citationKey]);
    }).catch(() => undefined);
  }

  async function submitFeedback(feedback: FeedbackPayload): Promise<void> {
    await research.write("feedback", feedback);
  }

  function clearConversation() {
    emit({
      eventType: "conversation_cleared",
      metadata: { messageCount: messages.length },
    });
    setMessages([assistantIntro]);
    setActiveCitation(null);
    setEvidenceOpen(false);
    setCheckedCitationIds([]);
    setSystemFailure(false);
    setFailureCorrelationId(undefined);
    setFailedRequest(undefined);
  }

  const activeCitationKey = activeCitation ? getCitationKey(activeCitation) : undefined;
  const activeCitationIndex = activeCitation
    ? allCitations.findIndex((citation) => citation.id === activeCitation.id)
    : -1;

  return (
    <div>
    <ResearchSessionBar research={research} answering={isLoading} onStarted={() => {
      setMessages([assistantIntro]); setActiveCitation(null); setEvidenceOpen(false);
      setCheckedCitationIds([]); setFailedRequest(undefined); setSystemFailure(false);
    }} />
    <div inert={research.blocked} className={research.blocked ? "opacity-60" : ""}>
    <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
      <div className="grid min-w-0 content-start gap-5">
        <div className="rounded-lg border border-[var(--border-light)] bg-[var(--background-soft)] p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex gap-3">
              <Bot className="mt-1 shrink-0 text-[var(--uq-purple)]" size={20} />
              <p className="text-sm leading-6 text-[var(--text-secondary)]">
                Answers are generated live by AI from retrieved university policy
                evidence. This research prototype is not official university advice.
              </p>
            </div>
            <Badge tone="purple" className="self-start shrink-0">
              Live AI
            </Badge>
          </div>
        </div>

        <QuestionInput
          key={research.session?.sessionId ?? "self-test"}
          onSubmit={submitQuestion}
          disabled={isLoading || systemFailure}
          disabledMessage={systemFailure ? CHAT_SYSTEM_UNAVAILABLE_MESSAGE : undefined}
        />

        {failedRequest && !systemFailure ? (
          <InlineNotice title="Request failed" tone="danger" className="p-4">
            <p>{CHAT_REQUEST_RETRY_MESSAGE}</p>
            <Button
              type="button"
              variant="secondary"
              className="mt-3"
              onClick={retryFailedRequest}
              disabled={isLoading}
            >
              <RotateCcw size={16} aria-hidden="true" />
              Retry
            </Button>
          </InlineNotice>
        ) : null}

        {systemFailure ? (
          <BlockingFailurePanel
            message={CHAT_SYSTEM_UNAVAILABLE_MESSAGE}
            correlationId={failureCorrelationId}
          />
        ) : null}

        <SuggestedQuestions
          onSelect={submitQuestion}
          disabled={isLoading || systemFailure}
        />
        <TranscriptActions messages={messages} onClear={clearConversation} onDownload={() => emit({ eventType: "transcript_downloaded" })} />

        <div className="grid min-h-[520px] content-start gap-5 rounded-lg border border-[var(--border-light)] bg-[var(--background-soft)] p-4">
          <div className="flex flex-col gap-1">
            <p className="text-sm font-black text-[var(--text-primary)]">Latest answers</p>
            <p className="text-xs text-[var(--text-secondary)]">
              New questions and answers appear first.
            </p>
          </div>

          {isLoading ? (
            <div className="flex items-center gap-2 rounded-lg border border-[var(--border-light)] bg-white px-4 py-3 text-sm font-bold text-[var(--text-secondary)]">
              <Loader2 className="animate-spin text-[var(--uq-purple)]" size={18} />
              Searching policy evidence...
            </div>
          ) : null}

          {visibleMessages.map((message) => (
            <ChatMessage
              key={message.id}
              message={message}
              onCitationClick={clickCitation}
              onSourceOpen={openSource}
              onEvidenceOpen={openEvidence}
              onFeedbackSubmit={submitFeedback}
            />
          ))}
        </div>
      </div>

      <EvidencePanel
        citation={activeCitation}
        isOpen={evidenceOpen}
        onClose={() => setEvidenceOpen(false)}
        onMarkChecked={markChecked}
        onOpenSource={() => activeCitation && openSource(activeCitation.id)}
        checked={
          activeCitationKey ? checkedCitationIds.includes(activeCitationKey) : false
        }
        citationPosition={
          activeCitationIndex >= 0
            ? { current: activeCitationIndex + 1, total: allCitations.length }
            : undefined
        }
      />
    </div>
    </div>
    </div>
  );
}
