import { AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";

type EscalationBannerProps = {
  level: "low" | "medium" | "high";
  message: string;
};

const levelClasses = {
  low: "bg-[var(--success-soft)] border-[#b7e3c7] text-[#195c32]",
  medium: "bg-[var(--warning-soft)] border-[#f2dc8d] text-[#6b4c00]",
  high: "bg-[var(--danger-soft)] border-[#f1b7b7] text-[#7d1d1d]",
};

export function EscalationBanner({ level, message }: EscalationBannerProps) {
  return (
    <div className={cn("flex gap-3 rounded-md border p-4", levelClasses[level])}>
      <AlertTriangle className="mt-0.5 shrink-0" size={20} aria-hidden="true" />
      <p className="text-sm leading-6">{message}</p>
    </div>
  );
}
