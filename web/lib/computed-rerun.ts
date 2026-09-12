import type { DecisionRerun } from "./decision-contract";
import { parseToolResultCard, toolInputChanges, type ToolResultCard, type ToolScalar } from "./tool-result-card";

/**
 * A computed kind's re-run result is the card its declaration produced. The
 * decision view and the Search dossier both read it through here.
 */
export function rerunCard(rerun: DecisionRerun | null | undefined): ToolResultCard | null {
  if (!rerun || rerun.status !== "computed") return null;
  return parseToolResultCard(rerun.result);
}

/** Drafts that leave every stored input as it was: nothing to recompute. */
export function rerunChanges(stored: ToolResultCard, drafts: Record<string, string>): Record<string, ToolScalar> | null {
  return toolInputChanges(stored, drafts);
}

export function changesAreEmpty(changes: Record<string, ToolScalar> | null): boolean {
  return changes !== null && Object.keys(changes).length === 0;
}
