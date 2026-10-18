import { AlertCircle, CheckCircle2, HelpCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { CitationCard } from "@/components/chat/CitationCard";
import { EscalationBanner } from "@/components/chat/EscalationBanner";
import { FeedbackWidget } from "@/components/chat/FeedbackWidget";
import { RetrievalStatusBadge } from "@/components/ui/status";
import { getPresentationPolicy } from "@/lib/presentationPolicy.mjs";
import type { AssistantAnswer, FeedbackPayload, StudyCondition } from "@/lib/types";
import { cn } from "@/lib/utils";

type AnswerCardProps = {
  answer: AssistantAnswer;
  condition: StudyCondition;
  onCitationClick: (citationId: string) => void;
  onEvidenceOpen: (citationId: string) => void;
  onFeedbackSubmit: (feedback: FeedbackPayload) => void;
  workbench?: boolean;
};

const uncertainty = {
  low: { label: "Evidence found", tone: "green" as const, icon: CheckCircle2 },
  medium: { label: "Evidence partly found", tone: "gold" as const, icon: HelpCircle },
  high: { label: "Evidence unclear", tone: "red" as const, icon: AlertCircle },
};

export function AnswerCard({
  answer,
  condition,
  onCitationClick,
  onEvidenceOpen,
  onFeedbackSubmit,
  workbench = false,
}: AnswerCardProps) {
  const current = uncertainty[answer.uncertaintyLevel];
  const Icon = current.icon;
  const answerText = answer.answer ?? answer.shortAnswer;
  const basedOn = answer.basedOn ?? answer.evidenceSummary;
  const uncertaintyNotice =
    answer.uncertainty ??
    "Check the cited evidence carefully; personal circumstances may change the outcome.";
  const escalationGuidance = answer.escalationGuidance ?? answer.nextStep;
  const policy = getPresentationPolicy(condition);

  return (
    <article
      className={cn(
        "grid gap-5 rounded-lg border border-[var(--border-light)] bg-white p-5",
        workbench && "answer-surface gap-0 overflow-hidden p-0",
      )}
    >
      <header className={cn("flex flex-wrap items-center gap-2", workbench && "px-5 py-4")}>
        {answer.retrievalStatus ? (
          <RetrievalStatusBadge status={answer.retrievalStatus} />
        ) : (
        <Badge tone={current.tone}>
          <Icon size={14} aria-hidden="true" />
          {current.label}
        </Badge>
        )}
        <Badge tone="neutral">{answer.citations.length} sources</Badge>
        {answer.escalationRecommended ? (
          <Badge tone="gold">Contact staff recommended</Badge>
        ) : null}
      </header>

      <section className={cn(workbench && "answer-surface-section px-5 py-5")}>
        <h3 className="text-sm font-black uppercase tracking-[0.14em] text-[var(--uq-purple)]">
          Plain-language answer
        </h3>
        <p className="mt-2 text-sm leading-7 text-[var(--text-primary)]">{answerText}</p>
      </section>

      <section className={cn(workbench && "answer-surface-section px-5 py-5")}>
        <h3 className="text-sm font-black uppercase tracking-[0.14em] text-[var(--uq-purple)]">
          What this is based on
        </h3>
        <p className="mt-2 text-sm leading-7 text-[var(--text-primary)]">
          {basedOn}
        </p>
      </section>

      <section className={cn("grid gap-3", workbench && "answer-surface-section px-5 py-5")}>
        <h3 className="text-sm font-black uppercase tracking-[0.14em] text-[var(--uq-purple)]">
          Citations
        </h3>
        {answer.citations.length ? (
          answer.citations.map((citation) => (
            <CitationCard
              key={citation.id}
              citation={citation}
              condition={condition}
              onOpenSource={() => onCitationClick(citation.id)}
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

      {policy.showLimitations ? <section className={cn(workbench && "answer-surface-section px-5 py-5")}>
        <h3 className="text-sm font-black uppercase tracking-[0.14em] text-[var(--uq-purple)]">
          Limitations
        </h3>
        <p className="mt-2 text-sm leading-7 text-[var(--text-primary)]">{answer.limitations}</p>
      </section> : null}

      {policy.showUncertainty ? <section className={cn(workbench && "answer-surface-section px-5 py-5")}>
        <h3 className="text-sm font-black uppercase tracking-[0.14em] text-[var(--uq-purple)]">
          Uncertainty
        </h3>
        <p className="mt-2 text-sm leading-7 text-[var(--text-primary)]">
          {uncertaintyNotice}
        </p>
      </section> : null}

      {policy.showEscalation ? <section className={cn(workbench && "answer-surface-section px-5 py-5")}>
        <h3 className="text-sm font-black uppercase tracking-[0.14em] text-[var(--uq-purple)]">
          Contact staff when needed
        </h3>
        <p className="mt-2 text-sm leading-7 text-[var(--text-primary)]">
          {escalationGuidance}
        </p>
      </section> : null}

      {answer.escalationRecommended && policy.showEscalation ? (
        <div className={cn(workbench && "answer-surface-section px-5 py-5")}>
          <EscalationBanner
            level={answer.uncertaintyLevel}
            message={escalationGuidance}
          />
        </div>
      ) : null}

      <div className={cn(workbench && "answer-surface-section px-5 py-5")}>
        <FeedbackWidget
          answerId={answer.id}
          interactionId={answer.interactionId}
          onFeedbackSubmit={onFeedbackSubmit}
        />
      </div>
    </article>
  );
}
