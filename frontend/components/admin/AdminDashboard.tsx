"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  Database,
  RefreshCw,
  Search,
  ShieldAlert,
  Wifi,
} from "lucide-react";
import { ExportButton } from "@/components/admin/ExportButton";
import { ResearchExports } from "@/components/admin/ResearchExports";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { StatusChip, SystemStatusBar } from "@/components/ui/status";
import {
  fetchAdminCorpusStatus,
  fetchAdminPilotPreflight,
  fetchAdminSessionDetail,
  fetchAdminSessions,
  fetchAdminTasks,
} from "@/lib/api";
import type {
  AdminCorpusStatus,
  AdminPilotPreflight,
  AdminPreflightCheck,
  AdminSessionDetail,
  AdminSessionSummary,
  AdminTaskSummary,
  AdminTrustChecklistSummary,
} from "@/lib/types";
import { cn } from "@/lib/utils";

function formatDate(value?: string | null) {
  if (!value) return "-";
  return new Date(value).toLocaleString();
}

function yesNo(value?: boolean | null) {
  if (value === true) return "Yes";
  if (value === false) return "No";
  return "-";
}

function trustSummaryText(summary?: AdminTrustChecklistSummary | null) {
  if (!summary) return "No checklist";
  const checked = [
    summary.answerClear,
    summary.evidenceChecked,
    summary.sourceSupportsAnswer,
    summary.uncertaintyNoticed,
    summary.wouldContactStaffIfNeeded,
  ].filter(Boolean).length;
  return `${checked}/5 checked`;
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border border-[var(--border-light)] bg-white p-4">
      <p className="text-xs font-black uppercase tracking-[0.12em] text-[var(--text-secondary)]">
        {label}
      </p>
      <p className="mt-2 text-2xl font-black text-[var(--text-primary)]">{value}</p>
    </div>
  );
}

function preflightCheckName(check: AdminPreflightCheck) {
  const identifier = check.check_id ?? check.checkId ?? check.check ?? "preflight check";
  return identifier.replaceAll("_", " ");
}

function PilotReadinessPanel({
  preflight,
  loading,
}: {
  preflight: AdminPilotPreflight | null;
  loading: boolean;
}) {
  const failedChecks =
    preflight?.checks.filter((check) => check.status.toUpperCase() === "FAIL") ?? [];
  const passedCount =
    preflight?.checks.filter((check) => check.status.toUpperCase() === "PASS").length ??
    0;

  return (
    <section
      className="min-w-0 rounded-[var(--radius-md)] border border-[var(--ui-border-subtle)] bg-[var(--ui-surface-elevated)] p-4"
      aria-labelledby="pilot-readiness-heading"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 id="pilot-readiness-heading" className="text-base font-black">
            Pilot readiness
          </h2>
          <p className="mt-1 text-sm text-[var(--ui-text-secondary)]">
            Review failed checks before opening a participant session.
          </p>
        </div>
        <StatusChip
          label={
            loading && preflight === null
              ? "Checking"
              : preflight === null
              ? "Unavailable"
              : preflight.ok
                ? "All checks passed"
                : `${failedChecks.length} failed`
          }
          tone={
            loading && preflight === null
              ? "neutral"
              : preflight === null
                ? "danger"
                : preflight.ok
                  ? "success"
                  : "warning"
          }
          icon={preflight?.ok ? CheckCircle2 : ShieldAlert}
        />
      </div>

      {loading && preflight === null ? (
        <p className="mt-4 text-sm text-[var(--ui-text-secondary)]" role="status">
          Checking pilot readiness...
        </p>
      ) : preflight === null ? (
        <p className="mt-4 text-sm font-bold text-[var(--ui-danger)]" role="alert">
          Preflight details are unavailable. Refresh after confirming the backend is
          running.
        </p>
      ) : preflight.ok ? (
        <p className="mt-4 text-sm text-[var(--ui-text-secondary)]">
          {passedCount} checks passed. The release gate is ready.
        </p>
      ) : (
        <div className="mt-4">
          <p className="text-xs font-black uppercase text-[var(--ui-text-muted)]">
            {passedCount} passed / {failedChecks.length} failed
          </p>
          <ul className="mt-3 grid min-w-0 gap-2">
            {failedChecks.map((check, index) => {
              const identifier =
                check.check_id ?? check.checkId ?? check.check ?? `check-${index}`;
              const detail = check.safe_detail ?? check.safeDetail ?? check.detail;
              const action =
                check.researcher_action ??
                check.researcherAction ??
                "Review this check before participant activation.";
              return (
                <li
                  key={`${identifier}-${index}`}
                  className="min-w-0 rounded-[var(--radius-md)] border border-[var(--ui-warning)] bg-[var(--ui-warning-subtle)] p-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="font-bold capitalize text-[var(--ui-text-primary)]">
                      {preflightCheckName(check)}
                    </p>
                    <span className="text-xs font-black uppercase text-[var(--ui-warning)]">
                      {check.severity ?? "critical"}
                    </span>
                  </div>
                  {check.message ? (
                    <p className="mt-1 break-words text-sm text-[var(--ui-text-secondary)]">
                      {check.message}
                    </p>
                  ) : null}
                  {detail ? (
                    <code className="mono-metadata mt-2 block break-all text-[var(--ui-text-secondary)]">
                      {detail}
                    </code>
                  ) : null}
                  <p className="mt-2 break-words text-sm font-bold text-[var(--ui-text-primary)]">
                    Action: {action}
                  </p>
                </li>
              );
            })}
          </ul>
        </div>
      )}
    </section>
  );
}

export function AdminDashboard({ workbench = false }: { workbench?: boolean }) {
  const [sessions, setSessions] = useState<AdminSessionSummary[]>([]);
  const [tasks, setTasks] = useState<AdminTaskSummary[]>([]);
  const [selectedSessionId, setSelectedSessionId] = useState<string | null>(null);
  const [sessionDetail, setSessionDetail] = useState<AdminSessionDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isStatusLoading, setIsStatusLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [corpusStatus, setCorpusStatus] = useState<AdminCorpusStatus | null>(null);
  const [preflight, setPreflight] = useState<AdminPilotPreflight | null>(null);

  async function loadDashboard() {
    setIsLoading(true);
    setIsStatusLoading(true);
    setError("");
    const [summariesResult, statusResult] = await Promise.allSettled([
      Promise.all([fetchAdminSessions(), fetchAdminTasks()]),
      Promise.all([fetchAdminCorpusStatus(), fetchAdminPilotPreflight()]),
    ]);
    const errors: string[] = [];

    if (summariesResult.status === "fulfilled") {
      const [sessionsResponse, tasksResponse] = summariesResult.value;
      setSessions(sessionsResponse.items);
      setTasks(tasksResponse.items);
      setSelectedSessionId((current) =>
        current && sessionsResponse.items.some((item) => item.sessionId === current)
          ? current
          : (sessionsResponse.items[0]?.sessionId ?? null),
      );
    } else {
      console.warn("Failed to load admin dashboard", summariesResult.reason);
      errors.push("Could not refresh backend admin summaries.");
    }

    if (statusResult.status === "fulfilled") {
      const [corpus, readiness] = statusResult.value;
      setCorpusStatus(corpus);
      setPreflight(readiness);
    } else {
      console.warn("Failed to load admin system status", statusResult.reason);
      setCorpusStatus(null);
      setPreflight(null);
      errors.push("System readiness is unavailable.");
    }

    setError(errors.join(" "));
    setIsStatusLoading(false);
    setIsLoading(false);
  }

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchAdminSessions(), fetchAdminTasks()])
      .then(([sessionsResponse, tasksResponse]) => {
        if (cancelled) return;
        setSessions(sessionsResponse.items);
        setTasks(tasksResponse.items);
        setSelectedSessionId(sessionsResponse.items[0]?.sessionId ?? null);
      })
      .catch((loadError) => {
        console.warn("Failed to load admin dashboard", loadError);
        if (!cancelled) setError("Could not load backend admin summaries.");
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchAdminCorpusStatus(), fetchAdminPilotPreflight()])
      .then(([corpus, readiness]) => {
        if (cancelled) return;
        setCorpusStatus(corpus);
        setPreflight(readiness);
      })
      .catch((statusError) => {
        console.warn("Failed to load admin system status", statusError);
        if (!cancelled) {
          setCorpusStatus(null);
          setPreflight(null);
          setError((current) =>
            current
              ? `${current} System readiness is unavailable.`
              : "System readiness is unavailable.",
          );
        }
      })
      .finally(() => {
        if (!cancelled) setIsStatusLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedSessionId) {
      return;
    }
    let cancelled = false;
    fetchAdminSessionDetail(selectedSessionId)
      .then((detail) => {
        if (!cancelled) setSessionDetail(detail);
      })
      .catch((detailError) => {
        console.warn("Failed to load session detail", detailError);
        if (!cancelled) setSessionDetail(null);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedSessionId]);

  const totals = useMemo(
    () => ({
      sessions: sessions.length,
      completed: sessions.filter((session) => session.completedAt).length,
      interactions: sessions.reduce((sum, session) => sum + session.interactionCount, 0),
      finalResponses: sessions.reduce(
        (sum, session) => sum + session.finalResponseCount,
        0,
      ),
      evidenceActions: sessions.reduce(
        (sum, session) => sum + session.evidenceUseCount,
        0,
      ),
    }),
    [sessions],
  );
  const filteredSessions = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return sessions;
    return sessions.filter(
      (session) =>
        session.participantLabel.toLowerCase().includes(normalized) ||
        session.sessionId.toLowerCase().includes(normalized) ||
        session.studyCondition?.toLowerCase().includes(normalized),
    );
  }, [query, sessions]);

  return (
    <div className={cn("grid min-w-0 gap-6", workbench && "admin-workbench")}>
      {workbench ? (
        <SystemStatusBar
          className="min-w-0"
          items={[
            {
              label: corpusStatus
                ? "Backend connected"
                : isStatusLoading
                  ? "Checking backend"
                  : "Status unavailable",
              tone: corpusStatus ? "success" : isStatusLoading ? "neutral" : "danger",
              icon: corpusStatus ? Wifi : ShieldAlert,
            },
            {
              label: corpusStatus?.vectorStoreProviderActive
                ? `Vector: ${corpusStatus.vectorStoreProviderActive}`
                : "Vector: unknown",
              tone: corpusStatus?.fallbackUsed ? "warning" : "neutral",
              icon: Database,
            },
            {
              label:
                isStatusLoading && preflight === null
                  ? "Checking preflight"
                  : preflight === null
                  ? "Preflight unavailable"
                  : preflight.ok
                    ? "Pilot preflight passed"
                    : "Pilot not ready",
              tone:
                isStatusLoading && preflight === null
                  ? "neutral"
                  : preflight === null
                    ? "danger"
                    : preflight.ok
                      ? "success"
                      : "warning",
              icon: ShieldAlert,
            },
          ]}
        />
      ) : null}
      <section className="min-w-0 rounded-lg border border-[var(--border-light)] bg-[var(--warning-soft)] p-5">
        <div className="flex min-w-0 flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0 flex-1">
            <Badge tone="gold">Local prototype only</Badge>
            <h2 className="mt-3 text-xl font-black">
              Local research monitoring dashboard.
            </h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-[var(--text-secondary)]">
              Protect before deployment. Raw logs may contain participant-entered
              free text and must be handled according to the approved ethics and
              data management process. Participant labels are study codes, and
              final decision text is truncated by default.
            </p>
          </div>
          <div className="grid min-w-0 shrink-0 gap-3 lg:max-w-[42rem] lg:grid-cols-[auto_minmax(0,1fr)] lg:items-start">
            <Button type="button" variant="secondary" onClick={loadDashboard}>
              <RefreshCw size={17} aria-hidden="true" />
              Refresh
            </Button>
            <ExportButton />
          </div>
        </div>
      </section>

      <ResearchExports />
      {error ? (
        <div
          className="rounded-lg border border-[var(--ui-danger)] bg-[var(--ui-danger-subtle)] p-5 text-sm font-bold text-[var(--ui-danger)]"
          role="alert"
        >
          {error}
        </div>
      ) : null}

      <section className="grid min-w-0 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Stat label="Sessions" value={totals.sessions} />
        <Stat label="Completed" value={totals.completed} />
        <Stat label="Interactions" value={totals.interactions} />
        <Stat label="Evidence actions" value={totals.evidenceActions} />
        <Stat label="Final responses" value={totals.finalResponses} />
      </section>

      {workbench ? (
        <section className="grid min-w-0 gap-3 rounded-[var(--radius-md)] border border-[var(--ui-border-subtle)] bg-[var(--ui-surface-elevated)] p-4 md:grid-cols-3">
          <div>
            <p className="text-xs font-black uppercase text-[var(--ui-text-muted)]">Corpus</p>
            <p className="mono-metadata mt-2 text-[var(--ui-text-primary)]">
              {corpusStatus?.sourceCount ?? "-"} sources / {corpusStatus?.chunkCount ?? "-"} chunks
            </p>
          </div>
          <div>
            <p className="text-xs font-black uppercase text-[var(--ui-text-muted)]">Collection</p>
            <p className="mono-metadata mt-2 break-all text-[var(--ui-text-primary)]">
              {corpusStatus?.vectorStoreCollection ?? "Unavailable"}
            </p>
          </div>
          <div>
            <p className="text-xs font-black uppercase text-[var(--ui-text-muted)]">Release gate</p>
            <div className="mt-2">
              <StatusChip
                label={preflight?.ok ? "Ready" : "Review required"}
                tone={preflight?.ok ? "success" : "warning"}
              />
            </div>
          </div>
        </section>
      ) : null}

      {workbench ? (
        <PilotReadinessPanel preflight={preflight} loading={isStatusLoading} />
      ) : null}

      <section className="min-w-0 rounded-lg border border-[var(--border-light)] bg-white">
        <div className="flex flex-col gap-3 border-b border-[var(--border-light)] p-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <h2 className="text-xl font-black">Session overview</h2>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Monitor study progress and data quality before CSV export.
            </p>
          </div>
          <div className="flex min-w-0 items-center gap-2">
            <label className="relative block min-w-0 flex-1 sm:flex-none">
              <span className="sr-only">Filter sessions</span>
              <Search
                className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-secondary)]"
                size={16}
                aria-hidden="true"
              />
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Filter sessions"
                className="h-10 w-full min-w-0 rounded-md border border-[var(--border-light)] bg-white pl-9 pr-3 text-sm sm:w-64"
              />
            </label>
            {isLoading ? <Badge tone="purple">Loading</Badge> : null}
          </div>
        </div>
        {sessions.length === 0 ? (
          <p className="p-5 text-sm text-[var(--text-secondary)]">
            No study sessions recorded yet.
          </p>
        ) : (
          <div className={cn("overflow-x-auto", workbench && "admin-table-frame")}>
            <table className="w-full min-w-[1240px] border-collapse text-left text-sm">
              <thead className="bg-[var(--background-soft)] text-xs uppercase tracking-[0.12em] text-[var(--text-secondary)]">
                <tr>
                  <th className="px-4 py-3">Participant code</th>
                  <th className="px-4 py-3">Condition</th>
                  <th className="px-4 py-3">Notice</th>
                  <th className="px-4 py-3">Started</th>
                  <th className="px-4 py-3">Completed</th>
                  <th className="px-4 py-3">Tasks</th>
                  <th className="px-4 py-3">Interactions</th>
                  <th className="px-4 py-3">Evidence</th>
                  <th className="px-4 py-3">Source checked</th>
                  <th className="px-4 py-3">Final responses</th>
                  <th className="px-4 py-3">Trust</th>
                  <th className="px-4 py-3">Warnings</th>
                  <th className="px-4 py-3">Last activity</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-light)]">
                {filteredSessions.map((session) => (
                  <tr
                    key={session.sessionId}
                    className="cursor-pointer align-top hover:bg-[var(--background-soft)]"
                    onClick={() => setSelectedSessionId(session.sessionId)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        setSelectedSessionId(session.sessionId);
                      }
                    }}
                    tabIndex={0}
                    aria-selected={selectedSessionId === session.sessionId}
                  >
                    <td className="px-4 py-4 font-bold">{session.participantLabel}</td>
                    <td className="px-4 py-4">{session.studyCondition ?? "-"}</td>
                    <td className="px-4 py-4">
                      {yesNo(session.prototypeNoticeAcknowledged)}
                    </td>
                    <td className="px-4 py-4">{formatDate(session.startedAt)}</td>
                    <td className="px-4 py-4">{formatDate(session.completedAt)}</td>
                    <td className="px-4 py-4">
                      {session.tasksStartedCount}/{session.tasksCompletedCount}
                    </td>
                    <td className="px-4 py-4">{session.interactionCount}</td>
                    <td className="px-4 py-4">{session.evidenceUseCount}</td>
                    <td className="px-4 py-4">{session.sourceCheckedCount}</td>
                    <td className="px-4 py-4">{session.finalResponseCount}</td>
                    <td className="px-4 py-4">
                      {trustSummaryText(session.latestTrustChecklistSummary)}
                    </td>
                    <td className="px-4 py-4">
                      {session.sensitiveWarningShownCount ?? 0}
                    </td>
                    <td className="px-4 py-4">{formatDate(session.lastActivityAt)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="admin-split-panel grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <div className="min-w-0 rounded-lg border border-[var(--border-light)] bg-white">
          <div className="border-b border-[var(--border-light)] p-5">
            <h2 className="text-xl font-black">Task summary</h2>
          </div>
          <div className={cn("overflow-x-auto", workbench && "admin-table-frame")}>
            <table className="w-full min-w-[980px] border-collapse text-left text-sm">
              <thead className="bg-[var(--background-soft)] text-xs uppercase tracking-[0.12em] text-[var(--text-secondary)]">
                <tr>
                  <th className="px-4 py-3">Task title</th>
                  <th className="px-4 py-3">Type</th>
                  <th className="px-4 py-3">Difficulty</th>
                  <th className="px-4 py-3">Escalation</th>
                  <th className="px-4 py-3">Sessions</th>
                  <th className="px-4 py-3">Final</th>
                  <th className="px-4 py-3">Avg confidence</th>
                  <th className="px-4 py-3">Contact staff</th>
                  <th className="px-4 py-3">Evidence</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border-light)]">
                {tasks.map((task) => (
                  <tr key={task.taskId} className="align-top">
                    <td className="px-4 py-4 font-bold">{task.title}</td>
                    <td className="px-4 py-4">{task.taskType}</td>
                    <td className="px-4 py-4">{task.difficulty}</td>
                    <td className="px-4 py-4">
                      {task.escalationExpected ? "Expected" : "Optional"}
                    </td>
                    <td className="px-4 py-4">
                      {task.sessionsStartedCount}/{task.sessionsCompletedCount}
                    </td>
                    <td className="px-4 py-4">{task.finalResponseCount}</td>
                    <td className="px-4 py-4">{task.averageConfidence ?? "-"}</td>
                    <td className="px-4 py-4">
                      Y {task.contactStaffYesCount} / N {task.contactStaffNoCount} / ?{" "}
                      {task.contactStaffUnsureCount}
                    </td>
                    <td className="px-4 py-4">
                      <span className="block">{task.evidenceUseCount} evidence actions</span>
                      <span className="mt-1 block text-[var(--text-secondary)]">
                        {task.trustChecklistCount} checklist
                        {task.trustChecklistCount === 1 ? "" : "s"} /{" "}
                        {task.trustSnapshotCount} updates
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <SessionDetailPanel detail={sessionDetail} />
      </section>
    </div>
  );
}

function SessionDetailPanel({ detail }: { detail: AdminSessionDetail | null }) {
  if (!detail) {
    return (
      <aside className="min-w-0 rounded-lg border border-[var(--border-light)] bg-white p-5">
        <h2 className="text-xl font-black">Session detail</h2>
        <p className="mt-3 text-sm text-[var(--text-secondary)]">
          Select a session to inspect study progress, trust checklist values, and a
          privacy-preserving final response summary.
        </p>
      </aside>
    );
  }

  const { summary } = detail;

  return (
    <aside className="grid min-w-0 content-start gap-5 rounded-lg border border-[var(--border-light)] bg-white p-5">
      <div>
        <h2 className="text-xl font-black">Session detail</h2>
        <p className="mt-1 text-sm text-[var(--text-secondary)]">
          {summary.participantLabel} · {summary.completedAt ? "Completed" : "Active"}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3 text-sm">
        <Stat label="Interactions" value={summary.interactionCount} />
        <Stat label="Evidence" value={summary.evidenceUseCount} />
        <Stat label="Source checked" value={summary.sourceCheckedCount} />
        <Stat label="Final responses" value={summary.finalResponseCount} />
      </div>

      <div className="rounded-lg bg-[var(--background-soft)] p-4 text-sm leading-6">
        <p className="font-black">Task progress</p>
        <p className="text-[var(--text-secondary)]">
          Started: {detail.taskProgress.startedTaskIds.join(", ") || "-"}
        </p>
        <p className="text-[var(--text-secondary)]">
          Completed: {detail.taskProgress.completedTaskIds.join(", ") || "-"}
        </p>
      </div>

      <div>
        <p className="mb-2 text-sm font-black">Latest trust checklist</p>
        <div className="grid gap-1 text-sm text-[var(--text-secondary)]">
          <p>Answer clear: {yesNo(detail.latestTrustChecklist?.answerClear)}</p>
          <p>Evidence checked: {yesNo(detail.latestTrustChecklist?.evidenceChecked)}</p>
          <p>
            Source supports answer:{" "}
            {yesNo(detail.latestTrustChecklist?.sourceSupportsAnswer)}
          </p>
          <p>
            Uncertainty noticed: {yesNo(detail.latestTrustChecklist?.uncertaintyNoticed)}
          </p>
          <p>
            Contact staff if needed:{" "}
            {yesNo(detail.latestTrustChecklist?.wouldContactStaffIfNeeded)}
          </p>
        </div>
      </div>

      <div>
        <p className="mb-2 text-sm font-black">Final response summary</p>
        {detail.finalResponses.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">No final response yet.</p>
        ) : (
          <div className="grid gap-3">
            {detail.finalResponses.map((response) => (
              <div
                key={response.responseId}
                className="rounded-lg border border-[var(--border-light)] p-3 text-sm"
              >
                <p className="font-bold">Task: {response.taskId}</p>
                <p className="mt-1 text-[var(--text-secondary)]">
                  Confidence {response.confidenceRating}; support{" "}
                  {response.perceivedAnswerSupported}; contact staff{" "}
                  {response.wouldContactStaff}
                </p>
                <details className="mt-2 text-[var(--text-secondary)]">
                  <summary className="cursor-pointer font-bold">
                    Show truncated decision preview
                  </summary>
                  <p className="mt-2">{response.finalDecisionPreview}</p>
                </details>
                <p className="mt-1 text-xs text-[var(--text-secondary)]">
                  Length: {response.finalDecisionLength} characters
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div>
        <p className="mb-2 text-sm font-black">Major event timeline</p>
        {detail.eventTimeline.length === 0 ? (
          <p className="text-sm text-[var(--text-secondary)]">No events yet.</p>
        ) : (
          <ul className="max-h-72 overflow-auto rounded-lg border border-[var(--border-light)]">
            {detail.eventTimeline.map((event) => (
              <li
                key={event.eventId}
                className="border-b border-[var(--border-light)] p-3 text-xs last:border-b-0"
              >
                <p className="font-black text-[var(--uq-purple)]">{event.eventType}</p>
                <p className="mt-1 text-[var(--text-secondary)]">
                  {formatDate(event.createdAt)}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
