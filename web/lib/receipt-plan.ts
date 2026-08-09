import type {
  PublicReceiptPayload,
  PublicReceiptStrategyFactKey,
} from "./public-receipt-contract";
import { interpolate, type ReceiptCopy } from "./receipt-copy";

/**
 * Turns the frozen strategy facts into one or two sentences a person can read.
 *
 * The facts stay frozen, closed, and complete in the payload; this composes them
 * at view time, in the viewer's language, the same way the field labels already
 * do. Twelve label and value pairs is a correct description of a crossover and
 * nobody reads it, so the same truth is stated as prose and the exact settings
 * move to the fine print.
 */
export type ReceiptPlan = {
  /** One or two sentences, in the viewer's language. */
  sentences: string[];
  /** Every frozen fact, for the fine print, in payload order. */
  settings: { key: PublicReceiptStrategyFactKey; value: string }[];
};

/** Indicator names are frozen lowercase; they are acronyms and read as such. */
function indicatorName(value: string | undefined): string {
  if (!value) return "";
  return /^[a-z]{2,5}$/.test(value) ? value.toUpperCase() : value;
}

export function receiptPlan(
  payload: PublicReceiptPayload,
  copy: ReceiptCopy,
): ReceiptPlan {
  const facts = new Map<string, string>(
    payload.strategy_facts.map((fact) => [fact.key, fact.value]),
  );
  const plan = copy.plan;
  const read = (key: string) => facts.get(key);
  const sentences: string[] = [];

  const shape = read("strategy_type") ?? "";
  if (facts.has("fast_period") && facts.has("slow_period")) {
    if (shape.includes("macd")) {
      sentences.push(
        interpolate(plan.macd, {
          fast_period: read("fast_period") ?? "",
          slow_period: read("slow_period") ?? "",
          signal_period: read("signal_period") ?? "",
        }),
      );
    } else {
      sentences.push(
        interpolate(plan.crossover, {
          fast_period: read("fast_period") ?? "",
          fast_indicator: indicatorName(read("fast_indicator")),
          slow_period: read("slow_period") ?? "",
          slow_indicator: indicatorName(read("slow_indicator")),
        }),
      );
      // The exit side only carries its own facts when it differs from the entry,
      // so its absence is the statement that it mirrors the entry.
      sentences.push(
        facts.has("exit_fast_period")
          ? interpolate(plan.crossover_exit_own, {
              fast_period: read("exit_fast_period") ?? "",
              fast_indicator: indicatorName(read("exit_fast_indicator")),
              slow_period: read("exit_slow_period") ?? "",
              slow_indicator: indicatorName(read("exit_slow_indicator")),
            })
          : plan.crossover_exit_mirrored,
      );
    }
  } else if (facts.has("indicator") && facts.has("entry_threshold")) {
    sentences.push(
      interpolate(plan.indicator, {
        indicator: indicatorName(read("indicator")),
        entry: read("entry_threshold") ?? "",
        exit: read("exit_threshold") ?? "",
      }),
    );
  } else if (facts.has("cadence")) {
    const cadence = read("cadence") ?? "";
    const phrase =
      (copy.cadence_values as Record<string, string>)[cadence] ?? cadence;
    sentences.push(interpolate(plan.dca, { cadence: phrase }));
  } else if (shape.includes("dip")) {
    sentences.push(plan.buy_the_dip);
  } else if (shape.includes("buy and hold")) {
    sentences.push(plan.buy_and_hold);
  } else {
    sentences.push(
      interpolate(plan.unnamed, { label: payload.strategy_label ?? shape }),
    );
  }

  return {
    sentences: sentences.filter(Boolean),
    settings: payload.strategy_facts
      .filter((fact) => fact.key !== "strategy_type")
      .map((fact) => ({ key: fact.key, value: fact.value })),
  };
}

/**
 * The one comparison the page exists to make, stated as a phrase.
 *
 * Both numbers are frozen display strings, so this parses them for the delta and
 * says nothing rather than guessing when either will not parse.
 */
export function benchmarkVerdict(
  payload: PublicReceiptPayload,
  copy: ReceiptCopy,
): string | null {
  const symbol = payload.benchmark_symbol;
  if (!symbol) return null;
  const find = (...keys: string[]) =>
    payload.metrics.find((metric) => keys.includes(metric.key))?.value ?? null;
  const mine = find("total_return_pct", "total_return");
  const theirs = find("benchmark_return_pct", "benchmark_return");
  if (!theirs) return null;

  const parse = (value: string) => {
    const match = value.replace(/,/g, "").match(/-?\d+(\.\d+)?/);
    return match ? Number.parseFloat(match[0]) : null;
  };
  const left = mine ? parse(mine) : null;
  const right = parse(theirs);
  if (left === null || right === null) {
    return interpolate(copy.hero.vs, { symbol, value: theirs });
  }
  const delta = left - right;
  const rounded = `${Math.abs(delta).toFixed(1)} pts`;
  return interpolate(delta >= 0 ? copy.hero.ahead : copy.hero.behind, {
    value: rounded,
    symbol,
  });
}
