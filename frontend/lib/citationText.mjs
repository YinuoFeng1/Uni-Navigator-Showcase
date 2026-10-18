const CITATION_LABEL_PATTERN = /(\[\d+\])/g;

/**
 * @typedef {{ text: string, citationLabel: string | null }} CitationSegment
 */

/**
 * @param {string} text
 * @param {string[]} citationLabels
 * @returns {CitationSegment[]}
 */
export function createCitationSegments(text, citationLabels) {
  const availableLabels = new Set(citationLabels.filter(Boolean));

  return text
    .split(CITATION_LABEL_PATTERN)
    .filter(Boolean)
    .map((segment) => ({
      text: segment,
      citationLabel: availableLabels.has(segment) ? segment : null,
    }));
}

/**
 * @param {string} answerId
 * @param {string} citationLabel
 * @returns {string}
 */
export function createCitationAnchorId(answerId, citationLabel) {
  const safeAnswerId = String(answerId).replace(/[^a-zA-Z0-9_-]/g, "-");
  const citationNumber = /^\[(\d+)\]$/.exec(citationLabel)?.[1];
  const safeCitationLabel = citationNumber ?? citationLabel.replace(/\W/g, "-");

  return `answer-${safeAnswerId}-citation-${safeCitationLabel}`;
}
