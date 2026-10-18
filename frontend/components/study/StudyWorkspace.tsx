"use client";

import { useEffect, useMemo, useState } from "react";
import { Check, Loader2, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { ChatShell } from "@/components/chat/ChatShell";
import { ConfidenceRating } from "@/components/study/ConfidenceRating";
import { StudyConditionSwitcher } from "@/components/study/StudyConditionSwitcher";
import { StudyTaskCard } from "@/components/study/StudyTaskCard";
import { TaskCompletionForm } from "@/components/study/TaskCompletionForm";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input, Label, Select } from "@/components/ui/form";
import { InlineNotice } from "@/components/ui/status";
import {
  STUDY_SYSTEM_UNAVAILABLE_MESSAGE,
  completeStudySession,
  completeStudyTask,
  fetchStudyTasks,
  startStudySession,
  startStudyTask,
  submitFinalTaskResponse,
} from "@/lib/api";
import { defaultCondition } from "@/lib/constants";
import { studyTasks as fallbackStudyTasks } from "@/lib/mockData";
import type {
  StudyCondition,
  StudyEvent,
  StudySession,
  StudyTask,
  WouldContactStaff,
} from "@/lib/types";

type StudyEventInput = Omit<StudyEvent, "timestamp" | "condition">;
type PendingAction =
  | "start_session"
  | "complete_session"
  | "start_task"
  | "complete_task"
  | null;
type StatusTone = "info" | "success" | "error";

const studySteps = [
  "Consent and session",
  "Read scenario",
  "Ask and review",
  "Check evidence",
  "Record decision",
  "Finish task",
];
const PILOT_STUDY_MODE =
  process.env.NEXT_PUBLIC_STUDY_MODE !== "development";

export function StudyWorkspace({ workbench = false }: { workbench?: boolean }) {
  const [participantLabel, setParticipantLabel] = useState("");
  const [prototypeNoticeAcknowledged, setPrototypeNoticeAcknowledged] =
    useState(false);
  const [studySession, setStudySession] = useState<StudySession | null>(null);
  const [tasks, setTasks] = useState<StudyTask[]>(
    PILOT_STUDY_MODE ? [] : fallbackStudyTasks,
  );
  const [taskLoadWarning, setTaskLoadWarning] = useState(false);
  const [condition, setCondition] = useState<StudyCondition>(defaultCondition);
  const [taskId, setTaskId] = useState(
    PILOT_STUDY_MODE ? "" : fallbackStudyTasks[0].taskId,
  );
  const [preConfidence, setPreConfidence] = useState(2);
  const [postConfidence, setPostConfidence] = useState(3);
  const [finalDecision, setFinalDecision] = useState("");
  const [wouldContactStaff, setWouldContactStaff] =
    useState<WouldContactStaff>("not_sure");
  const [perceivedAnswerSupported, setPerceivedAnswerSupported] = useState(3);
  const [finalResponseNotes, setFinalResponseNotes] = useState("");
  const [finalResponseSubmitted, setFinalResponseSubmitted] = useState(false);
  const [finalResponseSubmitting, setFinalResponseSubmitting] = useState(false);
  const [lastInteractionId, setLastInteractionId] = useState<string | undefined>();
  const [taskSystemFailed, setTaskSystemFailed] = useState(false);
  const [evidenceChecked, setEvidenceChecked] = useState(false);
  const [taskStarted, setTaskStarted] = useState(false);
  const [statusMessage, setStatusMessage] = useState("");
  const [statusTone, setStatusTone] = useState<StatusTone>("info");
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);
  const [chatRunKey, setChatRunKey] = useState(0);
  const [studyRailCollapsed, setStudyRailCollapsed] = useState(false);
  const activeSession = studySession && !studySession.completedAt ? studySession : null;

  useEffect(() => {
    let cancelled = false;
    fetchStudyTasks()
      .then((items) => {
        if (cancelled || items.length === 0) return;
        setTasks(items);
        setTaskId(items[0].taskId);
      })
      .catch((error) => {
        console.warn("Failed to fetch study tasks.", error);
        if (!cancelled) {
          if (!PILOT_STUDY_MODE) {
            setTasks(fallbackStudyTasks);
            setTaskId(fallbackStudyTasks[0].taskId);
          }
          setTaskLoadWarning(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const activeTask = useMemo(
    () => tasks.find((task) => task.taskId === taskId) ?? tasks[0],
    [taskId, tasks],
  );

  function logEvent(event: StudyEventInput) {
    if (
      event.eventType === "answer_received" &&
      event.interactionId
    ) {
      setLastInteractionId(event.interactionId);
    }
    if (event.eventType === "system_failure") {
      setTaskSystemFailed(true);
      setLastInteractionId(undefined);
      showStatus(STUDY_SYSTEM_UNAVAILABLE_MESSAGE, "error");
    }
    if (event.eventType === "source_checked") {
      setEvidenceChecked(true);
    }
  }

  function resetFinalResponseState() {
    setFinalDecision("");
    setPostConfidence(3);
    setWouldContactStaff("not_sure");
    setPerceivedAnswerSupported(3);
    setFinalResponseNotes("");
    setFinalResponseSubmitted(false);
    setFinalResponseSubmitting(false);
    setLastInteractionId(undefined);
    setTaskSystemFailed(false);
    setEvidenceChecked(false);
  }

  function showStatus(message: string, tone: StatusTone = "info") {
    setStatusMessage(message);
    setStatusTone(tone);
  }

  async function startSession() {
    const participantCode = participantLabel.trim();
    if (!participantCode) {
      showStatus("Enter the participant code provided by the researcher.", "error");
      return;
    }
    if (!prototypeNoticeAcknowledged) {
      showStatus("Acknowledge the research prototype notice before starting.", "error");
      return;
    }
    setPendingAction("start_session");
    showStatus("Starting the participant session...");
    try {
      const session = await startStudySession({
        participantLabel: participantCode,
        studyCondition: condition,
        prototypeNoticeAcknowledged,
        metadata: {
          source: "study_workspace",
          studyMode: PILOT_STUDY_MODE ? "pilot" : "development",
        },
      });
      setParticipantLabel(participantCode);
      setStudySession(session);
      if (session.releaseId && taskLoadWarning) {
        setTaskSystemFailed(true);
        showStatus(STUDY_SYSTEM_UNAVAILABLE_MESSAGE, "error");
        return;
      }
      showStatus("Session ready. Review the scenario and start the task.", "success");
    } catch (error) {
      console.warn("Failed to start study session", error);
      showStatus(
        "The session could not be started. Check that the backend is running, then try again.",
        "error",
      );
    } finally {
      setPendingAction(null);
    }
  }

  async function completeSession() {
    if (!activeSession) return;
    if (taskStarted) {
      showStatus("Finish the active task before ending the session.", "error");
      return;
    }
    setPendingAction("complete_session");
    showStatus("Completing the participant session...");
    try {
      const completed = await completeStudySession(activeSession.sessionId);
      setStudySession(completed);
      setTaskStarted(false);
      showStatus(
        "Session complete. Please tell the researcher before closing this page.",
        "success",
      );
    } catch (error) {
      console.warn("Failed to complete study session", error);
      showStatus(
        "The session could not be completed. Keep this page open and try again.",
        "error",
      );
    } finally {
      setPendingAction(null);
    }
  }

  async function startTask() {
    if (!activeSession || !activeTask) {
      showStatus("Start a participant session before starting a task.", "error");
      return;
    }
    if (taskSystemFailed) {
      showStatus(STUDY_SYSTEM_UNAVAILABLE_MESSAGE, "error");
      return;
    }
    setPendingAction("start_task");
    showStatus("Starting the task...");
    try {
      await startStudyTask(
        activeSession.sessionId,
        activeTask.taskId,
        preConfidence,
      );
      setStudySession((current) =>
        current ? { ...current, currentTaskId: activeTask.taskId } : current,
      );
      setTaskStarted(true);
      resetFinalResponseState();
      setChatRunKey((current) => current + 1);
      showStatus(
        "Task in progress. Ask questions and inspect the evidence before deciding.",
        "success",
      );
    } catch (error) {
      console.warn("Failed to start task", error);
      showStatus(
        "The task could not be started. Check the backend connection and try again.",
        "error",
      );
      return;
    } finally {
      setPendingAction(null);
    }
  }

  async function completeTask() {
    if (!activeSession || !activeTask) {
      showStatus("Start a participant session before completing a task.", "error");
      return;
    }
    if (!finalResponseSubmitted) {
      showStatus("Submit the final response before finishing the task.", "error");
      return;
    }
    if (taskSystemFailed) {
      showStatus(STUDY_SYSTEM_UNAVAILABLE_MESSAGE, "error");
      return;
    }
    setPendingAction("complete_task");
    showStatus("Saving and finishing the task...");
    try {
      await completeStudyTask(activeSession.sessionId, activeTask.taskId);
      setStudySession((current) =>
        current ? { ...current, currentTaskId: null } : current,
      );
      setTaskStarted(false);
      showStatus(
        "Task complete. Select another task, or complete the participant session.",
        "success",
      );
    } catch (error) {
      console.warn("Failed to complete task", error);
      showStatus(
        "The task could not be finished. Your final response is still shown; try again.",
        "error",
      );
      return;
    } finally {
      setPendingAction(null);
    }
  }

  async function submitFinalResponse() {
    if (!activeSession || !activeTask || !taskStarted) {
      showStatus("Start a task before submitting the final response.", "error");
      return;
    }
    if (taskSystemFailed) {
      showStatus(STUDY_SYSTEM_UNAVAILABLE_MESSAGE, "error");
      return;
    }
    const finalDecisionText = finalDecision.trim();
    if (!finalDecisionText) {
      showStatus("Write what you would do before submitting.", "error");
      return;
    }

    setFinalResponseSubmitting(true);
    try {
      const response = await submitFinalTaskResponse({
        sessionId: activeSession.sessionId,
        taskId: activeTask.taskId,
        interactionId: lastInteractionId,
        finalDecisionText,
        confidenceRating: postConfidence,
        wouldContactStaff,
        perceivedAnswerSupported,
        notes: finalResponseNotes.trim() || undefined,
      });
      setFinalResponseSubmitted(true);
      showStatus(
        "Final response saved. Review the confirmation, then finish the task.",
        "success",
      );
      logEvent({
        eventType: "final_response_submitted",
        interactionId: lastInteractionId,
        metadata: {
          responseId: response.responseId,
          finalDecisionLength: finalDecisionText.length,
          confidenceRating: postConfidence,
          wouldContactStaff,
          perceivedAnswerSupported,
        },
      });
    } catch (error) {
      console.warn("Failed to submit final task response", error);
      showStatus(
        "The final response was not saved. Your text remains here; try submitting again.",
        "error",
      );
    } finally {
      setFinalResponseSubmitting(false);
    }
  }

  const sessionFinished = Boolean(studySession?.completedAt);
  const stepComplete = [
    Boolean(studySession),
    taskStarted || finalResponseSubmitted,
    Boolean(lastInteractionId) || finalResponseSubmitted,
    evidenceChecked || finalResponseSubmitted,
    finalResponseSubmitted,
    finalResponseSubmitted && !taskStarted,
  ];
  const currentStep = sessionFinished
    ? 5
    : !activeSession
      ? 0
      : !taskStarted && !finalResponseSubmitted
        ? 1
        : !lastInteractionId && !finalResponseSubmitted
          ? 2
          : !evidenceChecked && !finalResponseSubmitted
            ? 3
            : !finalResponseSubmitted
              ? 4
              : 5;
  const chatDisabledReason = !activeSession
    ? "Start the participant session and task to enable chat."
    : !taskStarted
      ? "Start the selected task to enable chat."
      : finalResponseSubmitted
        ? "The final response is saved. Finish the task to continue."
        : taskSystemFailed
          ? STUDY_SYSTEM_UNAVAILABLE_MESSAGE
        : undefined;

  const workbenchProgress = (
    <nav className="study-progress-rail" aria-label="Study progress">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="text-xs font-black uppercase text-[var(--ui-text-muted)]">
          Study progress
        </p>
        <span className="mono-metadata text-[var(--ui-text-muted)]">
          {Math.min(currentStep + 1, studySteps.length)}/{studySteps.length}
        </span>
      </div>
      <ol>
        {studySteps.map((step, index) => {
          const complete = stepComplete[index];
          const current = currentStep === index;
          const blocked = taskSystemFailed && index >= currentStep;
          return (
            <li
              key={step}
              className="study-progress-step"
              data-current={current}
              data-complete={complete}
              data-blocked={blocked}
              aria-current={current ? "step" : undefined}
            >
              <span className="study-progress-dot">
                {complete ? <Check size={14} aria-hidden="true" /> : index + 1}
              </span>
              <span className="pt-1 text-xs font-bold leading-5 text-[var(--ui-text-secondary)]">
                {step}
              </span>
            </li>
          );
        })}
      </ol>
    </nav>
  );

  return (
    <div className={workbench ? "study-workbench grid gap-4" : "grid gap-6"}>
      <nav
        className="legacy-progress rounded-lg border border-[var(--border-light)] bg-white p-4"
        aria-label="Study progress"
      >
        <ol className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          {studySteps.map((step, index) => {
            const complete = stepComplete[index];
            const current = currentStep === index;
            return (
              <li
                key={step}
                className={`flex min-w-0 items-center gap-3 rounded-md px-3 py-2 ${
                  current ? "bg-[var(--uq-purple-light)]" : "bg-[var(--background-soft)]"
                }`}
                aria-current={current ? "step" : undefined}
              >
                <span
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-black ${
                    complete
                      ? "bg-[var(--success-soft)] text-[#176b3a]"
                      : current
                        ? "bg-[var(--uq-purple)] text-white"
                        : "border border-[var(--border-light)] bg-white text-[var(--text-secondary)]"
                  }`}
                >
                  {complete ? <Check size={17} aria-hidden="true" /> : index + 1}
                </span>
                <span className="min-w-0 text-sm font-bold text-[var(--text-primary)]">
                  {step}
                </span>
              </li>
            );
          })}
        </ol>
      </nav>

      {statusMessage && workbench ? (
        <InlineNotice
          tone={
            statusTone === "error"
              ? "danger"
              : statusTone === "success"
                ? "success"
                : "neutral"
          }
        >
          {statusMessage}
        </InlineNotice>
      ) : statusMessage ? (
        <div
          className={`rounded-lg border p-4 text-sm font-bold leading-6 ${
            statusTone === "error"
              ? "border-[#b42318] bg-[var(--danger-soft)] text-[#7a271a]"
              : statusTone === "success"
                ? "border-[#3b8c5a] bg-[var(--success-soft)] text-[#176b3a]"
                : "border-[var(--border-light)] bg-[var(--background-soft)] text-[var(--text-primary)]"
          }`}
          role={statusTone === "error" ? "alert" : "status"}
          aria-live="polite"
        >
          {statusMessage}
        </div>
      ) : null}

      {taskLoadWarning ? (
        workbench ? (
          <InlineNotice tone="danger">
            {PILOT_STUDY_MODE
              ? STUDY_SYSTEM_UNAVAILABLE_MESSAGE
              : "Study tasks could not be loaded from the backend. Development fallback tasks are visible."}
          </InlineNotice>
        ) : (
          <div
            className="rounded-lg border border-[#b42318] bg-[var(--danger-soft)] p-4 text-sm leading-6 text-[#7a271a]"
            role="alert"
          >
            {PILOT_STUDY_MODE
              ? STUDY_SYSTEM_UNAVAILABLE_MESSAGE
              : "Study tasks could not be loaded from the backend. Development fallback tasks are visible."}
          </div>
        )
      ) : null}

      {workbench ? (
        <button
          type="button"
          className="study-rail-toggle"
          aria-controls="study-context-rail"
          aria-expanded={!studyRailCollapsed}
          onClick={() => setStudyRailCollapsed((current) => !current)}
        >
          {studyRailCollapsed ? (
            <PanelLeftOpen size={17} aria-hidden="true" />
          ) : (
            <PanelLeftClose size={17} aria-hidden="true" />
          )}
          {studyRailCollapsed ? "Show study rail" : "Hide study rail"}
        </button>
      ) : null}

      <div
        className="study-body-grid grid items-start gap-6 xl:grid-cols-[340px_minmax(0,1fr)]"
        data-rail-collapsed={studyRailCollapsed}
      >
        <aside
          id="study-context-rail"
          className="study-context-rail grid content-start gap-5"
        >
          {workbench ? workbenchProgress : null}
          <Card>
            <CardHeader>
              <CardTitle>1. Participant setup</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4">
              {!studySession ? (
                <div className="rounded-md border border-[var(--uq-gold)] bg-[var(--warning-soft)] p-3 text-xs leading-5 text-[var(--text-primary)]">
                  <p className="font-black">Research prototype notice</p>
                  <p className="mt-1">
                    Uni-Navigator is not an official advice service. Use only the
                    synthetic scenario and do not enter real academic, visa,
                    health, financial, appeal, or other sensitive information.
                    Contact authorised staff for real decisions.
                  </p>
                </div>
              ) : null}

              <div className="grid gap-2">
                <Label htmlFor="participant-label">Participant code</Label>
                <Input
                  id="participant-label"
                  value={participantLabel}
                  onChange={(event) => setParticipantLabel(event.target.value)}
                  placeholder="Example: P-001"
                  disabled={Boolean(studySession) || pendingAction !== null}
                  aria-describedby="participant-code-help"
                />
                <p
                  id="participant-code-help"
                  className="text-xs leading-5 text-[var(--text-secondary)]"
                >
                  Use the code provided by the researcher, never a real name or student ID.
                </p>
              </div>

              <StudyConditionSwitcher
                value={condition}
                onChange={setCondition}
                label="Study condition (researcher setup)"
                disabled={Boolean(studySession) || pendingAction !== null}
              />

              {!studySession ? (
                <label className="flex items-start gap-3 rounded-md border border-[var(--border-light)] bg-white p-3 text-sm leading-5 text-[var(--text-primary)]">
                  <input
                    type="checkbox"
                    className="mt-1 h-4 w-4 shrink-0 accent-[var(--uq-purple)]"
                    checked={prototypeNoticeAcknowledged}
                    onChange={(event) =>
                      setPrototypeNoticeAcknowledged(event.target.checked)
                    }
                    disabled={pendingAction !== null}
                  />
                  <span>
                    I understand this is a research prototype, not official advice,
                    and I will not enter real personal sensitive information.
                  </span>
                </label>
              ) : null}

              <Button
                type="button"
                onClick={startSession}
                disabled={
                  Boolean(studySession) ||
                  !prototypeNoticeAcknowledged ||
                  tasks.length === 0 ||
                  pendingAction !== null
                }
              >
                {pendingAction === "start_session" ? (
                  <Loader2 className="animate-spin" size={17} aria-hidden="true" />
                ) : null}
                {pendingAction === "start_session"
                  ? "Starting session..."
                  : "Start participant session"}
              </Button>

              {studySession ? (
                <div className="rounded-md bg-[var(--background-soft)] p-3 text-sm leading-6 text-[var(--text-secondary)]">
                  <span className="font-bold text-[var(--text-primary)]">
                    {activeSession ? "Active session" : "Completed session"}
                  </span>
                  <br />
                  Participant: {studySession.participantLabel}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>2. Select a task</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-5">
              <div className="grid gap-2">
                <Label htmlFor="task-id">Synthetic study task</Label>
                <Select
                  id="task-id"
                  value={taskId}
                  disabled={taskStarted || sessionFinished || pendingAction !== null}
                  onChange={(event) => {
                    setTaskId(event.target.value);
                    resetFinalResponseState();
                    showStatus("Task selected. Review the scenario before starting.");
                  }}
                >
                  {tasks.map((task) => (
                    <option key={task.taskId} value={task.taskId}>
                      {task.title}
                    </option>
                  ))}
                </Select>
              </div>

              <ConfidenceRating
                label="Before starting: How confident are you that you know what to do?"
                value={preConfidence}
                onChange={setPreConfidence}
                disabled={!activeSession || taskStarted || pendingAction !== null}
              />
            </CardContent>
          </Card>

          {activeTask ? (
            <StudyTaskCard
              task={activeTask}
              onStart={startTask}
              onFinish={completeTask}
              started={taskStarted}
              sessionActive={Boolean(activeSession)}
              finalResponseSubmitted={finalResponseSubmitted}
              busy={pendingAction === "start_task" || pendingAction === "complete_task"}
            />
          ) : null}

          <Button
            type="button"
            variant="secondary"
            onClick={completeSession}
            disabled={
              !activeSession || taskStarted || pendingAction !== null
            }
          >
            {pendingAction === "complete_session" ? (
              <Loader2 className="animate-spin" size={17} aria-hidden="true" />
            ) : null}
            {pendingAction === "complete_session"
              ? "Completing session..."
              : "Complete participant session"}
          </Button>
        </aside>

        <section className="min-w-0" aria-label="Task chat and evidence">
          <div className="mb-4">
            <h2 className="text-xl font-black text-[var(--text-primary)]">
              3. Ask questions and check evidence
            </h2>
            <p className="mt-1 text-sm leading-6 text-[var(--text-secondary)]">
              Base your decision on the synthetic scenario. Open citations to inspect
              the supporting passage when evidence is available.
            </p>
          </div>
          <ChatShell
            key={chatRunKey}
            condition={condition}
            onConditionChange={setCondition}
            onEvent={logEvent}
            sessionId={activeSession?.sessionId}
            participantLabel={participantLabel || studySession?.participantLabel}
            participantId={participantLabel || "anonymous"}
            taskId={taskStarted ? taskId : undefined}
            showSidebar={false}
            showSuggestedQuestions={false}
            showTranscriptActions={false}
            interactionDisabled={
              !taskStarted || finalResponseSubmitted || taskSystemFailed
            }
            disabledReason={chatDisabledReason}
            failClosed={PILOT_STUDY_MODE || Boolean(activeSession?.releaseId)}
            workbench={workbench}
            taskTitle={activeTask?.title}
          />
        </section>
      </div>

      {taskStarted ? (
        <Card className={workbench ? "study-final-surface answer-surface" : undefined}>
          <CardHeader>
            <CardTitle>4. Submit your final response</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-6 lg:grid-cols-[minmax(0,0.7fr)_minmax(0,1.3fr)]">
            <div className="rounded-md bg-[var(--background-soft)] p-4 text-sm leading-6 text-[var(--text-secondary)]">
              <p className="font-black text-[var(--text-primary)]">Before submitting</p>
              <p className="mt-2">
                Decide what you would do in this synthetic scenario. Consider whether
                the evidence supports the answer, whether anything remains uncertain,
                and whether authorised staff should be contacted.
              </p>
              <p className="mt-3">
                After submission, your response is locked. You can then finish the task.
              </p>
            </div>
            <TaskCompletionForm
              finalDecisionText={finalDecision}
              onFinalDecisionTextChange={setFinalDecision}
              confidenceRating={postConfidence}
              onConfidenceRatingChange={setPostConfidence}
              wouldContactStaff={wouldContactStaff}
              onWouldContactStaffChange={setWouldContactStaff}
              perceivedAnswerSupported={perceivedAnswerSupported}
              onPerceivedAnswerSupportedChange={setPerceivedAnswerSupported}
              notes={finalResponseNotes}
              onNotesChange={setFinalResponseNotes}
              onSubmit={submitFinalResponse}
              isSubmitting={finalResponseSubmitting}
              isSubmitted={finalResponseSubmitted}
              disabled={
                !activeSession || !lastInteractionId || taskSystemFailed
              }
            />
            {!lastInteractionId ? (
              <p className="text-sm font-bold text-[var(--text-secondary)] lg:col-start-2">
                Ask at least one question and wait for an answer before submitting.
              </p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
