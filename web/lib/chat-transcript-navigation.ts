// #252 — pure navigation-state application for the shared chat shell.
// The shell supplies presentation callbacks; this module owns the mapping
// from cache navigation states to honest UI transitions.

import type { TranscriptNavigationState } from "@/lib/chat-transcript-session-cache";

export type TranscriptNavigationDeps<TSnapshot> = {
  applySnapshot: (snapshot: TSnapshot) => void;
  clearToNeutralSurface: () => void;
  setLoading: (loading: boolean, statusText: string | null) => void;
  showLoadError: () => void;
  onMissingConversation: () => void;
  onLoadFailure: () => void;
  isMissingConversationError: (error: unknown) => boolean;
};

export function applyTranscriptNavigationState<TSnapshot>(
  state: TranscriptNavigationState<TSnapshot>,
  deps: TranscriptNavigationDeps<TSnapshot>,
): void {
  if (state.phase === "loading") {
    // New-key cache miss: never show the previous conversation under the
    // newly selected id — render a neutral loading surface instead.
    deps.clearToNeutralSurface();
    deps.setLoading(true, "loading");
    return;
  }
  if (state.phase === "refreshing" || state.phase === "ready") {
    deps.applySnapshot(state.snapshot);
    deps.setLoading(false, null);
    return;
  }
  deps.setLoading(false, null);
  if (state.snapshot) {
    // The cached view stays visible; only the silent refresh failed.
    deps.showLoadError();
    return;
  }
  if (deps.isMissingConversationError(state.error)) {
    deps.onMissingConversation();
    return;
  }
  deps.onLoadFailure();
}

export function isTerminalJobStatus(status: string | null | undefined): boolean {
  return (
    status === "succeeded" ||
    status === "failed" ||
    status === "canceled" ||
    status === "expired"
  );
}
