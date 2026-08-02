import { useEffect, type Dispatch, type SetStateAction } from "react";

import type { GuestDecisionResumeTarget } from "@/lib/guest-conversion";

export function useDossierDecisionResumeRefresh(
  target: GuestDecisionResumeTarget | null | undefined,
  requestRefresh: Dispatch<SetStateAction<number>>,
) {
  useEffect(() => {
    if (target?.surface !== "omnisearch_dossier") return;
    requestRefresh((current) => current + 1);
  }, [requestRefresh, target]);
}
