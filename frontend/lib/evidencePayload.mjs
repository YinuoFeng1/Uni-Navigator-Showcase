export function createEvidenceUsePayload({
  interactionId,
  citation,
  evidenceAction,
}) {
  return {
    interactionId,
    citationId: citation?.citationId || citation?.id,
    sourceId: citation?.sourceId,
    chunkId: citation?.chunkId,
    evidenceAction,
  };
}
