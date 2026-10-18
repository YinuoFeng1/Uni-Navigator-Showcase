import type { LucideIcon } from "lucide-react";
import {
  AlertCircle,
  Check,
  CheckCircle2,
  CircleDashed,
  FileCheck2,
  HelpCircle,
  Info,
  Loader2,
  ShieldAlert,
  Wifi,
  WifiOff,
} from "lucide-react";
import { cn } from "@/lib/utils";

type StatusTone =
  | "neutral"
  | "accent"
  | "success"
  | "warning"
  | "danger"
  | "uncertainty";

const toneClasses: Record<StatusTone, string> = {
  neutral:
    "border-[var(--ui-border-subtle)] bg-[var(--ui-surface-recessed)] text-[var(--ui-text-secondary)]",
  accent:
    "border-[var(--ui-accent)] bg-[var(--ui-accent-subtle)] text-[var(--ui-accent-strong)]",
  success:
    "border-[var(--ui-success)] bg-[var(--ui-success-subtle)] text-[var(--ui-success)]",
  warning:
    "border-[var(--ui-warning)] bg-[var(--ui-warning-subtle)] text-[var(--ui-warning)]",
  danger:
    "border-[var(--ui-danger)] bg-[var(--ui-danger-subtle)] text-[var(--ui-danger)]",
  uncertainty:
    "border-[var(--ui-uncertainty)] bg-[var(--ui-uncertainty-subtle)] text-[var(--ui-uncertainty)]",
};

export function StatusChip({
  label,
  tone = "neutral",
  icon: Icon = CircleDashed,
  className,
}: {
  label: string;
  tone?: StatusTone;
  icon?: LucideIcon;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex min-h-7 items-center gap-1.5 rounded-[var(--radius-sm)] border px-2 py-1 text-xs font-bold",
        toneClasses[tone],
        className,
      )}
    >
      <Icon size={14} aria-hidden="true" />
      {label}
    </span>
  );
}

export function SystemStatusBar({
  items,
  className,
}: {
  items: Array<{
    label: string;
    tone?: StatusTone;
    icon?: LucideIcon;
  }>;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-2 border-y border-[var(--ui-border-subtle)] bg-[var(--ui-surface-recessed)] px-3 py-2",
        className,
      )}
      role="status"
      aria-label="System status"
    >
      {items.map((item) => (
        <StatusChip key={item.label} {...item} />
      ))}
    </div>
  );
}

export function InlineNotice({
  title,
  children,
  tone = "neutral",
  className,
}: {
  title?: string;
  children: React.ReactNode;
  tone?: StatusTone;
  className?: string;
}) {
  const Icon =
    tone === "danger"
      ? AlertCircle
      : tone === "warning"
        ? ShieldAlert
        : tone === "success"
          ? CheckCircle2
          : Info;
  return (
    <div
      className={cn(
        "flex gap-3 rounded-[var(--radius-md)] border p-3 text-sm leading-6",
        toneClasses[tone],
        className,
      )}
      role={tone === "danger" ? "alert" : "status"}
    >
      <Icon className="mt-0.5 shrink-0" size={18} aria-hidden="true" />
      <div className="min-w-0">
        {title ? <p className="font-bold">{title}</p> : null}
        <div>{children}</div>
      </div>
    </div>
  );
}

export function BlockingFailurePanel({
  message,
  correlationId,
}: {
  message: string;
  correlationId?: string;
}) {
  return (
    <InlineNotice title="Task paused" tone="danger" className="p-4">
      <p>{message}</p>
      {correlationId ? (
        <details className="mt-2">
          <summary className="cursor-pointer text-xs font-bold">
            Researcher reference
          </summary>
          <code className="mono-metadata mt-1 block">{correlationId}</code>
        </details>
      ) : null}
    </InlineNotice>
  );
}

export function SavedIndicator({ label = "Saved" }: { label?: string }) {
  return <StatusChip label={label} tone="success" icon={Check} />;
}

export function LoadingIndicator({ label }: { label: string }) {
  return (
    <span
      className="inline-flex items-center gap-2 text-sm font-bold text-[var(--ui-text-secondary)]"
      role="status"
      aria-live="polite"
    >
      <Loader2 className="animate-spin" size={17} aria-hidden="true" />
      {label}
    </span>
  );
}

export function RetrievalStatusBadge({ status }: { status?: string }) {
  const normalized = status?.toLowerCase() ?? "unavailable";
  if (normalized === "grounded") {
    return <StatusChip label="Grounded evidence" tone="success" icon={FileCheck2} />;
  }
  if (normalized === "partial_evidence") {
    return <StatusChip label="Partial evidence" tone="warning" icon={AlertCircle} />;
  }
  if (normalized === "individual_assessment") {
    return (
      <StatusChip
        label="Policy found; staff confirmation needed"
        tone="warning"
        icon={HelpCircle}
      />
    );
  }
  if (normalized === "ambiguous") {
    return (
      <StatusChip
        label="Evidence found, personal review may be needed"
        tone="uncertainty"
        icon={HelpCircle}
      />
    );
  }
  if (normalized === "insufficient_evidence") {
    return (
      <StatusChip
        label="Insufficient evidence"
        tone="uncertainty"
        icon={ShieldAlert}
      />
    );
  }
  return (
    <StatusChip
      label="Evidence status unavailable"
      tone="neutral"
      icon={CircleDashed}
    />
  );
}

export const ConnectionIcons = { connected: Wifi, unavailable: WifiOff };
