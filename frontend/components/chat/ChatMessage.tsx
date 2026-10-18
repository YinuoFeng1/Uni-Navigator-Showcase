import { AnswerCard } from "@/components/chat/AnswerCard";
import type { ChatMessage as ChatMessageType, FeedbackPayload } from "@/lib/types";

type ChatMessageProps = {
  message: ChatMessageType;
  onCitationClick: (citationId: string) => void;
  onSourceOpen: (citationId: string) => void;
  onEvidenceOpen: (citationId: string) => void;
  onFeedbackSubmit: (feedback: FeedbackPayload) => Promise<void>;
};

export function ChatMessage({
  message,
  onCitationClick,
  onSourceOpen,
  onEvidenceOpen,
  onFeedbackSubmit,
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
          onCitationClick={onCitationClick}
          onSourceOpen={onSourceOpen}
          onEvidenceOpen={onEvidenceOpen}
          onFeedbackSubmit={onFeedbackSubmit}
        />
      ) : (
        <div className="rounded-lg border border-[var(--border-light)] bg-white px-4 py-3 text-sm leading-6">
          {message.content}
        </div>
      )}
    </div>
  );
}
