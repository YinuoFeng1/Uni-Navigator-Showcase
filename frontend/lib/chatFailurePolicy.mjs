/**
 * Session-bound chat is always fail-closed. The browser environment cannot
 * downgrade a server-owned participant session into development fallback.
 *
 * @param {{
 *   sessionId?: string,
 *   studyMode?: "development" | "pilot",
 *   explicitFailClosed?: boolean
 * }} input
 */
export function requiresFailClosed(input) {
  return (
    input.explicitFailClosed === true ||
    Boolean(input.sessionId) ||
    input.studyMode === "pilot"
  );
}
