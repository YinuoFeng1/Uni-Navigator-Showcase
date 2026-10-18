"use client";

import { useState } from "react";
import { FileSearch } from "lucide-react";
import { EvidencePanel } from "@/components/chat/EvidencePanel";
import { designLabFixture } from "@/lib/designLabFixtures";
import type { Citation } from "@/lib/types";

const syntheticCitation: Citation = {
  id: designLabFixture.citation.citationId,
  citationId: designLabFixture.citation.citationId,
  sourceId: designLabFixture.citation.sourceId,
  chunkId: designLabFixture.citation.chunkId,
  documentTitle: designLabFixture.citation.title,
  sectionHeading: "Synthetic evidence requirement preview",
  pageNumber: 13,
  quotedText: designLabFixture.citation.passage,
  sourceType: "official_policy",
  version: designLabFixture.citation.version,
  sourceUrl: "https://example.invalid/synthetic-policy-preview",
};

export function EvidenceInspectorDemo() {
  const [open, setOpen] = useState(false);
  const [checked, setChecked] = useState(false);
  const [supportRating, setSupportRating] = useState<number>();

  return (
    <section className="answer-surface mb-6 grid gap-3 p-4 xl:hidden">
      <div>
        <p className="text-sm font-black">Interactive drawer check</p>
        <p className="mt-1 text-xs leading-5 text-[var(--ui-text-secondary)]">
          Synthetic fixture only. Use this control to review tablet and mobile
          focus, Escape, and scroll-lock behaviour.
        </p>
      </div>
      <button
        type="button"
        className="inline-flex min-h-11 w-fit items-center gap-2 rounded-[var(--radius-md)] border border-[var(--ui-border-strong)] bg-[var(--ui-surface-elevated)] px-3 text-sm font-bold text-[var(--ui-text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ui-focus-ring)]"
        onClick={() => setOpen(true)}
      >
        <FileSearch size={17} aria-hidden="true" />
        Open interactive evidence inspector
      </button>
      <EvidencePanel
        citation={syntheticCitation}
        isOpen={open}
        onClose={() => setOpen(false)}
        onMarkChecked={() => setChecked(true)}
        onSupportRatingChange={setSupportRating}
        checked={checked}
        supportRating={supportRating}
        variant="inspector"
        citationPosition={{ current: 1, total: 1 }}
      />
    </section>
  );
}
