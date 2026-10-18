"use client";

import { cn } from "@/lib/utils";

type ConfidenceRatingProps = {
  label: string;
  value: number;
  onChange: (value: number) => void;
  lowLabel?: string;
  highLabel?: string;
  disabled?: boolean;
};

export function ConfidenceRating({
  label,
  value,
  onChange,
  lowLabel = "Not confident",
  highLabel = "Very confident",
  disabled = false,
}: ConfidenceRatingProps) {
  return (
    <div className="grid gap-3">
      <p className="text-sm font-black text-[var(--text-primary)]">{label}</p>
      <div className="flex items-center gap-2" role="radiogroup" aria-label={label}>
        {[1, 2, 3, 4, 5].map((score) => (
          <button
            key={score}
            type="button"
            role="radio"
            aria-checked={value === score}
            className={cn(
              "flex h-10 w-10 items-center justify-center rounded-md border border-[var(--border-light)] bg-white text-sm font-black text-[var(--text-secondary)]",
              value === score &&
                "border-[var(--uq-purple)] bg-[var(--uq-purple)] text-white",
            )}
            disabled={disabled}
            onClick={() => onChange(score)}
          >
            {score}
          </button>
        ))}
      </div>
      <div className="flex justify-between text-xs text-[var(--text-secondary)]">
        <span>{lowLabel}</span>
        <span>{highLabel}</span>
      </div>
    </div>
  );
}
