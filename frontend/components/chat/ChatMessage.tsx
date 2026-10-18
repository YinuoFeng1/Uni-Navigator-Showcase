import { AnswerCard } from "@/components/chat/AnswerCard";
import type { ChatMessage as ChatMessageType, FeedbackPayload, StudyCondition } from "@/lib/types";

type ChatMessageProps = {
  message: ChatMessageType;
  condition: StudyCondition;
  onCitationClick: (citationId: string) => void;
  onEvidenceOpen: (citationId: string) => void;
  onFeedbackSubmit: (feedback: FeedbackPayload) => void;
  workbench?: boolean;
};

export function ChatMessage({
  message,
  condition,
  onCitationClick,
  onEvidenceOpen,
  onFeedbackSubmit,
  workbench = false,
}: ChatMessageProps) {
  if (message.role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[86%] rounded-lg bg-[var(--uq-purple)] px-4 py-3 text-sm leading-6 text-white">
          {message.content}
        </div>
      </div>
    );
  }

  return (
    <div className="grid max-w-[96%] gap-3">
      <div className="rounded-lg border border-[var(--border-light)] bg-white px-4 py-3 text-sm font-bold text-[var(--uq-purple)]">
        Uni-Navigator
      </div>
      {message.answer ? (
        <AnswerCard
          answer={message.answer}
          condition={condition}
          onCitationClick={onCitationClick}
          onEvidenceOpen={onEvidenceOpen}
          onFeedbackSubmit={onFeedbackSubmit}
          workbench={workbench}
        />
      ) : (
        <div className="rounded-lg border border-[var(--border-light)] bg-white px-4 py-3 text-sm leading-6">
          {message.content}
        </div>
      )}
    </div>
  );
}
