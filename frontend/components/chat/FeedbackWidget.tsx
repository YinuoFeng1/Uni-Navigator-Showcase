"use client";

import { ThumbsDown, ThumbsUp } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/form";
import type { FeedbackPayload } from "@/lib/types";
import { cn } from "@/lib/utils";

type FeedbackWidgetProps = {
  answerId: string;
  interactionId?: string;
  onFeedbackSubmit: (feedback: FeedbackPayload) => void;
};

export function FeedbackWidget({
  answerId,
  interactionId,
  onFeedbackSubmit,
}: FeedbackWidgetProps) {
  const [rating, setRating] = useState<"up" | "down" | null>(null);
  const [comment, setComment] = useState("");
  const [submitted, setSubmitted] = useState(false);

  function submitFeedback() {
    if (!rating) return;
    onFeedbackSubmit({
      interactionId,
      answerId,
      rating,
      comment: comment.trim() || undefined,
    });
    setSubmitted(true);
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
          <Button type="button" size="sm" onClick={submitFeedback} disabled={submitted}>
            {submitted ? "Feedback saved" : "Submit feedback"}
          </Button>
        </div>
      ) : null}
    </div>
  );
}
