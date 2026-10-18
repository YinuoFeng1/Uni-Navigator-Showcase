export function createEvidenceUsePayload({
  sessionId,
  participantLabel,
  taskId,
  interactionId,
  citation,
  evidenceAction,
  extras = {},
}) {
  return {
    sessionId,
    participantLabel,
    taskId,
    interactionId,
    citationId: citation?.citationId || citation?.id,
    sourceId: citation?.sourceId,
    chunkId: citation?.chunkId,
    evidenceAction,
    ...extras,
  };
}
