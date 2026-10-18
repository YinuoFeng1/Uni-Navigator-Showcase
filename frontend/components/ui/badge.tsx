import * as React from "react";
import { cn } from "@/lib/utils";

type BadgeTone = "purple" | "gold" | "green" | "red" | "neutral";

const tones: Record<BadgeTone, string> = {
  purple: "bg-[var(--uq-purple-light)] text-[var(--uq-purple-dark)]",
  gold: "bg-[var(--ui-warning-subtle)] text-[var(--ui-warning)]",
  green: "bg-[var(--ui-success-subtle)] text-[var(--ui-success)]",
  red: "bg-[var(--ui-danger-subtle)] text-[var(--ui-danger)]",
  neutral:
    "bg-[var(--ui-surface-recessed)] text-[var(--ui-text-secondary)]",
};

export function Badge({
  className,
  tone = "neutral",
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: BadgeTone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-bold",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
