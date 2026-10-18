"use client";

import { useState } from "react";
import { AlertCircle, CheckCircle2, Download, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  downloadAdminLogsCsv,
  downloadAdminSessionSummaryCsv,
  downloadAdminTaskSummaryCsv,
} from "@/lib/api";

type ExportOption = {
  label: string;
  description: string;
  filename: string;
  download: () => Promise<Blob>;
};

type ExportStatus = {
  tone: "success" | "warning" | "danger";
  message: string;
};

const statusClasses: Record<ExportStatus["tone"], string> = {
  success: "text-[var(--ui-success)]",
  warning: "text-[var(--ui-warning)]",
  danger: "text-[var(--ui-danger)]",
};

export function ExportButton() {
  const [pendingFilename, setPendingFilename] = useState<string | null>(null);
  const [status, setStatus] = useState<ExportStatus | null>(null);

  function downloadBlob(blob: Blob, filename: string) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  const exportOptions: ExportOption[] = [
    {
      label: "Export Raw Logs CSV",
      description: "Detailed research data; may include participant-entered free text",
      filename: "uni_navigator_logs.csv",
      download: downloadAdminLogsCsv,
    },
    {
      label: "Export Session Summary CSV",
      description: "One row per participant session",
      filename: "uni_navigator_session_summary.csv",
      download: downloadAdminSessionSummaryCsv,
    },
    {
      label: "Export Task Summary CSV",
      description: "One row per session-task pair",
      filename: "uni_navigator_task_summary.csv",
      download: downloadAdminTaskSummaryCsv,
    },
  ];

  async function exportCsv(option: ExportOption) {
    setPendingFilename(option.filename);
    setStatus(null);
    try {
      const backendCsv = await option.download();
      downloadBlob(backendCsv, option.filename);
      setStatus({
        tone: "success",
        message: `${option.label} downloaded.`,
      });
    } catch (error) {
      console.warn(`Failed to download ${option.filename}.`, error);
      setStatus({
        tone: "danger",
        message: `${option.label} failed. No file was created; check the backend and retry.`,
      });
    } finally {
      setPendingFilename(null);
    }
  }

  return (
    <div className="grid min-w-0 max-w-full gap-2">
      {exportOptions.map((option) => (
        <div
          key={option.filename}
          className="grid min-w-0 gap-1 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center sm:gap-3"
        >
          <p className="min-w-0 break-words text-xs font-bold text-[var(--text-secondary)] sm:text-right">
            {option.description}
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="w-full sm:w-auto"
            onClick={() => void exportCsv(option)}
            disabled={pendingFilename !== null}
          >
            {pendingFilename === option.filename ? (
              <Loader2 className="animate-spin" size={16} aria-hidden="true" />
            ) : (
              <Download size={16} aria-hidden="true" />
            )}
            {option.label}
          </Button>
        </div>
      ))}
      {status ? (
        <div
          className={`flex min-w-0 items-start gap-2 text-xs font-bold leading-5 ${statusClasses[status.tone]}`}
          role={status.tone === "danger" ? "alert" : "status"}
          aria-live="polite"
        >
          {status.tone === "success" ? (
            <CheckCircle2 className="mt-0.5 shrink-0" size={15} aria-hidden="true" />
          ) : (
            <AlertCircle className="mt-0.5 shrink-0" size={15} aria-hidden="true" />
          )}
          <span className="min-w-0 break-words">{status.message}</span>
        </div>
      ) : null}
    </div>
  );
}
