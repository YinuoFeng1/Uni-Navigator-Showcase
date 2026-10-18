import type { AdminLog, AssistantAnswer, StudyTask } from "@/lib/types";

export const suggestedQuestions = [
  "Can I apply for special consideration after missing an exam?",
  "What evidence do I need for an assessment extension?",
  "What should I do if I am unsure which policy applies to me?",
  "When should I contact Student Services?",
];

export const mockAssistantAnswer: AssistantAnswer = {
  id: "answer_001",
  answer:
    "Based on the available policy evidence, you may be able to apply for special consideration if your circumstances affected your exam. You should check the specific eligibility rules and submit supporting evidence.",
  shortAnswer:
    "Based on the available policy evidence, you may be able to apply for special consideration if your circumstances affected your exam. You should check the specific eligibility rules and submit supporting evidence.",
  basedOn:
    "This answer is based on retrieved prepared policy passages about special consideration evidence and when to contact staff.",
  evidenceSummary:
    "The cited policy section explains that students may need to provide evidence when applying for special consideration.",
  nextStep:
    "Read the cited section, prepare supporting evidence, and contact Student Services if your case is urgent or unclear.",
  limitations:
    "This answer is general guidance only. Your case may depend on dates, evidence type, and individual circumstances.",
  uncertainty:
    "The evidence may help with the general scenario, but personal circumstances and deadlines may change the outcome.",
  uncertaintyLevel: "medium",
  escalationRecommended: true,
  highStakesDetected: true,
  retrievalStatus: "ambiguous",
  escalationGuidance:
    "Contact authorised university staff if the case involves deadlines, enrolment status, visa conditions, fees, appeals, or personal academic records.",
  citations: [
    {
      id: "citation_001",
      chunkId: "mock_chunk_001",
      documentTitle: "Assessment Policy",
      sectionHeading: "Special consideration",
      pageNumber: 4,
      quotedText:
        "Students may be required to provide supporting evidence when applying for special consideration.",
      surroundingText:
        "Special consideration is available where circumstances beyond a student's control affect assessment. Students may be required to provide supporting evidence when applying for special consideration. Applications must follow the relevant university process.",
      sourceUrl: "#",
      relevanceScore: 0.86,
    },
    {
      id: "citation_002",
      chunkId: "mock_chunk_002",
      documentTitle: "Student Services Guide",
      sectionHeading: "When to contact staff",
      pageNumber: 2,
      quotedText:
        "Students should contact the relevant office when a case depends on individual circumstances or urgent deadlines.",
      surroundingText:
        "General guidance can help students identify the right policy pathway. Students should contact the relevant office when a case depends on individual circumstances or urgent deadlines. Staff can confirm the correct process for personal cases.",
      sourceUrl: "#",
      relevanceScore: 0.74,
    },
  ],
};

export const studyTasks: StudyTask[] = [
  {
    id: "task_special_consideration",
    taskId: "task_special_consideration",
    title: "Missed exam because of illness",
    scenario:
      "You missed an exam because of illness. Use the system to find what you should do next and what evidence may be needed.",
    taskType: "clear_single_source",
    difficulty: "easy",
    expectedSafeBehaviour:
      "Check the cited policy, identify evidence needs, and decide whether staff contact is needed.",
    expectedAction:
      "Identify whether special consideration may apply, check the cited policy, and decide whether staff contact is needed.",
    escalationExpected: true,
    active: true,
  },
  {
    id: "task_extension",
    taskId: "task_extension",
    title: "Assessment extension evidence",
    scenario:
      "You need a short extension for an assessment and want to know what evidence may be required.",
    taskType: "high_stakes",
    difficulty: "medium",
    expectedSafeBehaviour:
      "Find evidence, avoid entering real private details, and contact staff if deadlines matter.",
    expectedAction:
      "Find the policy evidence, decide what to prepare, and avoid sharing private details in chat.",
    escalationExpected: true,
    active: true,
  },
  {
    id: "task_unclear_policy",
    taskId: "task_unclear_policy",
    title: "Unsure which policy applies",
    scenario:
      "You are not sure whether your situation is covered by an extension, deferral, or special consideration process.",
    taskType: "ambiguous",
    difficulty: "hard",
    expectedSafeBehaviour:
      "Recognise uncertainty, check evidence, and decide when to contact Student Services.",
    expectedAction:
      "Use the answer to identify uncertainty and decide when to contact Student Services.",
    escalationExpected: true,
    active: true,
  },
];

export const mockAdminLogs: AdminLog[] = [
  {
    id: "log_001",
    participantId: "P-014",
    condition: "C_HIGHLIGHT",
    taskId: "task_special_consideration",
    question: "Can I apply for special consideration after missing an exam?",
    citationClicked: true,
    evidenceOpened: true,
    preConfidence: 2,
    postConfidence: 4,
    timeTaken: "4m 18s",
    feedback: "Clear answer, source quote helped.",
  },
  {
    id: "log_002",
    participantId: "P-021",
    condition: "A_SIMPLE_LINK",
    taskId: "task_extension",
    question: "What evidence do I need for an assessment extension?",
    citationClicked: true,
    evidenceOpened: false,
    preConfidence: 3,
    postConfidence: 3,
    timeTaken: "3m 02s",
    feedback: "Wanted more detail before opening the source.",
  },
  {
    id: "log_003",
    participantId: "P-033",
    condition: "D_NEXT_STEP",
    taskId: "task_unclear_policy",
    question: "What should I do if I am unsure which policy applies?",
    citationClicked: true,
    evidenceOpened: true,
    preConfidence: 1,
    postConfidence: 4,
    timeTaken: "5m 41s",
    feedback: "Next-step guidance made escalation clearer.",
  },
  {
    id: "log_004",
    participantId: "P-041",
    condition: "B_SECTION",
    taskId: "task_special_consideration",
    question: "When should I contact Student Services?",
    citationClicked: false,
    evidenceOpened: false,
    preConfidence: 2,
    postConfidence: 3,
    timeTaken: "2m 47s",
    feedback: "Trusted the section name but did not verify.",
  },
];
