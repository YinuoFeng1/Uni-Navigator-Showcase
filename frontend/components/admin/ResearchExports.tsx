"use client";

import { useEffect, useState } from "react";
import { Download, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { exportResearch, listResearchSessions } from "@/lib/researchSessionApi";
import type { ResearchSessionSummary } from "@/lib/types";

export function ResearchExports() {
  const [items, setItems] = useState<ResearchSessionSummary[]>([]);
  const [round, setRound] = useState("");
  const [participant, setParticipant] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  async function refresh() {
    setBusy(true); setError("");
    try { setItems((await listResearchSessions()).items); }
    catch { setError("Session list could not load. Retry refresh."); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    let cancelled = false;
    listResearchSessions().then(result => {
      if (!cancelled) setItems(result.items);
    }).catch(() => {
      if (!cancelled) setError("Session list could not load. Retry refresh.");
    }).finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, []);
  const filtered = items.filter(item => (!round || item.round_id === round) && (!participant || item.participant_code === participant));
  const rounds = [...new Set(items.map(item => item.round_id))].sort();
  const participants = [...new Set(items.filter(item => !round || item.round_id === round).map(item => item.participant_code))].sort();
  async function download(kind: "participants" | "timeline" | "answers") {
    setBusy(true); setError(""); setMessage("");
    try {
      const blob = await exportResearch(kind, { round_id: round, participant });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `uni_navigator_${round || "all-rounds"}_${participant || "all-participants"}_${kind}.csv`;
      anchor.click(); URL.revokeObjectURL(url);
      setMessage("Export downloaded.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Export failed. Retry."); }
    finally { setBusy(false); }
  }
  return <section className="min-w-0 border-y border-[var(--border-light)] py-5" aria-label="Chat study exports">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <h2 className="text-lg font-bold">Chat study exports</h2>
      <Button variant="ghost" size="sm" disabled={busy} onClick={() => void refresh()}><RefreshCw size={16} />Refresh</Button>
    </div>
    <div className="my-3 grid gap-3 sm:grid-cols-2">
      <label className="text-sm font-bold">Test round
        <select value={round} onChange={e => { setRound(e.target.value); setParticipant(""); }} className="mt-1 w-full rounded-md border p-2" disabled={busy}>
          <option value="">All rounds</option>{rounds.map(value => <option key={value}>{value}</option>)}
        </select>
      </label>
      <label className="text-sm font-bold">Participant code
        <select value={participant} onChange={e => setParticipant(e.target.value)} className="mt-1 w-full rounded-md border p-2" disabled={busy}>
          <option value="">All participants</option>{participants.map(value => <option key={value}>{value}</option>)}
        </select>
      </label>
    </div>
    <div className="flex flex-wrap gap-2">
      {([ ["participants", "Participant summary"], ["timeline", "Activity timeline"], ["answers", "Questions and answers"] ] as const).map(([kind, label]) =>
        <Button key={kind} size="sm" variant="secondary" disabled={busy || !filtered.length} onClick={() => void download(kind)}><Download size={16} />{label}</Button>)}
    </div>
    {error && <p role="alert" className="mt-2 text-sm text-red-700">{error}</p>}
    {message && <p role="status" className="mt-2 text-sm text-[var(--ui-success)]">{message}</p>}
    <p className="my-3 text-sm text-[var(--text-secondary)]">{filtered.length} {filtered.length === 1 ? "session" : "sessions"}</p>
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead><tr>{["Round", "Participant", "Environment", "State", "Started", "Answers", "Source opens"].map(label => <th key={label} className="whitespace-nowrap border-b p-2">{label}</th>)}</tr></thead>
        <tbody>{filtered.map(item => <tr key={item.session_id}>
          <td className="p-2">{item.round_id}</td><td className="p-2">{item.participant_code}</td>
          <td className="p-2">{item.execution_context === "participant_study" ? "Participant study" : "Development"}</td>
          <td className="p-2">{item.state}</td><td className="whitespace-nowrap p-2">{new Date(item.started_at).toLocaleString()}</td>
          <td className="p-2">{item.answer_count}</td><td className="p-2">{item.source_open_count}</td>
        </tr>)}</tbody>
      </table>
    </div>
  </section>;
}
