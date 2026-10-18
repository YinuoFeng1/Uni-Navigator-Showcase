"use client";

import { FormEvent, useState } from "react";
import { ShieldCheck, Send } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type QuestionInputProps = {
  onSubmit: (question: string, sensitiveWarningShown?: boolean) => void;
  disabled?: boolean;
  disabledMessage?: string;
  contextLabel?: string;
  workbench?: boolean;
};

const sensitivePattern =
  /\b(passport|visa number|medical certificate|diagnosis|bank account|tfn|tax file number|student number|student id|address|phone|email)\b|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}|\b(?:\+?61|0)[2-478](?:[\s-]?\d){8}\b|\b\d{8,10}\b/i;

export function QuestionInput({
  onSubmit,
  disabled = false,
  disabledMessage,
  contextLabel,
  workbench = false,
}: QuestionInputProps) {
  const [value, setValue] = useState("");
  const sensitiveWarningShown = sensitivePattern.test(value);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const question = value.trim();
    if (!question) return;
    onSubmit(question, sensitiveWarningShown);
    setValue("");
  }

  return (
    <form
      className={cn("grid gap-2", workbench && "workbench-composer")}
      onSubmit={handleSubmit}
    >
      {contextLabel ? (
        <div className="flex items-center justify-between gap-3 text-xs">
          <span className="font-bold text-[var(--ui-text-primary)]">Current task</span>
          <span className="min-w-0 truncate text-[var(--ui-text-muted)]">
            {contextLabel}
          </span>
        </div>
      ) : null}
      <div className="flex items-end gap-2">
        <textarea
          className="min-h-[5.5rem] flex-1 resize-y rounded-md border border-[var(--border-light)] bg-white px-4 py-3 text-sm leading-6 shadow-sm focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--focus-ring)]"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Ask a university policy question..."
          aria-label="University policy question"
          disabled={disabled}
          rows={3}
        />
        <Button
          type="submit"
          size={workbench ? "icon" : "default"}
          disabled={disabled || value.trim().length === 0}
          aria-label="Send question"
          title="Send question"
        >
          <Send size={18} aria-hidden="true" />
          {!workbench ? <span className="hidden sm:inline">Send</span> : null}
        </Button>
      </div>
      {disabled && disabledMessage ? (
        <p
          className="rounded-md border border-[var(--border-light)] bg-[var(--background-soft)] px-3 py-2 text-xs font-bold leading-5 text-[var(--text-secondary)]"
          role="status"
        >
          {disabledMessage}
        </p>
      ) : null}
      {sensitiveWarningShown ? (
        <p className="rounded-md border border-[var(--uq-gold)] bg-[var(--warning-soft)] px-3 py-2 text-xs font-bold leading-5 text-[var(--text-primary)]">
          This looks like it may include personal or sensitive information. Use
          the synthetic scenario only and remove real personal details.
        </p>
      ) : null}
      <p className="flex items-start gap-1.5 text-xs leading-5 text-[var(--text-secondary)]">
        <ShieldCheck className="mt-0.5 shrink-0" size={14} aria-hidden="true" />
        <span>
          Use the synthetic scenario only. Do not type real personal or sensitive details.
        </span>
      </p>
    </form>
  );
}
