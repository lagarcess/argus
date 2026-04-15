import { useState } from "react";
import { toast } from "sonner";
import { StrategyCreate } from "@/app/(protected)/builder/page";

export interface StrategyDraft extends StrategyCreate {
  ai_explanation?: string;
}

export function useDraftStrategy() {
  const [isDrafting, setIsDrafting] = useState(false);
  // Frontend-local quota for mock drafting only. This is intentionally independent
  // from global backtest/session quotas until backend draft quota sync lands.
  const [quotaRemaining, setQuotaRemaining] = useState(5);

  const draftStrategy = async (prompt: string): Promise<StrategyDraft | null> => {
    setIsDrafting(true);

    // Check quota
    if (quotaRemaining <= 0) {
      toast.error("Drafting Quota Exceeded", {
        description: "Mock draft quota reached for this session."
      });
      setIsDrafting(false);
      return null;
    }

    // Mock API Delay
    await new Promise((resolve) => setTimeout(resolve, 1500));

    try {
      const isMockApi = process.env.NEXT_PUBLIC_MOCK_API === "true" || process.env.NODE_ENV !== "production";

      if (isMockApi) {
        setQuotaRemaining((prev) => prev - 1);
        toast.success("Strategy Drafted Successfully");

        return {
          name: "AI Generated Strategy",
          parameters: { sma_fast: 10, sma_slow: 30 },
          capital: 100000,
          trade_direction: "LONG",
          participation_rate: 0.1,
          execution_priority: 1.0,
          va_sensitivity: 1.0,
          slippage_model: "vol_adjusted",
          asset_symbol: "AAPL",
          timeframe: "15Min",
          period_start: "2024-01-01",
          period_end: "2024-02-01",
          slippage_bps: 10,
          fees_per_trade_bps: 5,
          entry_criteria: [
            { indicator_a: "RSI_14", operator: "lt", value: 30 }
          ],
          exit_criteria: [
            { indicator_a: "EMA_20", operator: "cross_below", indicator_b: "Price" }
          ],
          ai_explanation: `Parsed '${prompt}' as a mean reversion strategy. Added RSI oversold conditions and EMA crossover exits for validation.`
        };
      }

      throw new Error("Backend API not implemented yet. Set NEXT_PUBLIC_MOCK_API=true to mock.");

    } catch (error) {
      toast.error("Drafting Failed", {
        description: error instanceof Error ? error.message : "An unknown error occurred"
      });
      return null;
    } finally {
      setIsDrafting(false);
    }
  };

  return { draftStrategy, isDrafting, quotaRemaining };
}
