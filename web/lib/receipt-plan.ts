import type {
  PublicReceiptAssumptionKey,
  PublicReceiptMetricKey,
  PublicReceiptPayload,
  PublicReceiptStrategyFactKey,
} from "./public-receipt-contract";
import {
  formatReceiptNumber,
  interpolate,
  type ReceiptCopy,
} from "./receipt-copy";
import type { ArgusLanguage } from "./language-features";

/**
 * Turns the frozen strategy facts into the rules a person can read.
 *
 * The facts stay frozen, closed and complete in the payload; this composes them at
 * view time, in the viewer's language, the same way the field labels already do.
 *
 * One row per rule, and only the rules that exist. Two of the five executable
 * strategies never sell (buy and hold and recurring buys both set every exit to
 * false in the engine), so a fixed buy-against-sell layout would be built around
 * the exception and leave the common case holding an empty half.
 */
export type ReceiptPlanRow = {
  /** The rule in plain words. */
  text: string;
  /** The frozen parameters behind it, or null when the rule has none to show. */
  exact: string | null;
};

export type ReceiptPlan = {
  rows: ReceiptPlanRow[];
  /** Every frozen fact, for the fine print, in payload order. */
  settings: { key: PublicReceiptStrategyFactKey; value: string }[];
};

/** Indicator names are frozen lowercase; they are acronyms and read as such. */
function indicatorName(value: string | undefined): string {
  if (!value) return "";
  return /^[a-z]{2,5}$/.test(value) ? value.toUpperCase() : value;
}

function joinExact(...parts: (string | undefined)[]): string | null {
  const kept = parts.filter((part): part is string => Boolean(part && part.trim()));
  return kept.length ? kept.join(" · ") : null;
}

export function receiptPlan(
  payload: PublicReceiptPayload,
  copy: ReceiptCopy,
): ReceiptPlan {
  const facts = new Map<string, string>(
    payload.strategy_facts.map((fact) => [fact.key, fact.value]),
  );
  const read = (key: string) => facts.get(key);
  const plan = copy.plan;
  const rows: ReceiptPlanRow[] = [];
  const shape = read("strategy_type") ?? "";

  if (facts.has("fast_period") && facts.has("slow_period")) {
    if (shape.includes("macd")) {
      rows.push({
        text: plan.macd_entry,
        exact: joinExact(read("fast_period"), read("slow_period"), read("signal_period")),
      });
      rows.push({ text: plan.macd_exit, exact: null });
    } else {
      rows.push({
        text: interpolate(plan.crossover_entry, {
          fast_period: read("fast_period") ?? "",
          slow_period: read("slow_period") ?? "",
        }),
        exact: joinExact(
          [indicatorName(read("fast_indicator")), read("fast_period")]
            .filter(Boolean)
            .join(" "),
          [indicatorName(read("slow_indicator")), read("slow_period")]
            .filter(Boolean)
            .join(" "),
        ),
      });
      // The exit side only carries its own facts when it differs from the entry, so
      // their absence is the statement that it mirrors the entry.
      const ownExit = facts.has("exit_fast_period");
      rows.push({
        text: ownExit
          ? interpolate(plan.crossover_exit_own, {
              fast_period: read("exit_fast_period") ?? "",
              slow_period: read("exit_slow_period") ?? "",
            })
          : plan.crossover_exit_mirrored,
        exact: ownExit
          ? joinExact(
              [indicatorName(read("exit_fast_indicator")), read("exit_fast_period")]
                .filter(Boolean)
                .join(" "),
              [indicatorName(read("exit_slow_indicator")), read("exit_slow_period")]
                .filter(Boolean)
                .join(" "),
            )
          : null,
      });
    }
  } else if (facts.has("indicator") && facts.has("entry_threshold")) {
    const indicator = indicatorName(read("indicator"));
    rows.push({
      text: interpolate(plan.indicator_entry, {
        indicator,
        entry: read("entry_threshold") ?? "",
      }),
      exact: joinExact([indicator, read("indicator_period")].filter(Boolean).join(" ")),
    });
    if (facts.has("exit_threshold")) {
      rows.push({
        text: interpolate(plan.indicator_exit, {
          indicator,
          exit: read("exit_threshold") ?? "",
        }),
        exact: null,
      });
    }
  } else if (facts.has("cadence")) {
    const cadence = read("cadence") ?? "";
    const phrase =
      (copy.cadence_values as Record<string, string>)[cadence] ?? cadence;
    // The cadence is already the subject of the sentence, so repeating it as a
    // parameter would say the same thing twice.
    rows.push({ text: interpolate(plan.dca, { cadence: phrase }), exact: null });
  } else if (shape.includes("dip")) {
    // Its trigger is fixed in the engine, so there is nothing frozen to show.
    rows.push({ text: plan.buy_the_dip, exact: null });
  } else if (shape.includes("buy and hold")) {
    rows.push({ text: plan.buy_and_hold, exact: null });
  } else {
    // The shape name is a closed token frozen by the projection, not a label in the
    // author's language, so it gets translated like every other key on this page.
    const named =
      (copy.strategy_type_values as Record<string, string>)[shape] ?? shape;
    rows.push({ text: interpolate(plan.unnamed, { label: named }), exact: null });
  }

  return {
    rows,
    settings: payload.strategy_facts
      .filter((fact) => fact.key !== "strategy_type")
      .map((fact) => ({ key: fact.key, value: fact.value })),
  };
}

/**
 * Turns the frozen assumptions into the fine print under the rules block.
 *
 * Same job as `receiptPlan` and for the same reason: the payload freezes keys and
 * bare scalars, and the language they are read in belongs to whoever opened the
 * link. Numbers get their separators here too, from the viewer's locale.
 *
 * Terse fragments, not sentences. This block sits below the rules as muted
 * one-liners, and the result card it replaced froze fragments of the same weight
 * ("Long-only", "Equal weight", "Benchmark: SPY"). Past-tense sentences with
 * terminal periods turn it into a second narration beside the one above it, which
 * is the shape this surface was redesigned out of.
 *
 * Two pairs read as one line each, the contribution with its cadence and the fee
 * with its slippage. They are separate frozen facts because either half can be
 * absent, but each pair is one thing to a reader and the app states it on one line.
 *
 * A key whose line needs a value it does not have is dropped. Half a fragment
 * about money is worse on this page than one fewer line.
 */
export function receiptAssumptions(
  payload: PublicReceiptPayload,
  copy: ReceiptCopy,
  language: ArgusLanguage,
): string[] {
  const values = new Map<PublicReceiptAssumptionKey, string>();
  for (const assumption of payload.assumptions) {
    if (assumption.value != null) values.set(assumption.key, assumption.value);
  }
  const said = copy.assumptions as Record<string, string>;
  const lines: string[] = [];
  const money = (key: PublicReceiptAssumptionKey) =>
    formatReceiptNumber(values.get(key), language);

  for (const assumption of payload.assumptions) {
    switch (assumption.key) {
      case "long_only":
      case "equal_weight":
      case "no_costs":
      case "fractional_shares":
        lines.push(said[assumption.key]);
        break;
      case "modeled_fee_bps": {
        // What a run cost is one thing to a reader, and the app states it on one
        // line, so the pair is composed here the way the contribution pair is. The
        // single-sided lines below only run when a payload carries just one.
        const fee = formatReceiptNumber(assumption.value, language);
        const slippage = formatReceiptNumber(
          values.get("modeled_slippage_bps"),
          language,
        );
        if (fee && slippage) {
          lines.push(interpolate(said.modeled_costs, { fee, slippage }));
        } else if (fee) {
          lines.push(interpolate(said.modeled_fee_bps, { bps: fee }));
        }
        break;
      }
      case "modeled_slippage_bps": {
        if (values.has("modeled_fee_bps")) break;
        const bps = formatReceiptNumber(assumption.value, language);
        if (bps) lines.push(interpolate(said.modeled_slippage_bps, { bps }));
        break;
      }
      case "benchmark":
      case "benchmark_same_modeled_costs": {
        if (assumption.value) {
          lines.push(
            interpolate(said[assumption.key], { symbol: assumption.value }),
          );
        }
        break;
      }
      case "recurring_contribution": {
        const amount = money("recurring_contribution");
        if (!amount) break;
        const token = values.get("contribution_cadence");
        const cadence = token
          ? ((copy.cadence_values as Record<string, string>)[token] ?? token)
          : null;
        lines.push(
          cadence
            ? interpolate(said.recurring_contribution_cadence, { amount, cadence })
            : interpolate(said.recurring_contribution, { amount }),
        );
        break;
      }
      case "starting_principal": {
        const amount = money("starting_principal");
        if (amount) lines.push(interpolate(said.starting_principal, { amount }));
        break;
      }
      // Spoken as part of the contribution sentence above, never on its own.
      case "contribution_cadence":
        break;
    }
  }
  return lines;
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
  const find = (key: PublicReceiptMetricKey) =>
    payload.metrics.find((metric) => metric.key === key)?.value ?? null;
  const parse = (value: string) => {
    const match = value.replace(/,/g, "").match(/-?\d+(\.\d+)?/);
    return match ? Number.parseFloat(match[0]) : null;
  };

  // The engine's own delta, when the payload carries it. Subtracting two already
  // rounded display strings can land a tenth of a point away from what the run
  // actually computed, and this page is a record.
  const frozenDelta = find("delta_vs_benchmark_pct");
  const theirs = find("benchmark_return_pct");
  const delta =
    frozenDelta !== null
      ? parse(frozenDelta)
      : (() => {
          const mine = find("total_return_pct");
          const left = mine ? parse(mine) : null;
          const right = theirs ? parse(theirs) : null;
          return left === null || right === null ? null : left - right;
        })();

  if (delta === null) {
    return theirs ? interpolate(copy.hero.vs, { symbol, value: theirs }) : null;
  }
  const rounded = `${Math.abs(delta).toFixed(1)} pts`;
  return interpolate(delta >= 0 ? copy.hero.ahead : copy.hero.behind, {
    value: rounded,
    symbol,
  });
}

/** What the benchmark itself did, for the line beside the headline number. */
export function benchmarkReturn(payload: PublicReceiptPayload): string | null {
  if (!payload.benchmark_symbol) return null;
  return (
    payload.metrics.find((metric) => metric.key === "benchmark_return_pct")
      ?.value ?? null
  );
}
