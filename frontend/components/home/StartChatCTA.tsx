import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";

export function StartChatCTA() {
  return (
    <section className="uq-container pb-16">
      <div className="rounded-lg bg-[var(--uq-purple)] p-8 text-white md:flex md:items-center md:justify-between md:gap-8">
        <div>
          <h2 className="text-2xl font-black">Ready to test the prototype?</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-white/80">
            Ask a general university policy question and check how the source evidence is shown.
          </p>
        </div>
        <Button asChild variant="warning" className="mt-6 md:mt-0">
          <Link href="/chat">
            Start chat
            <ArrowRight size={18} aria-hidden="true" />
          </Link>
        </Button>
      </div>
    </section>
  );
}
