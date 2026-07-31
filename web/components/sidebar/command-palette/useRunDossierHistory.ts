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
};

export function useRunDossierHistory(
  conversationId: string,
): UseRunDossierHistoryResult {
  const controller = useMemo(
    () =>
      createRunDossierHistoryController({
        conversationId,
        listRunDossiers,
      }),
    [conversationId],
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
    }),
    [controller, state],
  );
}
