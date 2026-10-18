import Link from "next/link";
import { CircleHelp, ShieldCheck } from "lucide-react";
import { AppearanceSwitcher } from "@/components/layout/AppearanceSwitcher";
import { StatusChip } from "@/components/ui/status";

export function WorkbenchHeader({
  context,
  admin = false,
}: {
  context: string;
  admin?: boolean;
}) {
  return (
    <header className="workbench-topbar">
      <div className="flex min-w-0 items-center gap-3">
        <Link
          href="/"
          className="workbench-brand-mark shrink-0 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ui-focus-ring)]"
          aria-label="Uni-Navigator home"
        >
          <ShieldCheck size={19} aria-hidden="true" />
        </Link>
        <div className="workbench-brand-copy min-w-0">
          <p className="truncate text-sm font-black text-[var(--ui-text-primary)]">
            Uni-Navigator
          </p>
          <p className="truncate text-xs text-[var(--ui-text-muted)]">{context}</p>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <StatusChip
          label={admin ? "Researcher view" : "Research prototype"}
          tone={admin ? "uncertainty" : "accent"}
        />
        <Link
          href={admin ? "/study" : "/"}
          className="grid h-10 w-10 place-items-center rounded-[var(--radius-md)] border border-[var(--ui-border-subtle)] text-[var(--ui-text-secondary)] hover:bg-[var(--ui-surface-recessed)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ui-focus-ring)]"
          aria-label={admin ? "Open study workspace" : "Open help and home"}
          title={admin ? "Open study workspace" : "Help and home"}
        >
          <CircleHelp size={18} aria-hidden="true" />
        </Link>
        <AppearanceSwitcher />
      </div>
    </header>
  );
}
