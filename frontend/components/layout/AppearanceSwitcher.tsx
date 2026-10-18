"use client";

import { Laptop, Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

type Appearance = "system" | "light" | "dark";

const options = [
  { value: "system", label: "Use system appearance", icon: Laptop },
  { value: "light", label: "Use light appearance", icon: Sun },
  { value: "dark", label: "Use dark appearance", icon: Moon },
] as const;

export function AppearanceSwitcher() {
  const [appearance, setAppearance] = useState<Appearance>("system");

  function applyAppearance(next: Appearance) {
    if (next === "system") {
      delete document.documentElement.dataset.appearance;
      window.localStorage.removeItem("uni-navigator-appearance");
      return;
    }
    document.documentElement.dataset.appearance = next;
    window.localStorage.setItem("uni-navigator-appearance", next);
  }

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const stored = window.localStorage.getItem("uni-navigator-appearance");
      const next: Appearance =
        stored === "light" || stored === "dark" ? stored : "system";
      setAppearance(next);
      applyAppearance(next);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  function select(next: Appearance) {
    setAppearance(next);
    applyAppearance(next);
  }

  return (
    <div
      className="inline-flex rounded-[var(--radius-md)] border border-[var(--ui-border-subtle)] bg-[var(--ui-surface-recessed)] p-0.5"
      role="group"
      aria-label="Appearance"
    >
      {options.map(({ value, label, icon: Icon }) => (
        <button
          key={value}
          type="button"
          className={cn(
            "grid h-9 w-9 place-items-center rounded-[var(--radius-sm)] text-[var(--ui-text-muted)] transition-colors hover:text-[var(--ui-text-primary)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--ui-focus-ring)]",
            appearance === value &&
              "bg-[var(--ui-surface-elevated)] text-[var(--ui-accent-strong)] shadow-sm",
          )}
          aria-label={label}
          aria-pressed={appearance === value}
          title={label}
          onClick={() => select(value)}
        >
          <Icon size={17} aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}
