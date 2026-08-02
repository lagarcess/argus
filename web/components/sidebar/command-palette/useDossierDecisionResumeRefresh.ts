import { useEffect, type Dispatch, type SetStateAction } from "react";

import type { GuestDecisionResumeTarget } from "@/lib/guest-conversion";

export function useDossierDecisionResumeRefresh(
  target: GuestDecisionResumeTarget | null | undefined,
  requestSearchRefresh: Dispatch<SetStateAction<number>>,
  refreshLoadedHistory: () => Promise<void>,
) {
  useEffect(() => {
    if (target?.surface !== "omnisearch_dossier") return;
    requestSearchRefresh((current) => current + 1);
    void refreshLoadedHistory();
  }, [refreshLoadedHistory, requestSearchRefresh, target]);
}
