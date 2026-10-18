import { AlertTriangle } from "lucide-react";

export function SafetyNotice() {
  return (
    <section className="uq-container py-12">
      <div className="rounded-lg border border-[#f2dc8d] border-l-8 border-l-[var(--uq-gold)] bg-[var(--warning-soft)] p-6">
        <div className="flex gap-4">
          <AlertTriangle className="mt-1 shrink-0 text-[#7a5a00]" size={24} />
          <div>
            <h2 className="text-xl font-black text-[var(--text-primary)]">
              Safety and privacy notice
            </h2>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-[var(--text-secondary)]">
              Please do not enter private personal information. Uni-Navigator gives
              general policy guidance based on available evidence. For personal,
              urgent, or high-risk cases, contact Student Services or the relevant
              university office.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
