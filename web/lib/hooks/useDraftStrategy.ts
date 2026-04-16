import { useState } from "react";
import { toast } from "sonner";
import { StrategyCreate } from "@/app/(protected)/builder/page";
import { postAgentDraft } from "@/lib/api/sdk.gen";
import { strategyToBuilderForm } from "@/lib/strategy-mapper";
import { FUNNEL_EVENTS, trackFunnelEvent } from "@/lib/telemetry";

export interface StrategyDraft extends Partial<StrategyCreate> {
  ai_explanation?: string;
}

export function useDraftStrategy() {
  const [isDrafting, setIsDrafting] = useState(false);
  const [quotaRemaining, setQuotaRemaining] = useState<number | null>(null);

  const draftStrategy = async (prompt: string): Promise<StrategyDraft | null> => {
    setIsDrafting(true);

    try {
      const { data } = await postAgentDraft({
        body: { prompt },
      });
      if (!data) {
        throw new Error("Missing draft response payload");
      }
      setQuotaRemaining(null);
      toast.success("Strategy Drafted Successfully");
      trackFunnelEvent(FUNNEL_EVENTS.DRAFT_SUCCESS);
      return {
        ...strategyToBuilderForm(data.draft),
        ai_explanation: data.ai_explanation,
      };
    } catch {
      trackFunnelEvent(FUNNEL_EVENTS.DRAFT_FAIL);
      toast.error("Drafting Failed", {
        description:
          "AI drafting is unavailable or quota is exhausted. You can continue with manual builder edits."
      });
      setQuotaRemaining(0);
      return null;
    } finally {
      setIsDrafting(false);
    }
  };

  return { draftStrategy, isDrafting, quotaRemaining };
}
