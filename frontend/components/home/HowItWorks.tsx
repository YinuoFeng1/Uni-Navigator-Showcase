const steps = [
  "Ask one policy question",
  "Read the answer and evidence",
  "Check the source or escalate to staff",
];

export function HowItWorks() {
  return (
    <section className="bg-[var(--background-soft)] py-14">
      <div className="uq-container">
        <div className="max-w-3xl">
          <p className="text-sm font-black uppercase tracking-[0.18em] text-[var(--uq-purple)]">
            How it works
          </p>
          <h2 className="mt-3 text-3xl font-black text-[var(--text-primary)]">
            A simple flow that keeps verification visible.
          </h2>
        </div>
        <div className="mt-8 grid gap-5 md:grid-cols-3">
          {steps.map((step, index) => (
            <div
              key={step}
              className="rounded-lg border border-[var(--border-light)] bg-white p-6"
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-full bg-[var(--uq-purple)] text-sm font-black text-white">
                {index + 1}
              </span>
              <h3 className="mt-5 text-xl font-black">{step}</h3>
              <p className="mt-3 text-sm leading-6 text-[var(--text-secondary)]">
                {index === 0
                  ? "Keep questions specific and avoid personal identifiers."
                  : index === 1
                    ? "Use the citation card and highlighted clause to inspect the basis for the answer."
                    : "When the case is personal, urgent, or unclear, contact the relevant university office."}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
