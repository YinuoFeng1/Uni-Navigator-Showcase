import { AlertCircle, CheckCircle2, HelpCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CitationCard } from "@/components/chat/CitationCard";
import { EscalationBanner } from "@/components/chat/EscalationBanner";
import { FeedbackWidget } from "@/components/chat/FeedbackWidget";
import { RetrievalStatusBadge } from "@/components/ui/status";
import {
  createCitationAnchorId,
  createCitationSegments,
} from "@/lib/citationText.mjs";
import type { AssistantAnswer, FeedbackPayload } from "@/lib/types";

type AnswerCardProps = {
  answer: AssistantAnswer;
  onCitationClick: (citationId: string) => void;
  onSourceOpen: (citationId: string) => void;
  onEvidenceOpen: (citationId: string) => void;
  onFeedbackSubmit: (feedback: FeedbackPayload) => Promise<void>;
};

const uncertainty = {
  low: { label: "Evidence found", tone: "green" as const, icon: CheckCircle2 },
  medium: { label: "Evidence partly found", tone: "gold" as const, icon: HelpCircle },
  high: { label: "Evidence unclear", tone: "red" as const, icon: AlertCircle },
};

export function AnswerCard({
  answer,
  onCitationClick,
  onSourceOpen,
  onEvidenceOpen,
  onFeedbackSubmit,
}: AnswerCardProps) {
  const current = uncertainty[answer.uncertaintyLevel];
  const Icon = current.icon;
  const answerText = answer.answer ?? answer.shortAnswer;
  const basedOn = answer.basedOn ?? answer.evidenceSummary;
  const uncertaintyNotice =
    answer.uncertainty ??
    "Check the cited evidence carefully; personal circumstances may change the outcome.";
  const escalationGuidance = answer.escalationGuidance ?? answer.nextStep;
  const evidencePassageCount = answer.citations.length;
  const policyFileCount = new Set(
    answer.citations
      .map(
        (citation) =>
          citation.sourceId ??
          citation.documentName ??
          citation.documentTitle ??
          citation.sourceUrl ??
          citation.url,
      )
      .filter(Boolean),
  ).size;
  const actionSteps = buildActionSteps(answer);
  const citationEntries = answer.citations.map((citation, index) => {
    const label = citation.label ?? `[${index + 1}]`;
    return {
      citation,
      label,
      anchorId: createCitationAnchorId(answer.id, label),
    };
  });
  const citationByLabel = new Map(
    citationEntries.map((entry) => [entry.label, entry]),
  );

  return (
    <article className="grid gap-5 rounded-lg border border-[var(--border-light)] bg-white p-5">
      <header className="flex flex-wrap items-center gap-2">
        {answer.retrievalStatus ? (
          <RetrievalStatusBadge status={answer.retrievalStatus} />
        ) : (
          <Badge tone={current.tone}>
            <Icon size={14} aria-hidden="true" />
            {current.label}
          </Badge>
        )}
        <Badge tone="neutral">{formatCount(evidencePassageCount, "evidence passage")}</Badge>
        <Badge tone="neutral">{formatCount(policyFileCount, "policy file")}</Badge>
        {answer.escalationRecommended ? (
          <Badge tone="gold">Contact staff recommended</Badge>
        ) : null}
      </header>

      <section>
        <h3 className="text-sm font-black uppercase tracking-[0.14em] text-[var(--uq-purple)]">
          Direct answer
        </h3>
        <p className="mt-2 whitespace-pre-wrap text-sm leading-7 text-[var(--text-primary)]">
          {createCitationSegments(answerText, [...citationByLabel.keys()]).map(
            (segment, index) => {
              const entry = segment.citationLabel
                ? citationByLabel.get(segment.citationLabel)
                : undefined;

              return entry ? (
                <a
                  key={`${segment.text}-${index}`}
                  href={`#${entry.anchorId}`}
                  className="rounded-sm font-bold text-[var(--uq-purple)] underline decoration-2 underline-offset-2 hover:text-[var(--uq-purple-dark)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--uq-purple)] focus-visible:ring-offset-2"
                  aria-label={`Jump to citation ${entry.label}`}
                  onClick={() => onCitationClick(entry.citation.id)}
                >
                  {segment.text}
                </a>
              ) : (
                segment.text
              );
            },
          )}
        </p>
      </section>

      <section>
        <h3 className="text-sm font-black uppercase tracking-[0.14em] text-[var(--uq-purple)]">
          Action steps
        </h3>
        <ol className="mt-2 grid list-decimal gap-2 pl-5 text-sm leading-7 text-[var(--text-primary)]">
          {actionSteps.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      </section>

      <section className="grid gap-3">
        <h3 className="text-sm font-black uppercase tracking-[0.14em] text-[var(--uq-purple)]">
          Citations
        </h3>
        {basedOn ? (
          <p className="text-sm leading-7 text-[var(--text-secondary)]">{basedOn}</p>
        ) : null}
        {answer.citations.length ? (
          citationEntries.map(({ citation, anchorId }) => (
            <CitationCard
              key={citation.id}
              citation={citation}
              anchorId={anchorId}
              onOpenSource={() => onSourceOpen(citation.id)}
              onViewEvidence={() => onEvidenceOpen(citation.id)}
            />
          ))
        ) : (
          <p className="text-sm leading-7 text-[var(--text-secondary)]">
            No citation was attached because the system did not find enough policy
            evidence for this answer.
          </p>
        )}
      </section>

      <section>
        <h3 className="text-sm font-black uppercase tracking-[0.14em] text-[var(--uq-purple)]">
          Limitations
        </h3>
        <p className="mt-2 text-sm leading-7 text-[var(--text-primary)]">
          {answer.limitations}
        </p>
        {uncertaintyNotice !== answer.limitations ? (
          <p className="mt-2 text-sm leading-7 text-[var(--text-secondary)]">
            {uncertaintyNotice}
          </p>
        ) : null}
      </section>

      {answer.escalationRecommended ? (
        <section>
          <h3 className="mb-3 text-sm font-black uppercase tracking-[0.14em] text-[var(--uq-purple)]">
            Contact university staff
          </h3>
          <EscalationBanner
            level={answer.uncertaintyLevel}
            message={escalationGuidance}
          />
        </section>
      ) : null}

      <FeedbackWidget
        answerId={answer.id}
        interactionId={answer.interactionId}
        onFeedbackSubmit={onFeedbackSubmit}
      />
    </article>
  );
}

function formatCount(count: number, singular: string) {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}

function buildActionSteps(answer: AssistantAnswer) {
  const status = answer.retrievalStatus?.toLowerCase();
  if (status === "insufficient_evidence" || answer.citations.length === 0) {
    return [
      "Try a more specific question that names the policy or university process.",
      "Use the staff guidance below if the issue is urgent or evidence is still unavailable.",
    ];
  }

  return [
    "Review the cited policy passages below before acting.",
    "Follow only the process, deadline, or evidence requirements supported by those citations.",
  ];
}
