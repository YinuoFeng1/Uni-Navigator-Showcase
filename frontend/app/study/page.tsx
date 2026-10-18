import { Footer } from "@/components/layout/Footer";
import { Header } from "@/components/layout/Header";
import { UQBrandBar } from "@/components/layout/UQBrandBar";
import { WorkbenchHeader } from "@/components/layout/WorkbenchHeader";
import { StudyWorkspace } from "@/components/study/StudyWorkspace";
import { resolveUiTheme } from "@/lib/uiThemePolicy.mjs";

export default function StudyPage() {
  const uiTheme = resolveUiTheme(process.env.NEXT_PUBLIC_UI_THEME);
  if (uiTheme === "research_workbench") {
    return (
      <div className="ui-research-workbench">
        <WorkbenchHeader context="Participant study workspace" />
        <main className="workbench-page">
          <header className="workbench-context">
            <p className="text-xs font-black uppercase text-[var(--ui-accent-strong)]">
              Source-aware policy research
            </p>
            <div className="mt-2 flex flex-col gap-2 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h1 className="text-2xl font-black text-[var(--ui-text-primary)]">
                  Study workspace
                </h1>
                <p className="mt-1 max-w-3xl text-sm leading-6 text-[var(--ui-text-secondary)]">
                  Work only from the assigned synthetic scenario. Review the answer,
                  inspect evidence, and record your own decision.
                </p>
              </div>
              <p className="text-xs font-bold text-[var(--ui-text-muted)]">
                Not an official advice service
              </p>
            </div>
          </header>
          <StudyWorkspace workbench />
        </main>
      </div>
    );
  }

  return (
    <>
      <UQBrandBar />
      <Header activePage="study" />
      <main>
        <section className="border-b border-[var(--border-light)] bg-[var(--background-soft)] py-10">
          <div className="uq-container">
            <p className="text-sm font-black uppercase tracking-[0.16em] text-[var(--uq-purple)]">
              Participant study workspace
            </p>
            <h1 className="mt-3 text-4xl font-black text-[var(--text-primary)]">
              Study mode
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-[var(--text-secondary)]">
              Complete the assigned synthetic policy task, inspect the evidence, and
              record what you would do next. Follow the researcher&apos;s instructions
              before starting.
            </p>
          </div>
        </section>
        <section className="uq-container py-8">
          <StudyWorkspace />
        </section>
      </main>
      <Footer />
    </>
  );
}
