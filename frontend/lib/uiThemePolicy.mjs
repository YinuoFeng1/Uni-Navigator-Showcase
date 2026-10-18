export const UI_THEMES = Object.freeze(["legacy", "research_workbench"]);

export function resolveUiTheme(value) {
  return value === "research_workbench" ? "research_workbench" : "legacy";
}

export function isDesignLabEnabled({ nodeEnv, studyMode }) {
  return nodeEnv === "development" && studyMode === "development";
}
