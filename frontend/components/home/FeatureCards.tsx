import { ClipboardCheck, FileSearch, MessageSquareWarning, TestTube2 } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const features = [
  {
    title: "Trusted policy evidence",
    description:
      "Answers are generated from selected university policy documents, not open web guesses.",
    icon: FileSearch,
  },
  {
    title: "Checkable citations",
    description:
      "Each important answer links back to the document, section, or highlighted clause used as evidence.",
    icon: ClipboardCheck,
  },
  {
    title: "Clear next steps",
    description:
      "The system suggests what to check next and when to contact Student Services.",
    icon: MessageSquareWarning,
  },
  {
    title: "Built for research",
    description:
      "The prototype can compare different evidence designs and collect feedback for an HCI study.",
    icon: TestTube2,
  },
];

export function FeatureCards() {
  return (
    <section className="uq-container py-14">
      <div className="max-w-3xl">
        <p className="text-sm font-black uppercase tracking-[0.18em] text-[var(--uq-purple)]">
          What it can help with
        </p>
        <h2 className="mt-3 text-3xl font-black text-[var(--text-primary)]">
          Designed for policy questions that need evidence.
        </h2>
      </div>
      <div className="mt-8 grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {features.map((feature) => {
          const Icon = feature.icon;
          return (
            <Card key={feature.title} className="transition hover:-translate-y-1 hover:shadow-lg">
              <CardHeader>
                <span className="flex h-11 w-11 items-center justify-center rounded-lg bg-[var(--uq-purple-light)] text-[var(--uq-purple)]">
                  <Icon size={22} aria-hidden="true" />
                </span>
                <CardTitle>{feature.title}</CardTitle>
              </CardHeader>
              <CardContent>
                <CardDescription>{feature.description}</CardDescription>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </section>
  );
}
