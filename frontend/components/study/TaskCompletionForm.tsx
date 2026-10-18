"use client";

import { Button } from "@/components/ui/button";
import { Label, Select, Textarea } from "@/components/ui/form";
import { ConfidenceRating } from "@/components/study/ConfidenceRating";
import type { WouldContactStaff } from "@/lib/types";

type TaskCompletionFormProps = {
  finalDecisionText: string;
  onFinalDecisionTextChange: (value: string) => void;
  confidenceRating: number;
  onConfidenceRatingChange: (value: number) => void;
  wouldContactStaff: WouldContactStaff;
  onWouldContactStaffChange: (value: WouldContactStaff) => void;
  perceivedAnswerSupported: number;
  onPerceivedAnswerSupportedChange: (value: number) => void;
  notes: string;
  onNotesChange: (value: string) => void;
  onSubmit: () => void;
  isSubmitting: boolean;
  isSubmitted: boolean;
  disabled?: boolean;
};

export function TaskCompletionForm({
  finalDecisionText,
  onFinalDecisionTextChange,
  confidenceRating,
  onConfidenceRatingChange,
  wouldContactStaff,
  onWouldContactStaffChange,
  perceivedAnswerSupported,
  onPerceivedAnswerSupportedChange,
  notes,
  onNotesChange,
  onSubmit,
  isSubmitting,
  isSubmitted,
  disabled = false,
}: TaskCompletionFormProps) {
  return (
    <div className="grid gap-5">
      <p className="rounded-md bg-[var(--warning-soft)] p-3 text-xs leading-5 text-[var(--text-primary)]">
        Please answer based on the synthetic study scenario only. Do not enter real
        personal academic, visa, financial, health, or appeal details.
      </p>

      <div className="grid gap-2">
        <Label htmlFor="final-decision">
          What would you do based on the information you found?
        </Label>
        <Textarea
          id="final-decision"
          value={finalDecisionText}
          onChange={(event) => onFinalDecisionTextChange(event.target.value)}
          placeholder="Write the action you would take next..."
          disabled={disabled || isSubmitting || isSubmitted}
          required
          aria-describedby="final-decision-help"
        />
        <p id="final-decision-help" className="text-xs text-[var(--text-secondary)]">
          Required. Use the scenario only; do not include real personal details.
        </p>
      </div>

      <ConfidenceRating
        label="How confident are you in this decision?"
        value={confidenceRating}
        onChange={onConfidenceRatingChange}
        disabled={disabled || isSubmitting || isSubmitted}
      />

      <div className="grid gap-2">
        <Label htmlFor="would-contact-staff">
          Would you contact authorised university staff before acting on this decision?
        </Label>
        <Select
          id="would-contact-staff"
          value={wouldContactStaff}
          onChange={(event) =>
            onWouldContactStaffChange(event.target.value as WouldContactStaff)
          }
          disabled={disabled || isSubmitting || isSubmitted}
        >
          <option value="yes">Yes</option>
          <option value="no">No</option>
          <option value="not_sure">Not sure</option>
        </Select>
      </div>

      <ConfidenceRating
        label="Do you think the answer was supported by the evidence shown?"
        value={perceivedAnswerSupported}
        onChange={onPerceivedAnswerSupportedChange}
        lowLabel="Not supported"
        highLabel="Very well supported"
        disabled={disabled || isSubmitting || isSubmitted}
      />

      <div className="grid gap-2">
        <Label htmlFor="final-response-notes">
          Any notes about why you made this decision?
        </Label>
        <Textarea
          id="final-response-notes"
          value={notes}
          onChange={(event) => onNotesChange(event.target.value)}
          placeholder="Optional notes..."
          disabled={disabled || isSubmitting || isSubmitted}
        />
      </div>

      <Button
        type="button"
        onClick={onSubmit}
        disabled={
          disabled ||
          isSubmitting ||
          isSubmitted ||
          finalDecisionText.trim().length === 0
        }
      >
        {isSubmitted
          ? "Final response submitted"
          : isSubmitting
            ? "Submitting..."
            : "Submit final response"}
      </Button>
      {isSubmitted ? (
        <p
          className="rounded-md border border-[#3b8c5a] bg-[var(--success-soft)] p-3 text-sm font-bold text-[#176b3a]"
          role="status"
        >
          Your final response has been saved. Return to the task card and select
          Finish task.
        </p>
      ) : null}
    </div>
  );
}
