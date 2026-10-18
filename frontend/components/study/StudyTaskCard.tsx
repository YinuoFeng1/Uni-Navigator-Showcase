import { Play, SquareCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { StudyTask } from "@/lib/types";

type StudyTaskCardProps = {
  task: StudyTask;
  onStart: () => void;
  onFinish: () => void;
  started: boolean;
  sessionActive: boolean;
  finalResponseSubmitted: boolean;
  busy?: boolean;
};

export function StudyTaskCard({
  task,
  onStart,
  onFinish,
  started,
  sessionActive,
  finalResponseSubmitted,
  busy = false,
}: StudyTaskCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{task.title}</CardTitle>
        <CardDescription>{task.scenario}</CardDescription>
      </CardHeader>
      <CardContent className="grid gap-4">
        <p className="rounded-md bg-[var(--background-soft)] p-3 text-sm leading-6 text-[var(--text-secondary)]">
          Start the task when you are ready. Use the chat and inspect any evidence
          you think is relevant before submitting your final response.
        </p>
        <div className="grid gap-2">
          <Button
            type="button"
            onClick={onStart}
            disabled={!sessionActive || started || busy}
          >
            <Play size={17} aria-hidden="true" />
            {busy && !started ? "Starting task..." : started ? "Task in progress" : "Start task"}
          </Button>
          <Button
            type="button"
            variant="secondary"
            onClick={onFinish}
            disabled={!started || !finalResponseSubmitted || busy}
          >
            <SquareCheck size={17} aria-hidden="true" />
            {busy && started ? "Finishing task..." : "Finish task"}
          </Button>
        </div>
        {!sessionActive ? (
          <p className="text-xs leading-5 text-[var(--text-secondary)]">
            Start the participant session first.
          </p>
        ) : started && !finalResponseSubmitted ? (
          <p className="text-xs leading-5 text-[var(--text-secondary)]">
            Submit the final response before finishing this task.
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
