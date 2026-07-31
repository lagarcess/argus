import type { RunDossier } from "./run-dossier-contract";
import type { RunDossierHistoryState } from "./run-dossier-history-state";

export type DossierPaneState = {
  view: "dossier" | "history";
  historicalRunId: string | null;
};

type DossierPaneEvent =
  | { type: "open_history" }
  | { type: "select_run"; runId: string }
  | { type: "restore_latest" }
  | {
      type: "reset";
      reason: "selection" | "query" | "conversation";
    };

export const DEFAULT_DOSSIER_PANE_STATE: DossierPaneState = {
  view: "dossier",
  historicalRunId: null,
};

export function dossierPaneTransition(
  state: DossierPaneState,
  event: DossierPaneEvent,
): DossierPaneState {
  if (event.type === "open_history") {
    return { ...state, view: "history" };
  }
  if (event.type === "select_run") {
    return { view: "dossier", historicalRunId: event.runId };
  }
  return DEFAULT_DOSSIER_PANE_STATE;
}

export function selectedDossierForPane({
  latestDossier,
  historyItems,
  state,
}: {
  latestDossier: RunDossier;
  historyItems: readonly RunDossier[];
  state: DossierPaneState;
}): RunDossier {
  if (!state.historicalRunId) return latestDossier;
  return (
    historyItems.find((item) => item.run_id === state.historicalRunId) ??
    latestDossier
  );
}

export function dossierCountsForHistory({
  history,
  fallbackTotalRuns,
  fallbackDecidedRuns,
}: {
  history: Pick<
    RunDossierHistoryState,
    "totalRuns" | "decidedRuns" | "hasLoadedData"
  >;
  fallbackTotalRuns: number;
  fallbackDecidedRuns: number;
}): { totalRuns: number; decidedRuns: number } {
  return history.hasLoadedData
    ? {
        totalRuns: history.totalRuns,
        decidedRuns: history.decidedRuns,
      }
    : {
        totalRuns: fallbackTotalRuns,
        decidedRuns: fallbackDecidedRuns,
      };
}

export type DossierPaneKeyboardAction =
  | "allow_control"
  | "delegate"
  | "restore_latest"
  | "suppress_navigation";

export function dossierPaneKeyboardAction({
  key,
  state,
  targetIsDossierControl = false,
  targetIsEditable = false,
}: {
  key: string;
  metaKey: boolean;
  ctrlKey: boolean;
  targetIsDossierControl?: boolean;
  targetIsEditable?: boolean;
  state: DossierPaneState;
}): DossierPaneKeyboardAction {
  const isDigitShortcut = /^[1-9]$/.test(key);
  if (isDigitShortcut && targetIsEditable) return "allow_control";
  if (key === "Enter" && targetIsDossierControl) return "allow_control";
  const ownsKeyboard =
    state.view === "history" || state.historicalRunId !== null;
  if (!ownsKeyboard) return "delegate";
  if (key === "Escape") return "restore_latest";
  if (
    state.view === "history" &&
    (key === "ArrowUp" || key === "ArrowDown")
  ) {
    return "suppress_navigation";
  }
  if (key === "Enter") return "suppress_navigation";
  if (isDigitShortcut) return "suppress_navigation";
  return "delegate";
}

export function openSelectedDossierConversation({
  conversationId,
  dossier,
  navigationDisabled,
  onOpenConversation,
  onClose,
}: {
  conversationId: string | null;
  dossier: RunDossier;
  navigationDisabled: boolean;
  onOpenConversation: (conversationId: string, messageId: string) => void;
  onClose: () => void;
}): boolean {
  if (
    !conversationId ||
    !dossier.result_message_id ||
    navigationDisabled
  ) {
    return false;
  }
  onOpenConversation(conversationId, dossier.result_message_id);
  onClose();
  return true;
}

export async function commitDossierDecision({
  selectedRunId,
  mutate,
  refreshCanonicalSearch,
  refreshLoadedHistory,
}: {
  selectedRunId: string;
  mutate: () => Promise<void>;
  refreshCanonicalSearch: () => Promise<void>;
  refreshLoadedHistory: () => Promise<RunDossierHistoryState>;
}): Promise<RunDossier | null> {
  await mutate();
  const [, historyState] = await Promise.all([
    refreshCanonicalSearch(),
    refreshLoadedHistory(),
  ]);
  if (historyState.status === "error") {
    throw new Error("decision history refresh failed");
  }
  return (
    historyState.items.find((item) => item.run_id === selectedRunId) ?? null
  );
}
