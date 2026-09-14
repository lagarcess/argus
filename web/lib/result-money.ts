import displayPolicy from "../argus_display_contract/result_display_policy.json";
import type { ResultChartPayload } from "@/components/chat/types";

/**
 * The precision a result's money is shown with, from the policy the backend
 * reads too (src/argus/domain/result_money.py). Whole dollars once the
 * portfolio reached `currency_cents_below`; under it, an amount that is not
 * whole shows its cents.
 */
export function resultMoneyFractionDigits(
  value: number,
  peakValue: number | null | undefined,
): number {
  if (
    peakValue == null ||
    !Number.isFinite(peakValue) ||
    Math.abs(peakValue) >= displayPolicy.currency_cents_below
  ) {
    return displayPolicy.currency_fraction_digits;
  }
  return Math.round(Math.abs(value) * 100) % 100 === 0
    ? displayPolicy.currency_fraction_digits
    : 2;
}

/** The highest value the run's portfolio series recorded. */
export function resultChartPeakValue(
  chart: ResultChartPayload | null | undefined,
): number | undefined {
  const values = (chart?.series ?? [])
    .map((point) => point.value)
    .filter((value) => typeof value === "number" && Number.isFinite(value));
  return values.length > 0 ? Math.max(...values) : undefined;
}
