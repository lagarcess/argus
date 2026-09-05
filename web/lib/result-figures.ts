/**
 * The one place a shared result figure becomes text (#533).
 *
 * The engine persists returns and the benchmark gap to two decimals; the
 * result card, the Quick Take, the breakdown, and the Try next reason all
 * print them to one. That rounding happens here and nowhere else, so two
 * surfaces on one screen cannot show two numbers for one fact.
 */

/**
 * Python's fixed-point formatting, which every backend-voiced copy of these
 * figures uses: the exact binary value, correctly rounded, ties to even.
 * `toFixed` rounds the same exact value but breaks a tie away from zero, and
 * at one decimal the only exact ties are the .25 fractions.
 */
export function tenthFigure(value: number): string {
  const magnitude = Math.abs(value);
  const text =
    magnitude % 1 === 0.25
      ? (Math.floor(magnitude) + 0.2).toFixed(1)
      : magnitude.toFixed(1);
  return value < 0 || Object.is(value, -0) ? `-${text}` : text;
}

export function signedPercentFigure(value: number): string {
  return `${value > 0 ? "+" : ""}${tenthFigure(value)}%`;
}

export type BenchmarkComparisonClaim = "beat" | "lagged" | "matched";

export type BenchmarkComparisonView = {
  claim: BenchmarkComparisonClaim;
  /** Unsigned, one decimal, in percentage points. */
  magnitude: string;
};

/**
 * In line means the gap rounds to nothing at the printed precision. That is
 * the same 0.05-point cut the backend claim uses, and deriving the claim from
 * the printed digits means the two can never disagree on one card.
 */
export function benchmarkComparisonView(deltaPct: number): BenchmarkComparisonView {
  const magnitude = tenthFigure(Math.abs(deltaPct));
  if (magnitude === "0.0") return { claim: "matched", magnitude };
  return { claim: deltaPct > 0 ? "beat" : "lagged", magnitude };
}
