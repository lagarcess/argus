import type { ComputationRefresh } from "./computation-contract";
import type { DecisionRerun, DecisionRerunReasonCode } from "./decision-contract";
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

/**
 * What an edit re-runs, or null when there is nothing to run: an invalid draft,
 * or drafts back at the stored inputs with no earlier edit's result to replace.
 */
export function editRerun(stored: ToolResultCard, drafts: Record<string, string>, hasLatest: boolean): Record<string, ToolScalar> | null {
  const pending = rerunChanges(stored, drafts);
  if (!pending || (Object.keys(pending).length === 0 && !hasLatest)) return null;
  return pending;
}

export function changesAreEmpty(changes: Record<string, ToolScalar> | null): boolean {
  return changes !== null && Object.keys(changes).length === 0;
}

/** A failed request's message for one calculation, or for every calculation when `calculation` is null. */
export type RerunError = { calculation: number | null; message: string };

export function rerunErrorMessage(error: RerunError | null, calculation: number): string | null {
  return error && (error.calculation === null || error.calculation === calculation) ? error.message : null;
}

/** One calculation's latest result in the Search dossier, beside its stored card. */
export type AnswerRerunPanel = {
  latest: ToolResultCard | null;
  source: "changes" | "refreshed";
  reasonCode: DecisionRerunReasonCode | null;
};

export function answerRerunPanels(count: number): AnswerRerunPanel[] {
  return Array.from({ length: count }, (): AnswerRerunPanel => ({ latest: null, source: "changes", reasonCode: null }));
}

/** An edit re-runs every calculation; only the edited calculation's panel takes its result. */
export function panelsAfterEdit(panels: readonly AnswerRerunPanel[], calculation: number, reruns: readonly DecisionRerun[]): AnswerRerunPanel[] {
  const rerun = reruns[calculation];
  return panels.map((panel, index): AnswerRerunPanel => {
    if (index !== calculation) return panel;
    if (rerun?.status === "unavailable" && rerun.reason_code) return { ...panel, latest: null, reasonCode: rerun.reason_code };
    return { latest: rerunCard(rerun), source: "changes", reasonCode: null };
  });
}

/** Each calculation's refreshed card in marker order, or null when nothing was recomputed. */
export function refreshedCards(response: Pick<ComputationRefresh, "status" | "reruns">, count: number): Array<ToolResultCard | null> | null {
  if (response.status !== "refreshed") return null;
  const cards = Array.from({ length: count }, (_, index) => rerunCard(response.reruns[index]));
  return cards.some((card) => card !== null) ? cards : null;
}

/** A refreshed card lands beside its own stored card; a calculation that did not recompute keeps its panel. */
export function panelsAfterRefresh(panels: readonly AnswerRerunPanel[], cards: ReadonlyArray<ToolResultCard | null>): AnswerRerunPanel[] {
  return panels.map((panel, index): AnswerRerunPanel => {
    const card = cards[index];
    return card ? { latest: card, source: "refreshed", reasonCode: null } : panel;
  });
}
