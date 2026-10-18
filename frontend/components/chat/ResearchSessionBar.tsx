"use client";

import { useState } from "react";
import { CheckCircle2, Play, RotateCcw, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { useResearchSession } from "./useResearchSession";

export function ResearchSessionBar({ research, answering, onStarted }: {
  research: ReturnType<typeof useResearchSession>;
  answering: boolean;
  onStarted: () => void;
}) {
  const [round, setRound] = useState("");
  const [participant, setParticipant] = useState("");
  const [consent, setConsent] = useState(false);
  const active = research.session?.state === "active";
  const inputClass = "mt-1 w-full rounded-md border border-[var(--border-light)] bg-white px-3 py-2 text-sm";
  return <section aria-label="Research session" className="mb-5 border-y border-[var(--border-light)] py-4">
    {active ? <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="min-w-0 break-words text-sm">
        <strong>{research.session?.roundId} / {research.session?.participantLabel}</strong>
        <p className="text-[var(--text-secondary)]">{research.session?.executionContext === "participant_study" ? "Participant study" : "Development test"} · Active</p>
      </div>
      <Button variant="secondary" disabled={answering || research.busy || !research.ready} onClick={() => void research.end()}>
        <Square size={16} />{research.busy ? "Saving..." : "End test"}
      </Button>
    </div> : <details open={Boolean(research.session)}>
      <summary className="cursor-pointer text-sm font-bold">Researcher setup{research.session?.completedAt ? " · Test ended" : " · Self-test"}</summary>
      <form className="mt-3 grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end" onSubmit={async (event) => {
        event.preventDefault();
        onStarted();
        setConsent(false);
        await research.start(round.trim(), participant.trim(), consent);
      }}>
        <label className="text-sm font-bold">Test round
          <input className={inputClass} value={round} onChange={e => setRound(e.target.value)} placeholder="pilot-01" required pattern="[A-Za-z0-9][A-Za-z0-9_-]{0,39}" disabled={research.busy} />
        </label>
        <label className="text-sm font-bold">Participant code
          <input className={inputClass} value={participant} onChange={e => setParticipant(e.target.value.toUpperCase())} placeholder="P01" required pattern="P[0-9]{2,6}" disabled={research.busy} />
        </label>
        <Button type="submit" disabled={!research.ready || research.busy || answering || research.pending > 0 || !consent}>
          <Play size={16} />{research.busy ? "Starting..." : "Start test"}
        </Button>
        <label className="flex items-start gap-2 text-sm sm:col-span-3">
          <input type="checkbox" className="mt-1" checked={consent} onChange={e => setConsent(e.target.checked)} required />
          Participant information and consent completed
        </label>
      </form>
    </details>}
    <div className="mt-2 text-sm" aria-live="polite">
      {research.pending > 0 && <div role={research.failed ? "alert" : "status"} className={research.failed ? "text-red-700" : "text-[var(--text-secondary)]"}>
        {research.pending} pending {research.pending === 1 ? "save" : "saves"}{research.failed ? " · Save failed" : " · Saving..."}
        <Button size="sm" variant="ghost" disabled={research.busy} onClick={() => void research.retry()}><RotateCcw size={16} />Retry saves</Button>
      </div>}
      {active && research.pending === 0 && <span className="flex items-center gap-2 text-[var(--ui-success)]"><CheckCircle2 size={16} />All queued activity saved</span>}
      {research.error && <div role="alert" className="text-red-700">{research.error}{!research.ready && <Button variant="ghost" onClick={() => void research.restore()}>Retry connection</Button>}</div>}
    </div>
  </section>;
}
