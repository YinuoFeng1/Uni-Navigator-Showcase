import { ExternalLink, Eye, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Citation } from "@/lib/types";

type CitationCardProps = {
  citation: Citation;
  anchorId?: string;
  onViewEvidence: () => void;
  onOpenSource?: () => void;
};

export function CitationCard({
  citation,
  anchorId,
  onViewEvidence,
  onOpenSource,
}: CitationCardProps) {
  const pageLabel = citation.pageStart
    ? citation.pageEnd && citation.pageEnd !== citation.pageStart
      ? `Pages ${citation.pageStart}-${citation.pageEnd}`
      : `Page ${citation.pageStart}`
    : citation.pageNumber
      ? `Page ${citation.pageNumber}`
      : "";
  const sourceLabel =
    citation.sourceType === "official_policy"
      ? "Official policy"
      : citation.sourceType === "official_student_guidance"
        ? "Official guidance"
        : "Prepared prototype";
  const sourceUrl = citation.sourceUrl ?? citation.url;

  return (
    <div
      id={anchorId}
      className="scroll-mt-24 rounded-md border-t border-[var(--border-light)] py-4 first:border-t-0 first:pt-0 last:pb-0 target:bg-[var(--background-soft)] target:ring-2 target:ring-[var(--uq-purple)] target:ring-offset-4"
    >
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-[var(--uq-purple-light)] text-[var(--uq-purple)]">
          <FileText size={20} aria-hidden="true" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            {citation.label ? <Badge tone="neutral">{citation.label}</Badge> : null}
            <h4 className="font-black text-[var(--text-primary)]">
              {citation.documentTitle}
            </h4>
            <Badge tone="neutral">{sourceLabel}</Badge>
          </div>
          <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
            Section: {citation.sectionHeading ?? "Not specified"}
            {pageLabel ? ` · ${pageLabel}` : ""}
          </p>
          <blockquote className="mt-3 rounded-md bg-[var(--uq-purple-light)] p-3 text-sm leading-6 text-[var(--uq-purple-dark)]">
            &ldquo;{citation.quotedText}&rdquo;
          </blockquote>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button type="button" variant="secondary" size="sm" onClick={onViewEvidence}>
              <Eye size={16} aria-hidden="true" />
              View evidence
            </Button>
            {sourceUrl ? (
              <Button asChild variant="ghost" size="sm" onClick={onOpenSource}>
                <a href={sourceUrl} target="_blank" rel="noreferrer">
                  <ExternalLink size={16} aria-hidden="true" />
                  Open source
                </a>
              </Button>
            ) : (
              <Button type="button" variant="ghost" size="sm" onClick={onOpenSource}>
                <ExternalLink size={16} aria-hidden="true" />
                Open source
              </Button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
