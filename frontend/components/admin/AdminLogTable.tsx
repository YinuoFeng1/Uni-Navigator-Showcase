"use client";

import { useMemo, useState } from "react";
import { ExportButton } from "@/components/admin/ExportButton";
import { Badge } from "@/components/ui/badge";
import { Label, Select } from "@/components/ui/form";
import { studyConditionLabels } from "@/lib/constants";
import { mockAdminLogs } from "@/lib/mockData";
import type { StudyCondition } from "@/lib/types";

export function AdminLogTable() {
  const [filter, setFilter] = useState<StudyCondition | "ALL">("ALL");
  const logs = useMemo(
    () =>
      filter === "ALL"
        ? mockAdminLogs
        : mockAdminLogs.filter((log) => log.condition === filter),
    [filter],
  );

  return (
    <section className="rounded-lg border border-[var(--border-light)] bg-white">
      <div className="flex flex-col gap-4 border-b border-[var(--border-light)] p-5 md:flex-row md:items-end md:justify-between">
        <div>
          <h2 className="text-xl font-black">Interaction log</h2>
          <p className="mt-1 text-sm text-[var(--text-secondary)]">
            Mock research data for dashboard layout and export testing.
          </p>
        </div>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
          <div className="grid gap-2">
            <Label htmlFor="condition-filter">Condition filter</Label>
            <Select
              id="condition-filter"
              value={filter}
              onChange={(event) => setFilter(event.target.value as StudyCondition | "ALL")}
              className="min-w-56"
            >
              <option value="ALL">All conditions</option>
              {Object.entries(studyConditionLabels).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </Select>
          </div>
          <ExportButton logs={logs} />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[980px] border-collapse text-left text-sm">
          <thead className="bg-[var(--background-soft)] text-xs uppercase tracking-[0.12em] text-[var(--text-secondary)]">
            <tr>
              <th className="px-4 py-3">Participant ID</th>
              <th className="px-4 py-3">Condition</th>
              <th className="px-4 py-3">Task ID</th>
              <th className="px-4 py-3">Question</th>
              <th className="px-4 py-3">Citation clicked</th>
              <th className="px-4 py-3">Evidence opened</th>
              <th className="px-4 py-3">Pre</th>
              <th className="px-4 py-3">Post</th>
              <th className="px-4 py-3">Time</th>
              <th className="px-4 py-3">Feedback</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border-light)]">
            {logs.map((log) => (
              <tr key={log.id} className="align-top">
                <td className="px-4 py-4 font-bold">{log.participantId}</td>
                <td className="px-4 py-4">
                  <Badge tone="purple">{log.condition.replace("_", " ")}</Badge>
                </td>
                <td className="px-4 py-4 text-[var(--text-secondary)]">{log.taskId}</td>
                <td className="px-4 py-4">{log.question}</td>
                <td className="px-4 py-4">{log.citationClicked ? "Yes" : "No"}</td>
                <td className="px-4 py-4">{log.evidenceOpened ? "Yes" : "No"}</td>
                <td className="px-4 py-4">{log.preConfidence}</td>
                <td className="px-4 py-4">{log.postConfidence}</td>
                <td className="px-4 py-4">{log.timeTaken}</td>
                <td className="px-4 py-4 text-[var(--text-secondary)]">{log.feedback}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
