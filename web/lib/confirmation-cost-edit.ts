import type { TFunction } from "i18next";
import type { ConfirmationDisplayFacts } from "./confirmation-assumptions-display";

type Translate = TFunction;

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

export function isValidFeePercent(value: number | null): boolean {
  return value !== null && value >= 0;
}

export function isValidSlippagePercent(value: number | null): boolean {
  return value !== null && value >= 0 && value <= MAX_SLIPPAGE_PERCENT;
}

export function isValidCostEditDraft(draft: ExecutionCostEditDraft): boolean {
  return (
    isValidFeePercent(parseCostPercentInput(draft.feePercent)) &&
    isValidSlippagePercent(parseCostPercentInput(draft.slippagePercent))
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

export function executionCostEditMessage(
  draft: ExecutionCostEditDraft,
  t: Translate,
): string | null {
  const fee = parseCostPercentInput(draft.feePercent);
  const slippage = parseCostPercentInput(draft.slippagePercent);
  if (!isValidFeePercent(fee) || !isValidSlippagePercent(slippage)) {
    return null;
  }
  return t("chat.confirmation.cost_editor.message", {
    defaultValue: "Set fees to {{fee}}% and slippage to {{slippage}}% per trade.",
    fee: formatPercentValue(fee as number),
    slippage: formatPercentValue(slippage as number),
  });
}

function formatPercentValue(value: number): string {
  const rounded = Math.round(value * 10000) / 10000;
  return String(rounded);
}
