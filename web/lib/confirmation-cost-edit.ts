import type { ConfirmationDisplayFacts } from "./confirmation-assumptions-display";

export const MAX_SLIPPAGE_PERCENT = 5;

export type ExecutionCostEditDraft = {
  feePercent: string;
  slippagePercent: string;
};

export function parseCostPercentInput(value: string): number | null {
  const trimmed = value.trim().replace(/%$/, "").trim();
  if (trimmed === "") {
    return null;
  }
  const numeric = Number(trimmed);
  return Number.isFinite(numeric) ? numeric : null;
}

export type CostPercentCaps = {
  feeMaxPercent?: number;
  slippageMaxPercent?: number;
};

export function isValidFeePercent(
  value: number | null,
  maxPercent?: number,
): boolean {
  if (value === null || value < 0) return false;
  return typeof maxPercent === "number" ? value <= maxPercent : true;
}

export function isValidSlippagePercent(
  value: number | null,
  maxPercent: number = MAX_SLIPPAGE_PERCENT,
): boolean {
  return value !== null && value >= 0 && value <= maxPercent;
}

export function isValidCostEditDraft(
  draft: ExecutionCostEditDraft,
  caps?: CostPercentCaps,
): boolean {
  return (
    isValidFeePercent(parseCostPercentInput(draft.feePercent), caps?.feeMaxPercent) &&
    isValidSlippagePercent(
      parseCostPercentInput(draft.slippagePercent),
      caps?.slippageMaxPercent ?? MAX_SLIPPAGE_PERCENT,
    )
  );
}

export function costEditDraftFromDisplayFacts(
  facts: ConfirmationDisplayFacts | null | undefined,
): ExecutionCostEditDraft {
  return {
    feePercent: decimalRateToPercentInput(facts?.fees),
    slippagePercent: decimalRateToPercentInput(facts?.slippage),
  };
}

export function decimalRateToPercentInput(
  value: number | string | null | undefined,
): string {
  const numeric =
    typeof value === "number"
      ? value
      : typeof value === "string" && value.trim() !== ""
        ? Number(value)
        : null;
  if (numeric === null || !Number.isFinite(numeric) || numeric <= 0) {
    return "0";
  }
  const percent = Math.round(numeric * 100 * 10000) / 10000;
  return String(percent);
}

export function costEditDraftToRates(
  draft: ExecutionCostEditDraft,
  caps?: CostPercentCaps,
): { fee_rate: number; slippage: number } | null {
  const fee = parseCostPercentInput(draft.feePercent);
  const slippage = parseCostPercentInput(draft.slippagePercent);
  if (
    !isValidFeePercent(fee, caps?.feeMaxPercent) ||
    !isValidSlippagePercent(
      slippage,
      caps?.slippageMaxPercent ?? MAX_SLIPPAGE_PERCENT,
    )
  ) {
    return null;
  }
  // The endpoint takes decimal rates; percent stays a display convention.
  return {
    fee_rate: (fee as number) / 100,
    slippage: (slippage as number) / 100,
  };
}
