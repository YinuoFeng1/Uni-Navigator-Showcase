import { AdminDashboard } from "@/components/admin/AdminDashboard";
import { Footer } from "@/components/layout/Footer";
import { Header } from "@/components/layout/Header";
import { UQBrandBar } from "@/components/layout/UQBrandBar";
import { WorkbenchHeader } from "@/components/layout/WorkbenchHeader";
import { resolveUiTheme } from "@/lib/uiThemePolicy.mjs";

export default function AdminPage() {
  const uiTheme = resolveUiTheme(process.env.NEXT_PUBLIC_UI_THEME);
  if (uiTheme === "research_workbench") {
    return (
      <div className="ui-research-workbench">
        <WorkbenchHeader context="Local research monitoring" admin />
        <main className="workbench-page">
          <header className="workbench-context">
            <p className="text-xs font-black uppercase text-[var(--ui-uncertainty)]">
              Researcher workspace
            </p>
            <h1 className="mt-2 text-2xl font-black">Study monitoring</h1>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-[var(--ui-text-secondary)]">
              Review system readiness, session progress, evidence activity, and
              privacy-preserving summaries before export.
            </p>
          </header>
          <AdminDashboard workbench />
        </main>
      </div>
    );
  }

  return (
    <>
      <UQBrandBar />
      <Header activePage="admin" />
      <main>
        <section className="border-b border-[var(--border-light)] bg-[var(--background-soft)] py-10">
          <div className="uq-container">
            <p className="text-sm font-black uppercase tracking-[0.16em] text-[var(--uq-purple)]">
              Researcher-facing local dashboard
            </p>
            <h1 className="mt-3 text-4xl font-black text-[var(--text-primary)]">
              Admin dashboard
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-[var(--text-secondary)]">
              Monitor pilot study data quality before exporting raw research logs.
            </p>
          </div>
        </section>
        <section className="uq-container grid gap-6 py-8">
          <AdminDashboard />
        </section>
      </main>
      <Footer />
    </>
  );
}
