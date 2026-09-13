import type { ExecutionCostEvidence } from "@/components/chat/types";
import { benchmarkClaim, type BenchmarkComparisonClaim } from "./result-figures";
import { canonicalStrategyType } from "./strategy-display";
import { resultRuleGroups, type ResultRuleGroup } from "./result-readout-rules";

/**
 * Reader-safe projection. Deliberately has no place for retained source prose.
 * Every percentage below is a display figure the backend rounded once; the
 * client prints it verbatim and never reads the two-decimal metrics to show it.
 */
export type ResultReadoutFacts = {
  symbols: string[];
  strategyType?: string;
  dateRange?: { start: string; end: string };
  benchmarkSymbol?: string;
  totalReturnPct?: number;
  benchmarkReturnPct?: number;
  benchmarkDeltaPct?: number;
  benchmarkClaim?: BenchmarkComparisonClaim;
  maxDrawdownPct?: number;
  startingCapital?: number;
  recurringContribution?: number;
  contributionPeriod?: string;
  timeframe?: string;
  costs?: ExecutionCostEvidence;
  indicator?: { name: "rsi"; period?: number; entryThreshold?: number; exitThreshold?: number };
  rules?: ResultRuleGroup[];
};

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown> : {};
}

function number(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function string(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined;
}

/** Accepts the persisted result_fact_bank and the equivalent canonical run. */
export function resultReadoutFacts(value: unknown): ResultReadoutFacts | null {
  const bank = record(value);
  const config = record(bank.config_snapshot);
  const parameters = record(config.resolved_parameters);
  const strategy = record(config.resolved_strategy);
  // The backend's one-decimal display figures; a bank without them has no
  // printable figure, because printing the engine metrics would mean rounding.
  const figures = record(bank.figures);
  const strategyType = canonicalStrategyType(strategy.strategy_type)
    ?? canonicalStrategyType(config.template === "rsi_mean_reversion" ? "indicator_threshold" : config.template)
    ?? canonicalStrategyType(parameters.strategy_type);
  const symbols = Array.isArray(bank.symbols)
    ? bank.symbols.filter((symbol): symbol is string => typeof symbol === "string" && Boolean(symbol.trim()))
    : [];
  const totalReturnPct = number(figures.total_return_pct);
  if (symbols.length === 0 && totalReturnPct === undefined && !strategyType) return null;
  const dateRange = record(config.date_range);
  const start = string(config.start_date) ?? string(dateRange.start);
  const end = string(config.end_date) ?? string(dateRange.end);
  const card = record(bank.result_card ?? bank.conversation_result_card);
  const costData = record(card.execution_costs);
  const feeBps = number(costData.fee_bps);
  const slippageBps = number(costData.slippage_bps);
  const period = string(parameters.cadence) ?? string(strategy.contribution_period);
  const contributionPeriod = period && ["daily", "weekly", "biweekly", "monthly", "quarterly"].includes(period)
    ? period : undefined;
  const entry = record(strategy.entry_rule);
  const exit = record(strategy.exit_rule);
  const indicatorName = string(parameters.indicator) ?? string(entry.indicator);
  return {
    symbols,
    strategyType,
    dateRange: start && end ? { start, end } : undefined,
    benchmarkSymbol: string(bank.benchmark_symbol) ?? string(parameters.benchmark_symbol) ?? string(config.benchmark_symbol),
    totalReturnPct,
    benchmarkReturnPct: number(figures.benchmark_return_pct),
    // The engine's comparison, rounded by the backend. Never recomputed here.
    benchmarkDeltaPct: number(figures.delta_vs_benchmark_pct),
    benchmarkClaim: benchmarkClaim(figures.benchmark_comparison_claim),
    maxDrawdownPct: number(figures.max_drawdown_pct),
    startingCapital: strategyType === "dca_accumulation"
      ? number(parameters.starting_capital) ?? number(strategy.initial_capital)
      : number(config.starting_capital) ?? number(parameters.starting_capital) ?? number(strategy.capital_amount),
    recurringContribution: number(parameters.recurring_contribution) ?? number(strategy.recurring_contribution),
    contributionPeriod,
    timeframe: string(config.timeframe) ?? string(parameters.timeframe),
    indicator: indicatorName === "rsi" ? {
      name: "rsi", period: number(parameters.indicator_period) ?? number(entry.period),
      entryThreshold: number(parameters.entry_threshold) ?? number(entry.threshold),
      exitThreshold: number(parameters.exit_threshold) ?? number(exit.threshold),
    } : undefined,
    rules: resultRuleGroups(strategy.rule_spec ?? parameters.rule_spec ?? record(config.parameters).rule_spec),
    costs: feeBps !== undefined || slippageBps !== undefined ? {
      fee_bps: feeBps, slippage_bps: slippageBps,
      gross_total_return_pct: number(figures.gross_total_return_pct),
      net_total_return_pct: number(figures.net_total_return_pct),
      benchmark_treatment: costData.benchmark_treatment === "same_modeled_costs" ? "same_modeled_costs" : undefined,
    } : undefined,
  };
}
