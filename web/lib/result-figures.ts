/**
 * Locale rendering for result figures the backend already rounded (#533).
 *
 * Every figure the result card, the Quick Take, the breakdown, the Try next
 * reason, and the dossier share (returns, the benchmark gap, worst drop,
 * modeled-cost returns) reaches the client at one decimal, rounded once by the
 * backend and carried as `figures` beside the engine metrics. Nothing here
 * rounds: it prints the digits it was given with the workspace locale's
 * decimal separator and grouping, so no two surfaces can print two numbers
 * for one fact.
 */

const FIGURE_DECIMALS = 1;

export function figureText(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    minimumFractionDigits: FIGURE_DECIMALS,
    maximumFractionDigits: FIGURE_DECIMALS,
  }).format(value);
}

export function percentText(value: number, locale: string): string {
  return `${figureText(value, locale)}%`;
}

export function signedPercentText(value: number, locale: string): string {
  return `${value > 0 ? "+" : ""}${percentText(value, locale)}`;
}

export type BenchmarkComparisonClaim = "beat" | "lagged" | "matched";

const BACKEND_CLAIMS: Record<string, BenchmarkComparisonClaim> = {
  beat_benchmark: "beat",
  lagged_benchmark: "lagged",
  matched_benchmark: "matched",
};

/** The backend's comparison claim; anything else is no claim at all. */
export function benchmarkClaim(value: unknown): BenchmarkComparisonClaim | undefined {
  return typeof value === "string" ? BACKEND_CLAIMS[value] : undefined;
}

export type BenchmarkComparisonView = {
  claim: BenchmarkComparisonClaim;
  /** Unsigned, one decimal, in percentage points, in the workspace locale. */
  magnitude: string;
};

export function benchmarkComparisonView(
  claim: BenchmarkComparisonClaim,
  deltaPct: number,
  locale: string,
): BenchmarkComparisonView {
  return { claim, magnitude: figureText(Math.abs(deltaPct), locale) };
}
