"use client";

import Link from "next/link";
import { Menu, ShieldCheck, X } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type HeaderProps = {
  activePage?: "home" | "chat" | "admin";
};

const navItems = [
  { href: "/", label: "Home", key: "home" },
  { href: "/chat", label: "Chat", key: "chat" },
] as const;

export function Header({ activePage = "home" }: HeaderProps) {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-[var(--border-light)] bg-white/95 backdrop-blur">
      <div className="uq-container flex min-h-20 items-center justify-between gap-4 py-3">
        <Link href="/" className="flex items-center gap-3" aria-label="Uni-Navigator home">
          <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-[var(--uq-purple)] text-white">
            <ShieldCheck size={24} aria-hidden="true" />
          </span>
          <span>
            <span className="block text-lg font-black leading-5 text-[var(--uq-purple)]">
              Uni-Navigator
            </span>
            <span className="text-xs font-bold uppercase tracking-[0.16em] text-[var(--text-secondary)]">
              Research prototype
            </span>
          </span>
        </Link>

        <nav className="hidden items-center gap-1 md:flex" aria-label="Main navigation">
          {navItems.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "rounded-md px-3 py-2 text-sm font-bold text-[var(--text-secondary)] transition hover:bg-[var(--uq-purple-light)] hover:text-[var(--uq-purple)] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2",
                activePage === item.key &&
                  "bg-[var(--uq-purple-light)] text-[var(--uq-purple)]",
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="hidden md:block">
          <Button asChild>
            <Link href="/chat">Start asking</Link>
          </Button>
        </div>

        <button
          className="inline-flex h-11 w-11 items-center justify-center rounded-md border border-[var(--border-light)] text-[var(--uq-purple)] md:hidden"
          type="button"
          aria-label={open ? "Close menu" : "Open menu"}
          onClick={() => setOpen((value) => !value)}
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {open ? (
        <div className="border-t border-[var(--border-light)] bg-white md:hidden">
          <nav className="uq-container grid gap-2 py-4" aria-label="Mobile navigation">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                onClick={() => setOpen(false)}
                className={cn(
                  "rounded-md px-3 py-3 text-sm font-bold text-[var(--text-secondary)]",
                  activePage === item.key &&
                    "bg-[var(--uq-purple-light)] text-[var(--uq-purple)]",
                )}
              >
                {item.label}
              </Link>
            ))}
            <Button asChild className="mt-2">
              <Link href="/chat" onClick={() => setOpen(false)}>
                Start asking
              </Link>
            </Button>
          </nav>
        </div>
      ) : null}
    </header>
  );
}
