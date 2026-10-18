"use client";

import { useState } from "react";
import { CheckCircle2, LockKeyhole } from "lucide-react";
import { SavedIndicator } from "@/components/ui/status";
import { cn } from "@/lib/utils";

const checklist = [
  { id: "answerClear", label: "I understand the answer." },
  { id: "evidenceChecked", label: "I checked the evidence." },
  {
    id: "sourceSupportsAnswer",
    label: "The evidence seems to support the answer.",
  },
  {
    id: "uncertaintyNoticed",
    label: "I noticed any limitations or uncertainty.",
  },
  {
    id: "wouldContactStaffIfNeeded",
    label:
      "I would contact authorised staff if the case is unclear or high-stakes.",
  },
] as const;

export type TrustChecklistState = Record<(typeof checklist)[number]["id"], boolean>;

type TrustCheckPanelProps = {
  onChange?: (state: TrustChecklistState) => void;
  disabled?: boolean;
  workbench?: boolean;
};

const initialState: TrustChecklistState = {
  answerClear: false,
  evidenceChecked: false,
  sourceSupportsAnswer: false,
  uncertaintyNoticed: false,
  wouldContactStaffIfNeeded: false,
};

export function TrustCheckPanel({
  onChange,
  disabled = false,
  workbench = false,
}: TrustCheckPanelProps) {
  const [checked, setChecked] = useState<TrustChecklistState>(initialState);

  function updateChecked(id: keyof TrustChecklistState, value: boolean) {
    const next = { ...checked, [id]: value };
    setChecked(next);
    onChange?.(next);
  }

  return (
    <section
      className={cn(
        "rounded-lg border border-[var(--border-light)] bg-white p-5",
        workbench && "answer-surface",
      )}
      aria-labelledby="trust-check-heading"
    >
      <div className="flex items-center gap-2">
        {disabled ? (
          <LockKeyhole className="text-[var(--ui-text-muted)]" size={20} />
        ) : (
          <CheckCircle2 className="text-[var(--uq-purple)]" size={20} />
        )}
        <h2 id="trust-check-heading" className="font-black">
          Trust checklist
        </h2>
        {!disabled && Object.values(checked).some(Boolean) ? (
          <SavedIndicator label="Saved" />
        ) : null}
      </div>
      <div className="mt-4 grid gap-3">
        {checklist.map((item) => (
          <label key={item.id} className="flex items-start gap-3 text-sm leading-5">
            <input
              type="checkbox"
              className="mt-0.5 h-5 w-5 shrink-0 accent-[var(--uq-purple)]"
              checked={Boolean(checked[item.id])}
              onChange={(event) => updateChecked(item.id, event.target.checked)}
              disabled={disabled}
            />
            <span>{item.label}</span>
          </label>
        ))}
      </div>
      {disabled ? (
        <p className="mt-4 text-xs leading-5 text-[var(--text-secondary)]">
          Available after an answer is shown.
        </p>
      ) : null}
    </section>
  );
}
