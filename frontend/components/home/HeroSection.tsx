import Link from "next/link";
import { ArrowRight, FileText, ShieldCheck } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

export function HeroSection() {
  return (
    <section className="bg-[linear-gradient(135deg,#ffffff_0%,#f7f4fa_58%,#eee7f6_100%)]">
      <div className="uq-container grid gap-10 py-14 md:grid-cols-[1.05fr_0.95fr] md:items-center md:py-20">
        <div>
          <Badge tone="purple" className="mb-5">
            <ShieldCheck size={14} aria-hidden="true" />
            Source-aware student support prototype
          </Badge>
          <h1 className="max-w-3xl text-4xl font-black leading-tight text-[var(--uq-purple-dark)] sm:text-5xl">
            Find university policy answers with sources you can check.
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-8 text-[var(--text-secondary)]">
            Uni-Navigator helps students understand administrative policies by giving
            simple answers, showing the evidence, and suggesting when to contact staff.
          </p>
          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Button asChild size="lg">
              <Link href="/chat">
                Start a question
                <ArrowRight size={18} aria-hidden="true" />
              </Link>
            </Button>
            <Button asChild size="lg" variant="secondary">
              <Link href="/study">View study mode</Link>
            </Button>
          </div>
        </div>

        <Card className="soft-shadow overflow-hidden border-0">
          <div className="border-b border-[var(--border-light)] bg-[var(--uq-purple)] p-5 text-white">
            <p className="text-sm font-bold">Assistant preview</p>
            <p className="mt-1 text-sm text-white/80">Evidence-first policy guidance</p>
          </div>
          <div className="space-y-4 p-5">
            <div className="ml-auto max-w-[86%] rounded-lg bg-[var(--uq-purple)] p-4 text-sm leading-6 text-white">
              Can I apply for special consideration if I missed an exam?
            </div>
            <div className="max-w-[92%] rounded-lg border border-[var(--border-light)] bg-white p-4">
              <p className="text-sm leading-6 text-[var(--text-primary)]">
                Based on the policy evidence found, you may need to submit an
                application and supporting evidence. Please check the cited policy
                section before making a decision.
              </p>
              <div className="mt-4 flex items-start gap-3 rounded-md bg-[var(--uq-purple-light)] p-3">
                <FileText className="mt-0.5 text-[var(--uq-purple)]" size={18} />
                <div>
                  <p className="text-sm font-bold text-[var(--uq-purple-dark)]">
                    Source: Assessment Policy
                  </p>
                  <p className="text-xs leading-5 text-[var(--text-secondary)]">
                    Special consideration section
                  </p>
                </div>
              </div>
            </div>
          </div>
        </Card>
      </div>
    </section>
  );
}
