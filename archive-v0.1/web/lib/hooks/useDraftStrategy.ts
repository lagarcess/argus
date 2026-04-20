import { useState } from "react";
import { toast } from "sonner";
import { StrategyCreate } from "@/app/(protected)/builder/page";
import { postAgentDraft } from "@/lib/api/sdk.gen";
import { strategyToBuilderForm } from "@/lib/strategy-mapper";
import { FUNNEL_EVENTS, trackFunnelEvent } from "@/lib/telemetry";

export interface StrategyDraft extends Partial<StrategyCreate> {
  ai_explanation?: string;
}

function isQuotaExhausted(status: number | undefined, error: unknown): boolean {
  if (status === 402) return true;
  if (!error) return false;

  const message =
    typeof error === "string"
      ? error
      : typeof error === "object"
        ? String(
            (error as { detail?: unknown; message?: unknown; error_code?: unknown })
              .detail ??
              (error as { detail?: unknown; message?: unknown; error_code?: unknown })
                .message ??
              (error as { detail?: unknown; message?: unknown; error_code?: unknown })
                .error_code ??
              "",
          )
        : "";

  return /quota|payment required|exhaust/i.test(message);
}

export function useDraftStrategy() {
  const [isDrafting, setIsDrafting] = useState(false);
  const [quotaRemaining, setQuotaRemaining] = useState<number | null>(null);

  const draftStrategy = async (prompt: string): Promise<StrategyDraft | null> => {
    setIsDrafting(true);

    try {
      const result = await postAgentDraft({
        body: { prompt },
      });
      const data = result.data;
      if (!data) {
        const quotaExhausted = isQuotaExhausted(
          result.response?.status,
          result.error,
        );
        setQuotaRemaining(quotaExhausted ? 0 : null);
        trackFunnelEvent(FUNNEL_EVENTS.DRAFT_FAIL, {
          reason: quotaExhausted ? "quota_exhausted" : "api_error",
        });
        toast.error(
          quotaExhausted ? "Drafting Quota Exhausted" : "Drafting Failed",
          {
            description: quotaExhausted
              ? "You have reached your AI draft quota for now. You can continue with manual builder edits."
              : "AI drafting is temporarily unavailable. You can continue with manual builder edits.",
          },
        );
        return null;
      }

      setQuotaRemaining(null);
      toast.success("Strategy Drafted Successfully");
      trackFunnelEvent(FUNNEL_EVENTS.DRAFT_SUCCESS);
      return {
        ...strategyToBuilderForm(data.draft),
        ai_explanation: data.ai_explanation,
      };
    } catch {
      trackFunnelEvent(FUNNEL_EVENTS.DRAFT_FAIL, { reason: "network_error" });
      toast.error("Drafting Failed", {
        description:
          "AI drafting is temporarily unavailable. You can continue with manual builder edits."
      });
      setQuotaRemaining(null);
      return null;
    } finally {
      setIsDrafting(false);
    }
  };

  return { draftStrategy, isDrafting, quotaRemaining };
}
