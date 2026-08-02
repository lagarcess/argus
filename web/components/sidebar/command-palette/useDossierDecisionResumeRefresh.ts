import { useEffect, useEffectEvent } from "react";

import type { GuestDecisionResumeTarget } from "@/lib/guest-conversion";

export function useDossierDecisionResumeRefresh(
  target: GuestDecisionResumeTarget | null | undefined,
  refreshCanonicalProjection: () => Promise<void>,
  refreshLoadedHistory: () => Promise<void>,
) {
  const refreshResumeSurface = useEffectEvent(() => {
    void Promise.allSettled([
      refreshCanonicalProjection(),
      refreshLoadedHistory(),
    ]);
  });

  useEffect(() => {
    if (target?.surface !== "omnisearch_dossier") return;
    refreshResumeSurface();
  }, [target]);
}
