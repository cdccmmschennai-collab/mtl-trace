import type { ScopeStatus } from "../types/api";

export type ScopeStateLabel = "Excel ready" | "Consolidated" | "Sources added" | "Scope locked" | "Draft scope";
export type ScopeTone = "match" | "accent" | "review";

/** Plain-language state of a tag scope, from what the backend reports for its current run. */
export function scopeState(s: {
  scopeStatus: ScopeStatus;
  hasSources: boolean;
  consolidated: boolean;
  compared: boolean;
}): { label: ScopeStateLabel; tone: ScopeTone } {
  if (s.compared) return { label: "Excel ready", tone: "match" };
  if (s.consolidated) return { label: "Consolidated", tone: "accent" };
  if (s.hasSources) return { label: "Sources added", tone: "accent" };
  if (s.scopeStatus === "LOCKED") return { label: "Scope locked", tone: "accent" };
  return { label: "Draft scope", tone: "review" };
}
