import {
  AlertCircle,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleDashed,
  FileCheck2,
  Loader2,
  LockKeyhole,
  Send,
  ShieldAlert,
} from "lucide-react";
import { AppearanceSwitcher } from "@/components/layout/AppearanceSwitcher";
import { EvidenceInspectorDemo } from "@/components/design-lab/EvidenceInspectorDemo";
import { designDirections, designLabFixture } from "@/lib/designLabFixtures";

function LabChip({
  children,
  tone = "default",
}: {
  children: React.ReactNode;
  tone?: "default" | "success" | "warning" | "danger";
}) {
  const classes = {
    default: "border-[var(--lab-border)] text-[var(--lab-muted)]",
    success: "border-[#3f8f6b] text-[#57ad81]",
    warning: "border-[#a47a2e] text-[#c49338]",
    danger: "border-[#b85c55] text-[#d87970]",
  };
  return (
    <span
      className={`inline-flex min-h-7 items-center gap-1.5 rounded border bg-[var(--lab-recessed)] px-2 py-1 text-xs font-bold ${classes[tone]}`}
    >
      {children}
    </span>
  );
}

function DirectionPreview({
  direction,
}: {
  direction: (typeof designDirections)[number];
}) {
  const paper = direction.id === "paper";
  return (
    <article className={`design-direction ${direction.className}`}>
      <header className="border-b border-[var(--lab-border)] bg-[var(--lab-surface)] p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-xs font-black uppercase text-[var(--lab-accent)]">
              Visual direction
            </p>
            <h2 className={`mt-1 text-xl font-black ${paper ? "font-serif" : ""}`}>
              {direction.name}
            </h2>
            <p className="design-lab-muted mt-2 max-w-4xl text-sm leading-6">
              {direction.rationale}
            </p>
          </div>
          {direction.id === "research" ? (
            <LabChip tone="success">
              <CheckCircle2 size={14} aria-hidden="true" /> Recommended
            </LabChip>
          ) : null}
        </div>
      </header>

      <div className="design-direction-preview">
        <aside className="design-lab-panel design-lab-rail">
          <p className="text-xs font-black uppercase text-[var(--lab-accent)]">
            Study progress
          </p>
          <ol className="mt-4 grid gap-3">
            {[
              "Consent and session",
              "Read scenario",
              "Ask and review",
              "Check evidence",
              "Record decision",
              "Finish task",
            ].map((step, index) => (
              <li key={step} className="flex items-start gap-2 text-xs leading-5">
                <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border border-[var(--lab-border)]">
                  {index < 3 ? <Check size={12} /> : index + 1}
                </span>
                <span className={index === 3 ? "font-black text-[var(--lab-accent)]" : "design-lab-muted"}>
                  {step}
                </span>
              </li>
            ))}
          </ol>
          <div className="mt-6 border-t border-[var(--lab-border)] pt-4">
            <p className="text-xs font-black">{designLabFixture.taskTitle}</p>
            <p className="design-lab-muted mt-2 text-xs leading-5">
              {designLabFixture.scenario}
            </p>
          </div>
          <button
            type="button"
            className="mt-5 min-h-11 w-full rounded border border-[var(--lab-border)] bg-[var(--lab-recessed)] px-3 text-left text-xs font-bold"
          >
            Session active
          </button>
        </aside>

        <main className="design-lab-panel min-w-0">
          <div className="flex flex-wrap gap-2 border-b border-[var(--lab-border)] pb-3">
            <LabChip tone="success">
              <CheckCircle2 size={14} /> Session active
            </LabChip>
            <LabChip>Task 1 of 3</LabChip>
            <LabChip tone="success">Saved</LabChip>
          </div>

          <section className="mt-4 rounded border border-[var(--lab-border)] bg-[var(--lab-surface)] p-3">
            <div className="flex items-end gap-2">
              <textarea
                className="min-h-20 flex-1 resize-none rounded border border-[var(--lab-border)] bg-[var(--lab-recessed)] p-3 text-sm text-[var(--lab-text)]"
                value={designLabFixture.question}
                readOnly
                aria-label={`${direction.name} synthetic question preview`}
              />
              <button
                type="button"
                className="grid h-11 w-11 place-items-center rounded bg-[var(--lab-accent)] text-white"
                aria-label="Send synthetic question"
              >
                <Send size={17} />
              </button>
            </div>
            <p className="design-lab-muted mt-2 text-xs">
              Synthetic scenario only. Do not enter real personal information.
            </p>
          </section>

          <section className="mt-4 rounded border border-[var(--lab-border)] bg-[var(--lab-surface)]">
            <header className="flex flex-wrap gap-2 border-b border-[var(--lab-border)] p-4">
              <LabChip tone="success">
                <FileCheck2 size={14} /> Grounded evidence
              </LabChip>
              <LabChip>1 citation</LabChip>
            </header>
            <div className="p-4">
              <p className="text-xs font-black uppercase text-[var(--lab-accent)]">
                Plain-language answer
              </p>
              <p className="mt-2 text-sm leading-6">{designLabFixture.answer}</p>
              <p className="design-lab-muted mt-3 text-sm leading-6">
                {designLabFixture.longAnswer}
              </p>
            </div>
            <div className="border-t border-[var(--lab-border)] p-4">
              <button
                type="button"
                className="flex min-h-11 w-full items-center justify-between gap-3 text-left text-sm font-bold"
              >
                <span className="min-w-0 truncate">[1] {designLabFixture.citation.title}</span>
                <ChevronRight className="shrink-0" size={17} />
              </button>
            </div>
          </section>

          <div className="mt-4 grid gap-3 lg:grid-cols-3">
            <StateCard icon={Loader2} label="Loading answer" detail="Searching policy evidence" />
            <StateCard icon={AlertCircle} label="Partial evidence" detail="Review limitations carefully" />
            <StateCard icon={ShieldAlert} label="Insufficient" detail="Contact authorised staff" />
          </div>

          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            <section className="rounded border border-[var(--lab-border)] bg-[var(--lab-surface)] p-4">
              <p className="font-black">Trust checklist</p>
              <label className="design-lab-muted mt-3 flex gap-2 text-xs">
                <input type="checkbox" checked readOnly /> I checked the evidence.
              </label>
              <label className="design-lab-muted mt-2 flex gap-2 text-xs">
                <input type="checkbox" readOnly /> I noticed uncertainty.
              </label>
            </section>
            <section className="rounded border border-[var(--lab-border)] bg-[var(--lab-surface)] p-4">
              <p className="font-black">Final decision</p>
              <div className="mt-3 h-12 rounded border border-[var(--lab-border)] bg-[var(--lab-recessed)]" />
              <LabChip tone="success">Response saved</LabChip>
            </section>
          </div>

          <div className="mt-4 rounded border border-[#b85c55] bg-[var(--lab-recessed)] p-4 text-sm">
            <p className="flex items-center gap-2 font-black text-[#d87970]">
              <LockKeyhole size={16} /> System failure state
            </p>
            <p className="design-lab-muted mt-2 leading-5">
              The study system is temporarily unavailable. Please pause this task and notify the researcher.
            </p>
          </div>
        </main>

        <aside className="design-lab-panel design-lab-inspector">
          <p className="text-xs font-black uppercase text-[var(--lab-accent)]">
            Evidence inspector
          </p>
          <p className={`mt-2 font-black leading-6 ${paper ? "font-serif" : ""}`}>
            {designLabFixture.citation.title}
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <LabChip>Official policy</LabChip>
            <LabChip>{designLabFixture.citation.page}</LabChip>
          </div>
          <blockquote className="mt-5 border-l-2 border-[var(--lab-accent)] bg-[var(--lab-recessed)] p-4 text-sm leading-6">
            {designLabFixture.citation.passage}
          </blockquote>
          <div className="mt-5 grid grid-cols-5 gap-1">
            {[1, 2, 3, 4, 5].map((value) => (
              <button
                key={value}
                type="button"
                className="grid h-9 place-items-center rounded border border-[var(--lab-border)] text-xs font-bold"
              >
                {value}
              </button>
            ))}
          </div>
          <button
            type="button"
            className="mt-4 min-h-11 w-full rounded bg-[var(--lab-accent)] px-3 text-sm font-bold text-white"
          >
            Mark source checked
          </button>

          <section className="mt-6 border-t border-[var(--lab-border)] pt-4">
            <p className="text-xs font-black uppercase text-[var(--lab-accent)]">
              Admin summary
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <MiniMetric label="Sessions" value="12" />
              <MiniMetric label="Complete" value="9" />
              <MiniMetric label="Evidence" value="31" />
              <MiniMetric label="Blocked" value="1" />
            </div>
          </section>
        </aside>
      </div>

      <footer className="border-t border-[var(--lab-border)] bg-[var(--lab-surface)] p-4">
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_190px]">
          <div>
            <p className="text-xs font-black uppercase text-[var(--lab-accent)]">
              Mobile behaviour
            </p>
            <p className="design-lab-muted mt-1 text-xs leading-5">
              The progress rail compacts into a horizontal step header and evidence opens as a full-height sheet; approved condition content is unchanged.
            </p>
          </div>
          <div className="rounded border border-[var(--lab-border)] bg-[var(--lab-recessed)] p-2">
            <div className="h-2 w-16 rounded bg-[var(--lab-accent)]" />
            <div className="mt-2 h-7 rounded border border-[var(--lab-border)] bg-[var(--lab-surface)]" />
            <div className="mt-2 h-12 rounded border border-[var(--lab-border)] bg-[var(--lab-surface)]" />
          </div>
        </div>
      </footer>
    </article>
  );
}

function StateCard({
  icon: Icon,
  label,
  detail,
}: {
  icon: typeof CircleDashed;
  label: string;
  detail: string;
}) {
  return (
    <div className="rounded border border-[var(--lab-border)] bg-[var(--lab-surface)] p-3">
      <Icon className="text-[var(--lab-accent)]" size={16} />
      <p className="mt-2 text-xs font-black">{label}</p>
      <p className="design-lab-muted mt-1 text-xs leading-5">{detail}</p>
    </div>
  );
}

function MiniMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-[var(--lab-border)] bg-[var(--lab-recessed)] p-2">
      <p className="design-lab-muted text-[10px] uppercase">{label}</p>
      <p className="mt-1 font-black">{value}</p>
    </div>
  );
}

export function DesignLab() {
  return (
    <div className="design-lab-root">
      <header className="workbench-topbar">
        <div>
          <p className="text-sm font-black">Uni-Navigator Design Lab</p>
          <p className="text-xs text-[var(--ui-text-muted)]">Synthetic fixtures only</p>
        </div>
        <AppearanceSwitcher />
      </header>
      <main className="workbench-page">
        <header className="workbench-context">
          <p className="text-xs font-black uppercase text-[var(--ui-accent-strong)]">
            Development preview
          </p>
          <h1 className="mt-2 text-3xl font-black">Three workbench directions</h1>
          <p className="mt-2 max-w-4xl text-sm leading-6 text-[var(--ui-text-secondary)]">
            These views use local synthetic content. They do not create sessions,
            call chat APIs, read participant data, or write study events.
          </p>
        </header>
        <EvidenceInspectorDemo />
        <div className="grid gap-8">
          {designDirections.map((direction) => (
            <DirectionPreview key={direction.id} direction={direction} />
          ))}
        </div>
      </main>
    </div>
  );
}
