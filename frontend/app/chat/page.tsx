import { ChatShell } from "@/components/chat/ChatShell";
import { Footer } from "@/components/layout/Footer";
import { Header } from "@/components/layout/Header";
import { UQBrandBar } from "@/components/layout/UQBrandBar";

export default function ChatPage() {
  return (
    <>
      <UQBrandBar />
      <Header activePage="chat" />
      <main className="bg-white">
        <section className="border-b border-[var(--border-light)] bg-[var(--background-soft)] py-10">
          <div className="uq-container">
            <p className="text-sm font-black uppercase tracking-[0.16em] text-[var(--uq-purple)]">
              Research prototype · Not an official decision tool
            </p>
            <h1 className="mt-3 text-4xl font-black text-[var(--text-primary)]">
              Ask Uni-Navigator
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-[var(--text-secondary)]">
              Ask one university policy question at a time. Check the evidence before
              making a decision.
            </p>
          </div>
        </section>
        <section className="uq-container py-8">
          <ChatShell />
        </section>
      </main>
      <Footer />
    </>
  );
}
