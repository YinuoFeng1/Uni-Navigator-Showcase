"use client";

import { AlertCircle, Loader2, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/form";
import type { FeedbackPayload } from "@/lib/types";
import { cn } from "@/lib/utils";

type FeedbackWidgetProps = {
  answerId: string;
  interactionId?: string;
  onFeedbackSubmit: (feedback: FeedbackPayload) => Promise<void>;
};

export function FeedbackWidget({
  answerId,
  interactionId,
  onFeedbackSubmit,
}: FeedbackWidgetProps) {
  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  async function submitFeedback() {
    if (!rating || submitting || submitted) return;
    setSubmitting(true);
    setErrorMessage("");
    try {
      await onFeedbackSubmit({
        interactionId,
        answerId,
        rating,
        comment: comment.trim() || undefined,
      });
      setSubmitted(true);
    } catch {
      setErrorMessage("Feedback was not saved. Check the connection and retry.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="rounded-lg border border-[var(--border-light)] bg-[var(--background-soft)] p-4">
      <p className="text-sm font-black">Was this answer useful?</p>
      <div className="mt-3 flex gap-2">
        <button
          type="button"
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-md border border-[var(--border-light)] bg-white text-[var(--text-secondary)] hover:bg-[var(--uq-purple-light)]",
            rating === "up" && "border-[var(--uq-purple)] text-[var(--uq-purple)]",
          )}
          onClick={() => setRating("up")}
          disabled={submitted || submitting}
          aria-label="Thumbs up"
        >
          <ThumbsUp size={18} />
        </button>
        <button
          type="button"
          className={cn(
            "flex h-10 w-10 items-center justify-center rounded-md border border-[var(--border-light)] bg-white text-[var(--text-secondary)] hover:bg-[var(--uq-purple-light)]",
            rating === "down" && "border-[var(--uq-purple)] text-[var(--uq-purple)]",
          )}
          onClick={() => setRating("down")}
          disabled={submitted || submitting}
          aria-label="Thumbs down"
        >
          <ThumbsDown size={18} />
        </button>
      </div>

      {rating ? (
        <div className="mt-3 grid gap-2">
          <Textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="What was helpful, unclear, or missing?"
            aria-label="Feedback comment"
          />
          {errorMessage ? (
            <p
              className="flex items-start gap-2 text-sm font-bold text-[var(--ui-danger)]"
              role="alert"
            >
              <AlertCircle className="mt-0.5 shrink-0" size={16} aria-hidden="true" />
              {errorMessage}
            </p>
          ) : null}
          <Button
            type="button"
            size="sm"
            onClick={() => void submitFeedback()}
            disabled={submitted || submitting}
          >
            {submitting ? (
              <>
                <Loader2 className="animate-spin" size={16} aria-hidden="true" />
                Saving feedback...
              </>
            ) : submitted ? (
              "Feedback saved"
            ) : errorMessage ? (
              "Retry feedback"
            ) : (
              "Submit feedback"
            )}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
