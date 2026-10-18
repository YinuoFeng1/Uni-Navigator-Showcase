import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-[var(--border-light)] bg-[var(--background-soft)]">
      <div className="uq-container grid gap-6 py-10 md:grid-cols-[1.4fr_1fr]">
        <div>
          <p className="text-lg font-black text-[var(--uq-purple)]">Uni-Navigator</p>
          <p className="mt-2 max-w-xl text-sm leading-6 text-[var(--text-secondary)]">
            A student-facing, source-aware policy assistant prototype for HCI research.
            It gives general guidance and encourages students to check the evidence.
          </p>
        </div>
        <div>
          <p className="text-sm font-bold text-[var(--text-primary)]">Prototype links</p>
          <div className="mt-3 grid gap-2 text-sm text-[var(--text-secondary)]">
            <Link href="/chat" className="hover:text-[var(--uq-purple)]">
              Ask a question
            </Link>
          </div>
        </div>
        <div>
          <p className="text-sm font-bold text-[var(--text-primary)]">Safety reminder</p>
          <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
            Do not enter student ID, passport, medical details, or other private personal
            information into this prototype.
          </p>
        </div>
      </div>
    </footer>
  );
}
