import type { StrategyResultPayload } from "@/components/chat/types";
import type { AssetClass } from "@/lib/argus-types";
import { assetClassDisplayLabel } from "@/lib/asset-class-display";
import { contributionPhrase } from "@/lib/contribution-period-display";
import { compactDateRangeDisplay } from "@/lib/date-range-display";

type MetricLike = {
  key?: string;
  label: string;
  value?: string;
};

type ActionLike = {
  type?: string;
  label?: string;
};

export type ResultCardDisplayCopy = {
  endingValueLabel: string;
  totalReturnLabel: string;
  contributionReturnLabel: string;
  comparedWithBenchmarkLabel: string;
  comparedWithSymbolLabel: (symbol: string) => string;
  worstDropLabel: string;
  explainResultAction: string;
  refineIdeaAction: string;
  unavailable: string;
  returnUnavailable: string;
  changeNoun: string;
  gainNoun: string;
  lossNoun: string;
  totalReturnSuffix: string;
  contributionReturnSuffix: string;
  benchmarkUnavailable: string;
  percentagePoints: (value: string) => string;
  inLineWith: (symbol: string) => string;
  beatBy: (value: string) => string;
  laggedBy: (value: string) => string;
  assetClassLabel: (assetClass: AssetClass) => string;
  trustStrip: string;
  historicalSimulationLabel: string;
  notAdviceLabel: string;
  startingCapitalLabel: string;
  totalContributedLabel: string;
  peakValueLabel: string;
  lowestValueLabel: string;
  dateRangeLabel: string;
  timeframeLabel: string;
  sideLabel: string;
  allocationLabel: string;
  benchmarkLabel: string;
  /** Amount and period as one phrase, so no surface labels a period alone. */
  contributionPhrase: (amount: string, period: string) => string;
  contributionLabel: string;
  entryRuleLabel: string;
  exitRuleLabel: string;
  grossReturnLabel: string;
  netReturnLabel: string;
  modeledCostsLabel: string;
  modeledCostsValue: (feeBps: string, slippageBps: string) => string;
  benchmarkSameCostsValue: (benchmark: string) => string;
  dailyData: string;
  hourlyData: string;
  intervalData: (amount: number, unit: string) => string;
  timeframeData: (value: string) => string;
};

export type ResultCardDisplayOptions = {
  copy?: Partial<ResultCardDisplayCopy>;
  locale?: string;
};

export const defaultResultCardDisplayCopy: ResultCardDisplayCopy = {
  endingValueLabel: "Ending value",
  totalReturnLabel: "Total return",
  contributionReturnLabel: "Return on contributions",
  comparedWithBenchmarkLabel: "Compared with benchmark",
  comparedWithSymbolLabel: (symbol) => `Compared with ${symbol}`,
  worstDropLabel: "Worst drop",
  explainResultAction: "Explain result",
  refineIdeaAction: "Refine idea",
  unavailable: "Unavailable",
  returnUnavailable: "return unavailable",
  changeNoun: "change",
  gainNoun: "gain",
  lossNoun: "loss",
  totalReturnSuffix: "total return",
  contributionReturnSuffix: "return on contributions",
  benchmarkUnavailable: "Benchmark unavailable",
  percentagePoints: (value) => `${value} percentage points`,
  inLineWith: (symbol) => `In line with ${symbol}`,
  beatBy: (value) => `Beat by ${value}`,
  laggedBy: (value) => `Lagged by ${value}`,
  assetClassLabel: (assetClass) => assetClassDisplayLabel(assetClass) ?? assetClass,
  trustStrip: "Historical simulation · Not advice",
  historicalSimulationLabel: "Historical simulation",
  notAdviceLabel: "Not advice",
  startingCapitalLabel: "Starting capital",
  totalContributedLabel: "Total contributed",
  peakValueLabel: "Peak value",
  lowestValueLabel: "Lowest value",
  dateRangeLabel: "Date range",
  timeframeLabel: "Timeframe",
  sideLabel: "Side",
  allocationLabel: "Allocation",
  benchmarkLabel: "Benchmark",
  contributionPhrase: (amount, period) => contributionPhrase(amount, period),
  contributionLabel: "Contribution",
  entryRuleLabel: "Entry rule",
  exitRuleLabel: "Exit rule",
  grossReturnLabel: "Gross return",
  netReturnLabel: "Net of costs",
  modeledCostsLabel: "Costs modeled",
  modeledCostsValue: (feeBps, slippageBps) =>
    `${feeBps} bps fee + ${slippageBps} bps slippage`,
  benchmarkSameCostsValue: (benchmark) => `${benchmark} (same modeled costs)`,
  dailyData: "Daily data",
  hourlyData: "Hourly data",
  intervalData: (amount, unit) => `${amount}-${unit} data`,
  timeframeData: (value) => `${value} data`,
};

function resultCardCopy(options?: ResultCardDisplayOptions) {
  return {
    ...defaultResultCardDisplayCopy,
    ...options?.copy,
  };
}

function benchmarkLabel(
  benchmarkSymbol: string | null | undefined,
  copy = defaultResultCardDisplayCopy,
) {
  return benchmarkSymbol
    ? copy.comparedWithSymbolLabel(benchmarkSymbol)
    : copy.comparedWithBenchmarkLabel;
}

export function resultMetricDisplayOrder(metric: MetricLike) {
  if (
    metric.key === "cash_value" ||
    metric.key === "final_value" || metric.key === "ending_value"
  ) {
    return 0;
  }
  if (
    metric.key === "total_return_pct" ||
    metric.key === "contribution_return_pct"
  ) {
    return 1;
  }
  if (
    metric.key === "benchmark_delta" ||
    metric.key === "benchmark_delta_pct"
  ) {
    return 2;
  }
  if (
    metric.key === "max_drawdown_pct" ||
    metric.key === "max_drawdown"
  ) {
    return 3;
  }
  return 10;
}

export function displayResultMetricLabel(
  metric: MetricLike,
  benchmarkSymbol?: string | null,
  options?: ResultCardDisplayOptions,
) {
  const copy = resultCardCopy(options);
  if (metric.key === "contribution_return_pct") {
    return copy.contributionReturnLabel;
  }
  if (
    metric.key === "total_return_pct"
  ) {
    return copy.totalReturnLabel;
  }
  if (
    metric.key === "cash_value" ||
    metric.key === "final_value" || metric.key === "ending_value"
  ) {
    return copy.endingValueLabel;
  }
  if (
    metric.key === "max_drawdown_pct" ||
    metric.key === "max_drawdown"
  ) {
    return copy.worstDropLabel;
  }
  if (
    metric.key === "benchmark_delta" ||
    metric.key === "benchmark_delta_pct"
  ) {
    if (benchmarkSymbol) {
      return benchmarkLabel(benchmarkSymbol, copy);
    }
    return benchmarkLabel(benchmarkSymbol, copy);
  }
  return copy.unavailable;
}

export function displayResultActionLabel(
  action: ActionLike,
  options?: ResultCardDisplayOptions,
) {
  const copy = resultCardCopy(options);
  if (action.type === "show_breakdown") {
    return copy.explainResultAction;
  }
  if (action.type === "refine_strategy") {
    return copy.refineIdeaAction;
  }
  return action.label ?? "";
}

type EvidenceTone = "positive" | "negative" | "neutral";

type EvidenceMetric = {
  label: string;
  value: string;
  unavailable?: boolean;
};

type HeroEvidence = {
  value: string;
  label: string;
  detail: string;
  tone: EvidenceTone;
  unavailable?: boolean;
};

export type HeroDeltaEvidenceView = {
  hero: HeroEvidence;
  benchmark: EvidenceMetric;
  worstDrop: EvidenceMetric;
  timeframeDisplay?: string;
  trustGroups: string[];
  details: EvidenceMetric[];
};

const CURRENCY_VALUE_PATTERN = /[-+]?\$[\d,]+(?:\.\d+)?\s?[KMBkmb]?/g;
const PERCENT_VALUE_PATTERN = /[-+]?\d+(?:\.\d+)?%/;
export function heroDeltaEvidenceView(
  result: StrategyResultPayload,
  options?: ResultCardDisplayOptions,
): HeroDeltaEvidenceView {
  const copy = resultCardCopy(options);
  const endingValue = findMetric(result, ["cash_value", "final_value", "ending_value"]);
  const totalReturn = findMetric(result, ["total_return_pct", "contribution_return_pct"]);
  const worstDrop = findMetric(result, ["max_drawdown_pct", "max_drawdown"]);
  const parsedEndingValue = parseEndingValue(endingValue?.value, options?.locale);
  const typedFacts = result.readoutFacts;
  const totalReturnValue = typedFacts?.totalReturnPct !== undefined
    ? formatSignedPercent(typedFacts.totalReturnPct)
    : normalizeSignedPercent(totalReturn?.value);
  const isContributionReturn =
    totalReturn?.key === "contribution_return_pct" || typedFacts?.strategyType === "dca_accumulation";
  const tone = evidenceTone(parsedEndingValue?.change, totalReturnValue);
  const facts = executionFacts(result, parsedEndingValue?.start, copy, options?.locale);
  const benchmarkSymbol = facts.benchmark;
  const delta = typedFacts?.benchmarkDeltaPct;
  const benchmarkValue = delta === undefined || !benchmarkSymbol ? copy.benchmarkUnavailable
    : Math.abs(delta) < 0.05 ? copy.inLineWith(benchmarkSymbol)
    : delta > 0 ? copy.beatBy(copy.percentagePoints(Math.abs(delta).toFixed(1)))
    : copy.laggedBy(copy.percentagePoints(Math.abs(delta).toFixed(1)));

  return {
    hero: {
      value: parsedEndingValue?.endingDisplay ?? copy.unavailable,
      label: copy.endingValueLabel,
      detail: heroDetail(
        parsedEndingValue?.change,
        totalReturnValue,
        copy,
        options?.locale,
        isContributionReturn ? copy.contributionReturnSuffix : undefined,
      ),
      tone,
      // Unavailable values must read as absent, never as a healthy metric.
      unavailable: !parsedEndingValue?.endingDisplay,
    },
    benchmark: {
      label: benchmarkLabel(benchmarkSymbol, copy),
      value: benchmarkValue,
      unavailable: delta === undefined || !benchmarkSymbol,
    },
    worstDrop: {
      label: copy.worstDropLabel,
      value: typedFacts?.maxDrawdownPct !== undefined ? formatSignedPercent(typedFacts.maxDrawdownPct) : normalizeSignedPercent(worstDrop?.value) ?? copy.unavailable,
      unavailable: typedFacts?.maxDrawdownPct === undefined && !normalizeSignedPercent(worstDrop?.value),
    },
    timeframeDisplay: facts.timeframeDisplay,
    trustGroups: compactTrustGroups({ ...copy, trustStrip: result.executionCosts?.fee_bps != null && result.executionCosts?.slippage_bps != null
      ? [copy.historicalSimulationLabel, copy.modeledCostsValue(String(result.executionCosts.fee_bps), String(result.executionCosts.slippage_bps)), copy.notAdviceLabel].join(" · ")
      : copy.trustStrip }, result.assetClass),
    details: facts.details,
  };
}

export function compactTrustGroups(
  copy = defaultResultCardDisplayCopy,
  assetClass?: AssetClass,
) {
  const assetClassLabel = assetClass ? copy.assetClassLabel(assetClass) : undefined;
  return [
    assetClassLabel ? `${assetClassLabel} · ${copy.trustStrip}` : copy.trustStrip,
  ];
}

export function compactTrustStrip(copy = defaultResultCardDisplayCopy) {
  return compactTrustGroups(copy).join(" · ");
}

function findMetric(result: StrategyResultPayload, keys: string[]) {
  return result.metrics.find((metric) => metric.key !== undefined && keys.includes(metric.key));
}

function executionFacts(
  result: StrategyResultPayload,
  parsedStartingCapital: number | undefined,
  copy: ResultCardDisplayCopy,
  locale?: string,
) {
  const config = result.configSnapshot;
  const resolvedParameters = recordValue(config?.resolved_parameters);
  const parameters = recordValue(config?.parameters);
  const timeframe =
    stringValue(config?.timeframe) ??
    stringValue(resolvedParameters?.timeframe);
  const benchmark =
    result.readoutFacts?.benchmarkSymbol ?? stringValue(resolvedParameters?.benchmark_symbol) ??
    stringValue(config?.benchmark_symbol);
  const contribution = contributionFromStructuredFacts(
    resolvedParameters,
    parameters,
    locale,
    copy,
  );
  const startingCapital =
    parsedStartingCapital ?? result.chart?.base_value ?? undefined;
  const dateRangeDisplay =
    compactDateRangeDisplay(result.dateRange, locale || "en-US") ?? copy.unavailable;
  const capitalBasisLabel = isRecurringContributionResult(
    result,
    resolvedParameters,
  )
    ? copy.totalContributedLabel
    : copy.startingCapitalLabel;
  const valueSummaryDetails = portfolioValueSummaryDetails(result, copy, locale);
  const details: EvidenceMetric[] = [
    startingCapital == null
      ? undefined
      : { label: capitalBasisLabel, value: formatCurrency(startingCapital, locale) },
    ...valueSummaryDetails,
    { label: copy.dateRangeLabel, value: dateRangeDisplay },
    timeframe ? { label: copy.timeframeLabel, value: formatTimeframeForDisplay(timeframe, copy) ?? copy.unavailable } : undefined,
    benchmark
      ? {
          label: copy.benchmarkLabel,
          value: withBenchmarkCostTreatment(benchmark, result, copy),
        }
      : undefined,
    contribution?.startingCapital
      ? { label: copy.startingCapitalLabel, value: contribution.startingCapital }
      : undefined,
    contribution?.amount
      ? { label: copy.contributionLabel, value: contribution.amount }
      : undefined,
    ...executionCostDetails(result, copy),
  ].filter((detail): detail is EvidenceMetric => Boolean(detail));

  return {
    timeframeDisplay: formatTimeframeForDisplay(timeframe, copy),
    benchmark,
    details,
  };
}

function withBenchmarkCostTreatment(
  benchmark: string,
  result: StrategyResultPayload,
  copy: ResultCardDisplayCopy,
): string {
  // State the benchmark cost treatment from the structured payload; skip when
  // the value already carries it (older persisted cards fall back to the
  // backend assumption string, which includes the marker).
  if (
    result.executionCosts?.benchmark_treatment === "same_modeled_costs" &&
    !benchmark.includes("(")
  ) {
    return copy.benchmarkSameCostsValue(benchmark);
  }
  return benchmark;
}

function executionCostDetails(
  result: StrategyResultPayload,
  copy: ResultCardDisplayCopy,
): (EvidenceMetric | undefined)[] {
  // Structured cost evidence from the backend artifact payload; present only
  // when the engine modeled non-zero costs.
  const costs = result.executionCosts;
  if (!costs) {
    return [];
  }
  const gross = finiteNumber(costs.gross_total_return_pct);
  const net = finiteNumber(costs.net_total_return_pct);
  const feeBps = finiteNumber(costs.fee_bps);
  const slippageBps = finiteNumber(costs.slippage_bps);
  if (gross === undefined || net === undefined) {
    return [];
  }
  return [
    { label: copy.grossReturnLabel, value: formatSignedPercent(gross) },
    { label: copy.netReturnLabel, value: formatSignedPercent(net) },
    feeBps === undefined && slippageBps === undefined
      ? undefined
      : {
          label: copy.modeledCostsLabel,
          value: copy.modeledCostsValue(
            formatBpsValue(feeBps ?? 0),
            formatBpsValue(slippageBps ?? 0),
          ),
        },
  ];
}

function finiteNumber(value: number | null | undefined): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function formatSignedPercent(value: number): string {
  const rounded = value.toFixed(1);
  return `${value > 0 ? "+" : ""}${rounded}%`;
}

function formatBpsValue(value: number): string {
  const rounded = Math.round(value * 100) / 100;
  return String(rounded);
}

function portfolioValueSummaryDetails(
  result: StrategyResultPayload,
  copy: ResultCardDisplayCopy,
  locale?: string,
) {
  const summary = recordValue(result.chart?.value_summary);
  if (!summary) {
    const legacyExtrema = chartValueExtrema(result.chart);
    if (!legacyExtrema) {
      return [];
    }
    return [
      {
        label: copy.peakValueLabel,
        value: formatCurrency(legacyExtrema.peak, locale, legacyExtrema.currency),
      },
      {
        label: copy.lowestValueLabel,
        value: formatCurrency(legacyExtrema.lowest, locale, legacyExtrema.currency),
      },
    ];
  }
  const source = stringValue(summary.source);
  if (source && source !== "strategy_portfolio_equity_close") {
    return [];
  }
  const peakValue = numberValue(summary.peak_value);
  const lowestValue = numberValue(summary.lowest_value);
  return [
    peakValue == null
      ? undefined
      : { label: copy.peakValueLabel, value: formatCurrency(peakValue, locale) },
    lowestValue == null
      ? undefined
      : { label: copy.lowestValueLabel, value: formatCurrency(lowestValue, locale) },
  ].filter((detail): detail is EvidenceMetric => Boolean(detail));
}

function isRecurringContributionResult(
  result: StrategyResultPayload,
  resolvedParameters: Record<string, unknown> | undefined,
) {
  const template =
    stringValue(result.template) ??
    stringValue(result.configSnapshot?.template) ??
    stringValue(resolvedParameters?.strategy_type);
  return template === "dca_accumulation";
}

function recordValue(value: unknown) {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function stringValue(value: unknown) {
  return typeof value === "string" && value.trim().length > 0
    ? value.trim()
    : undefined;
}

function contributionFromStructuredFacts(
  resolvedParameters?: Record<string, unknown>,
  parameters?: Record<string, unknown>,
  locale?: string,
  copy = defaultResultCardDisplayCopy,
) {
  const rawPeriod =
    stringValue(resolvedParameters?.cadence) ?? stringValue(parameters?.dca_cadence);
  if (!rawPeriod) return undefined;

  // One phrase, because nobody has a period without an amount. The seed is the
  // plan's other role and gets its own row.
  const amount = numberValue(resolvedParameters?.recurring_contribution);
  const startingCapital = numberValue(resolvedParameters?.starting_capital);
  return {
    amount:
      amount == null
        ? undefined
        : copy.contributionPhrase(formatCurrency(amount, locale), rawPeriod),
    startingCapital:
      startingCapital == null
        ? undefined
        : formatCurrency(startingCapital, locale),
  };
}

function numberValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function chartValueExtrema(chart: StrategyResultPayload["chart"]) {
  const peak = numberValue(chart?.value_extrema?.peak?.value);
  const lowest = numberValue(chart?.value_extrema?.lowest?.value);
  if (peak == null || lowest == null) return undefined;
  return {
    peak,
    lowest,
    currency: chart?.currency ?? "USD",
  };
}

export function formatTimeframeForDisplay(
  timeframe?: string,
  copy = defaultResultCardDisplayCopy,
) {
  const value = timeframe?.trim();
  if (!value) return undefined;

  const normalized = value.toLowerCase().replace(/\s+/g, "");
  if (normalized === "daily" || normalized === "1d" || normalized === "1day") {
    return copy.dailyData;
  }
  if (normalized === "hourly" || normalized === "1h" || normalized === "1hour") {
    return copy.hourlyData;
  }

  const compactMatch = normalized.match(/^(\d+)(m|minute|minutes|h|hour|hours|d|day|days|w|week|weeks)$/);
  if (compactMatch) {
    const amount = Number(compactMatch[1]);
    const unit = compactMatch[2][0];
    return copy.intervalData(amount, timeframeUnitLabel(unit));
  }

  return copy.timeframeData(value);
}

function timeframeUnitLabel(unit: string) {
  if (unit === "m") return "minute";
  if (unit === "h") return "hour";
  if (unit === "d") return "day";
  if (unit === "w") return "week";
  return "period";
}

function parseEndingValue(value?: string, locale?: string) {
  const matches = value?.match(CURRENCY_VALUE_PATTERN) ?? [];
  if (matches.length === 0) return undefined;

  const firstValue = matches[0];
  const lastValue = matches.at(-1);
  if (!firstValue || !lastValue) return undefined;

  const start = matches.length >= 2 ? parseCurrency(firstValue) : undefined;
  const ending = parseCurrency(lastValue);
  return {
    start,
    ending,
    change: start == null ? undefined : ending - start,
    endingDisplay: formatCurrency(ending, locale),
  };
}

function parseCurrency(value: string) {
  const compactSuffix = value.trim().match(/[KMB]$/i)?.[0]?.toUpperCase();
  const multiplier =
    compactSuffix === "K"
      ? 1_000
      : compactSuffix === "M"
        ? 1_000_000
        : compactSuffix === "B"
          ? 1_000_000_000
          : 1;
  return Number(value.replace(/[$,\sKMB]/gi, "")) * multiplier;
}

function normalizeSignedPercent(value?: string) {
  const match = value?.match(PERCENT_VALUE_PATTERN)?.[0];
  if (!match) return undefined;
  const numeric = Number(match.replace("%", ""));
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(1)}%`;
}

function heroDetail(
  change: number | undefined,
  totalReturn: string | undefined,
  copy: ResultCardDisplayCopy,
  locale?: string,
  returnSuffix?: string,
) {
  const suffix = returnSuffix ?? copy.totalReturnSuffix;
  const returnLabel = totalReturn ?? copy.returnUnavailable;
  if (change == null) return returnLabel;
  if (Math.abs(change) < 0.5) {
    return `${formatCurrency(0, locale)} ${copy.changeNoun} · ${returnLabel} ${suffix}`;
  }
  const sign = change > 0 ? "+" : "-";
  const noun = change > 0 ? copy.gainNoun : copy.lossNoun;
  return `${sign}${formatCurrency(Math.abs(change), locale)} ${noun} · ${returnLabel} ${suffix}`;
}

function evidenceTone(change?: number, totalReturn?: string): EvidenceTone {
  const numericReturn =
    totalReturn == null ? undefined : Number(totalReturn.replace("%", ""));
  const basis = numericReturn ?? change;
  if (basis == null || Math.abs(basis) <= 0.5) return "neutral";
  return basis > 0 ? "positive" : "negative";
}

export function formatCurrency(value: number, locale = "en-US", currency = "USD") {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}
