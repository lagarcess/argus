"use client";

import { useMemo, useSyncExternalStore } from "react";

import {
  createRunDossierHistoryController,
  type RunDossierHistoryState,
} from "@/lib/run-dossier-history-state";
import { listRunDossiers } from "@/lib/run-dossiers-api";

export type UseRunDossierHistoryResult = RunDossierHistoryState & {
  open: () => Promise<void>;
  loadOlder: () => Promise<void>;
  retry: () => Promise<void>;
  refresh: () => Promise<void>;
  getCurrentState: () => RunDossierHistoryState;
};

export function useRunDossierHistory(
  conversationId: string,
  resetKey: string = conversationId,
): UseRunDossierHistoryResult {
  const controller = useMemo(
    () => {
      void resetKey;
      return createRunDossierHistoryController({
        conversationId,
        listRunDossiers,
      });
    },
    [conversationId, resetKey],
  );
  const state = useSyncExternalStore(
    controller.subscribe,
    controller.getState,
    controller.getState,
  );

  return useMemo(
    () => ({
      ...state,
      open: controller.open,
      loadOlder: controller.loadOlder,
      retry: controller.retry,
      refresh: controller.refresh,
      getCurrentState: controller.getState,
    }),
    [controller, state],
  );
}
