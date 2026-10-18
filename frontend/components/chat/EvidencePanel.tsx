"use client";

import { useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  ExternalLink,
  FileText,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { InlineNotice, LoadingIndicator } from "@/components/ui/status";
import type { Citation } from "@/lib/types";
import { cn } from "@/lib/utils";

type EvidencePanelProps = {
  citation: Citation | null;
  isOpen: boolean;
  onClose: () => void;
  onMarkChecked: () => void;
  onOpenSource: () => void;
  checked?: boolean;
  variant?: "panel" | "inspector";
  citationPosition?: { current: number; total: number };
  isLoading?: boolean;
  errorMessage?: string;
};

function HighlightedText({ citation }: { citation: Citation }) {
  const surrounding = citation.surroundingText ?? citation.quotedText;
  const parts = surrounding.split(citation.quotedText);

  if (parts.length === 1) {
    return (
      <p className="text-sm leading-7 text-[var(--text-primary)]">
        <mark className="rounded bg-[var(--warning-soft)] px-1 py-0.5 text-[var(--text-primary)]">
          {citation.quotedText}
        </mark>
      </p>
    );
  }

  return (
    <p className="text-sm leading-7 text-[var(--text-primary)]">
      {parts[0]}
      <mark className="rounded bg-[var(--warning-soft)] px-1 py-0.5 text-[var(--text-primary)]">
        {citation.quotedText}
      </mark>
      {parts.slice(1).join(citation.quotedText)}
    </p>
  );
}

export function EvidencePanel({
  citation,
  isOpen,
  onClose,
  onMarkChecked,
  onOpenSource,
  checked = false,
  variant = "panel",
  citationPosition,
  isLoading = false,
  errorMessage,
}: EvidencePanelProps) {
  const panelRef = useRef<HTMLElement>(null);
  const [isOverlay, setIsOverlay] = useState(false);
  const pageLabel = citation?.pageStart
    ? citation.pageEnd && citation.pageEnd !== citation.pageStart
      ? `Pages ${citation.pageStart}-${citation.pageEnd}`
      : `Page ${citation.pageStart}`
    : citation?.pageNumber
      ? `Page ${citation.pageNumber}`
      : "";

  useEffect(() => {
    if (variant !== "inspector") return;
    const media = window.matchMedia("(max-width: 1199px)");
    const update = () => setIsOverlay(media.matches);
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [variant]);

  useEffect(() => {
    if (!isOpen || !isOverlay || variant !== "inspector") return;
    const panel = panelRef.current;
    if (!panel) return;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusableSelector =
      'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';
    const initial = panel.querySelector<HTMLElement>(focusableSelector) ?? panel;
    initial.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        panel?.querySelectorAll<HTMLElement>(focusableSelector) ?? [],
      );
      if (focusable.length === 0) {
        event.preventDefault();
        panel?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      document.body.style.overflow = previousOverflow;
      previouslyFocused?.focus();
    };
  }, [isOpen, isOverlay, onClose, variant]);

  const sourceLabel =
    citation?.sourceType === "official_policy"
      ? "Official policy"
      : citation?.sourceType === "official_student_guidance"
        ? "Official guidance"
        : "Prepared prototype";
  const sourceUrl = citation?.sourceUrl ?? citation?.url;
  return (
    <>
      {variant === "inspector" ? (
        <button
          type="button"
          className="evidence-backdrop hidden"
          data-open={isOpen && isOverlay}
          onClick={onClose}
          aria-label="Close evidence inspector"
          tabIndex={-1}
        />
      ) : null}
      <aside
        ref={panelRef}
        className={cn(
          "rounded-lg border border-[var(--border-light)] bg-white transition",
          variant === "inspector" ? "evidence-inspector" : "",
          variant === "panel" && (isOpen ? "block" : "hidden lg:block"),
        )}
        data-open={variant === "inspector" ? isOpen : undefined}
        aria-label={variant === "inspector" ? "Evidence inspector" : "Evidence panel"}
        role={isOverlay ? "dialog" : undefined}
        aria-modal={isOverlay ? true : undefined}
        tabIndex={-1}
      >
      <div className="flex items-start justify-between gap-3 border-b border-[var(--border-light)] p-5">
        <div>
          <p className="text-sm font-black uppercase tracking-[0.16em] text-[var(--uq-purple)]">
            Evidence inspector
          </p>
          <h2 className="mt-2 text-xl font-black">Check the source clause</h2>
          {citationPosition ? (
            <p className="mono-metadata mt-1 text-[var(--text-secondary)]">
              Citation {citationPosition.current} of {citationPosition.total}
            </p>
          ) : null}
        </div>
        <button
          type="button"
          className={cn(
            "rounded-md p-2 text-[var(--text-secondary)] hover:bg-[var(--uq-purple-light)]",
            variant === "inspector" ? "xl:hidden" : "lg:hidden",
          )}
          onClick={onClose}
          aria-label="Close evidence panel"
        >
          <X size={20} />
        </button>
      </div>

      {isLoading ? (
        <div className="p-5">
          <LoadingIndicator label="Loading source evidence..." />
        </div>
      ) : errorMessage ? (
        <div className="p-5">
          <InlineNotice tone="warning" title="Evidence unavailable">
            {errorMessage}
          </InlineNotice>
        </div>
      ) : citation ? (
        <div className="grid gap-5 p-5">
          <div className="rounded-lg bg-[var(--background-soft)] p-4">
            <div className="flex items-start gap-3">
              <FileText className="mt-1 text-[var(--uq-purple)]" size={20} />
              <div>
                <h3 className="font-black">{citation.documentTitle}</h3>
                <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
                  {citation.sectionHeading ?? "Section not specified"}
                  {pageLabel ? ` · ${pageLabel}` : ""}
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Badge tone="neutral">{sourceLabel}</Badge>
                  {citation.version ? (
                    <Badge tone="neutral">Version {citation.version}</Badge>
                  ) : null}
                </div>
              </div>
            </div>
          </div>

          <div>
            <p className="mb-2 text-sm font-bold text-[var(--text-primary)]">
              Highlighted evidence
            </p>
            <div className="rounded-lg border border-[var(--border-light)] p-4">
              <HighlightedText citation={citation} />
            </div>
          </div>

          <Button
            type="button"
            variant={checked ? "subtle" : "default"}
            onClick={onMarkChecked}
          >
            <CheckCircle2 size={18} aria-hidden="true" />
            {checked ? "Marked as checked" : "Mark as checked"}
          </Button>

          {sourceUrl ? (
            <Button asChild type="button" variant="secondary">
              <a href={sourceUrl} target="_blank" rel="noreferrer" onClick={onOpenSource}>
                <ExternalLink size={17} aria-hidden="true" />
                Open official source
              </a>
            </Button>
          ) : null}

        </div>
      ) : (
        <div className="p-5">
          <Badge tone="gold">No evidence selected</Badge>
          <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
            Open a citation from an answer to inspect the source text here.
          </p>
        </div>
      )}
      </aside>
    </>
  );
}
