import { Activity, ExternalLink, FileCheck2, TrendingUp, Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { mockAdminLogs } from "@/lib/mockData";

const totalSessions = mockAdminLogs.length;
const citationClicks = mockAdminLogs.filter((log) => log.citationClicked).length;
const evidenceOpenRate = Math.round(
  (mockAdminLogs.filter((log) => log.evidenceOpened).length / totalSessions) * 100,
);
const confidenceChange =
  mockAdminLogs.reduce(
    (sum, log) => sum + (log.postConfidence - log.preConfidence),
    0,
  ) / totalSessions;
const escalationCount = mockAdminLogs.filter((log) =>
  log.feedback.toLowerCase().includes("staff") ||
  log.feedback.toLowerCase().includes("escalation"),
).length;

const metrics = [
  {
    label: "Total sessions",
    value: totalSessions.toString(),
    icon: Users,
  },
  {
    label: "Citation clicks",
    value: citationClicks.toString(),
    icon: ExternalLink,
  },
  {
    label: "Evidence open rate",
    value: `${evidenceOpenRate}%`,
    icon: FileCheck2,
  },
  {
    label: "Avg confidence change",
    value: `+${confidenceChange.toFixed(1)}`,
    icon: TrendingUp,
  },
  {
    label: "Escalation mentions",
    value: escalationCount.toString(),
    icon: Activity,
  },
];

export function MetricCards() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
      {metrics.map((metric) => {
        const Icon = metric.icon;
        return (
          <Card key={metric.label} className="p-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-sm font-bold text-[var(--text-secondary)]">
                  {metric.label}
                </p>
                <p className="mt-2 text-3xl font-black text-[var(--uq-purple)]">
                  {metric.value}
                </p>
              </div>
              <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--uq-purple-light)] text-[var(--uq-purple)]">
                <Icon size={20} aria-hidden="true" />
              </span>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
