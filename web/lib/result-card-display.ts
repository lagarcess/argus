import type { StrategyResultPayload } from "@/components/chat/types";
import type { AssetClass } from "@/lib/argus-types";
import { assetClassDisplayLabel } from "@/lib/asset-class-display";
import { cadenceDisplayLabel } from "@/lib/cadence-display";
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
  comparedWithBenchmarkLabel: string;
  comparedWithSymbolLabel: (symbol: string) => string;
  worstDropLabel: string;
  explainResultAction: string;
  refineIdeaAction: string;
  saveAction: string;
  unavailable: string;
  returnUnavailable: string;
  changeNoun: string;
  gainNoun: string;
  lossNoun: string;
  totalReturnSuffix: string;
  benchmarkUnavailable: string;
  percentagePoints: (value: string) => string;
  inLineWith: (symbol: string) => string;
  beatBy: (value: string) => string;
  laggedBy: (value: string) => string;
  assetClassLabel: (assetClass: AssetClass) => string;
  trustStrip: string;
  startingCapitalLabel: string;
  totalContributedLabel: string;
  peakValueLabel: string;
  lowestValueLabel: string;
  dateRangeLabel: string;
  timeframeLabel: string;
  sideLabel: string;
  allocationLabel: string;
  benchmarkLabel: string;
  cadenceLabel: string;
  cadenceValueLabel: (cadence: string) => string;
  contributionLabel: string;
  entryRuleLabel: string;
  exitRuleLabel: string;
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
  comparedWithBenchmarkLabel: "Compared with benchmark",
  comparedWithSymbolLabel: (symbol) => `Compared with ${symbol}`,
  worstDropLabel: "Worst drop",
  explainResultAction: "Explain result",
  refineIdeaAction: "Refine idea",
  saveAction: "Save",
  unavailable: "Unavailable",
  returnUnavailable: "return unavailable",
  changeNoun: "change",
  gainNoun: "gain",
  lossNoun: "loss",
  totalReturnSuffix: "total return",
  benchmarkUnavailable: "Benchmark unavailable",
  percentagePoints: (value) => `${value} percentage points`,
  inLineWith: (symbol) => `In line with ${symbol}`,
  beatBy: (value) => `Beat by ${value}`,
  laggedBy: (value) => `Lagged by ${value}`,
  assetClassLabel: (assetClass) => assetClassDisplayLabel(assetClass) ?? assetClass,
  trustStrip: "Historical simulation · No fees/slippage · Not advice",
  startingCapitalLabel: "Starting capital",
  totalContributedLabel: "Total contributed",
  peakValueLabel: "Peak value",
  lowestValueLabel: "Lowest value",
  dateRangeLabel: "Date range",
  timeframeLabel: "Timeframe",
  sideLabel: "Side",
  allocationLabel: "Allocation",
  benchmarkLabel: "Benchmark",
  cadenceLabel: "Cadence",
  cadenceValueLabel: (cadence) => cadenceDisplayLabel(cadence) ?? cadence,
  contributionLabel: "Contribution",
  entryRuleLabel: "Entry rule",
  exitRuleLabel: "Exit rule",
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
    metric.key === "final_value" ||
    metric.label === "Cash Value ($)" ||
    metric.label === "Final Value ($)" ||
    metric.label === "Ending value"
  ) {
    return 0;
  }
  if (
    metric.key === "total_return_pct" ||
    metric.label === "Total Return (%)" ||
    metric.label === "Total Return" ||
    metric.label === "Total return"
  ) {
    return 1;
  }
  if (
    metric.key === "benchmark_delta" ||
    metric.key === "benchmark_delta_pct" ||
    metric.label === "Vs benchmark" ||
    metric.label.startsWith("Compared with ")
  ) {
    return 2;
  }
  if (
    metric.key === "max_drawdown_pct" ||
    metric.key === "max_drawdown" ||
    metric.label === "Max Drawdown" ||
    metric.label === "Worst drop"
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
  if (
    metric.key === "total_return_pct" ||
    metric.label === "Total Return (%)" ||
    metric.label === "Total Return"
  ) {
    return copy.totalReturnLabel;
  }
  if (
    metric.key === "cash_value" ||
    metric.key === "final_value" ||
    metric.label === "Cash Value ($)" ||
    metric.label === "Final Value ($)"
  ) {
    return copy.endingValueLabel;
  }
  if (
    metric.key === "max_drawdown_pct" ||
    metric.key === "max_drawdown" ||
    metric.label === "Max Drawdown"
  ) {
    return copy.worstDropLabel;
  }
  if (
    metric.key === "benchmark_delta" ||
    metric.key === "benchmark_delta_pct" ||
    metric.label === "Vs benchmark"
  ) {
    if (benchmarkSymbol) {
      return benchmarkLabel(benchmarkSymbol, copy);
    }
    if (metric.label.startsWith("Compared with ")) {
      return metric.label;
    }
    return benchmarkLabel(benchmarkSymbol, copy);
  }
  return metric.label;
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
  if (action.type === "save_strategy") {
    return copy.saveAction;
  }
  return action.label ?? "";
}

export function displayResultBenchmarkNote(note?: string | null) {
  const text = note?.trim();
  if (!text) return undefined;

  const normalized = text.toLowerCase();
  const repeatsBenchmarkOrUniverse =
    normalized.includes("benchmark:") ||
    normalized.includes("referencia:") ||
    normalized.startsWith("universe:") ||
    normalized.startsWith("universo:");

  return repeatsBenchmarkOrUniverse ? undefined : text;
}

type EvidenceTone = "positive" | "negative" | "neutral";

type EvidenceMetric = {
  label: string;
  value: string;
};

type HeroEvidence = {
  value: string;
  label: string;
  detail: string;
  tone: EvidenceTone;
};

type HeroDeltaEvidenceView = {
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
  const endingValue = findMetric(result, [
    copy.endingValueLabel,
    "Ending value",
    "Cash Value ($)",
    "Final Value ($)",
  ]);
  const totalReturn = findMetric(result, [
    copy.totalReturnLabel,
    "Total return",
    "Total Return",
    "Total Return (%)",
  ]);
  const benchmark = findBenchmarkMetric(result, copy);
  const worstDrop = findMetric(result, [
    copy.worstDropLabel,
    "Worst drop",
    "Max Drawdown",
  ]);
  const parsedEndingValue = parseEndingValue(endingValue?.value, options?.locale);
  const totalReturnValue = normalizeSignedPercent(totalReturn?.value);
  const tone = evidenceTone(parsedEndingValue?.change, totalReturnValue);
  const facts = executionFacts(result, parsedEndingValue?.start, copy, options?.locale);
  const benchmarkSymbol = facts.benchmark ?? benchmarkSymbolFromMetric(benchmark);

  return {
    hero: {
      value: parsedEndingValue?.endingDisplay ?? endingValue?.value ?? copy.unavailable,
      label: copy.endingValueLabel,
      detail: heroDetail(parsedEndingValue?.change, totalReturnValue, copy, options?.locale),
      tone,
    },
    benchmark: {
      label: benchmarkLabel(benchmarkSymbol, copy),
      value: benchmarkDisplayValue(benchmark, copy),
    },
    worstDrop: {
      label: copy.worstDropLabel,
      value: worstDrop?.value ?? copy.unavailable,
    },
    timeframeDisplay: facts.timeframeDisplay,
    trustGroups: compactTrustGroups(copy, result.assetClass),
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

function findMetric(result: StrategyResultPayload, labels: string[]) {
  const normalizedLabels = labels.map((label) => label.toLowerCase());
  return result.metrics.find(
    (metric) => normalizedLabels.includes(metric.label.toLowerCase()),
  );
}

function findBenchmarkMetric(
  result: StrategyResultPayload,
  copy = defaultResultCardDisplayCopy,
) {
  const labels = [
    "vs benchmark",
    "compared with ",
    "comparado con ",
    copy.comparedWithBenchmarkLabel.toLowerCase(),
  ];
  return result.metrics.find((metric) =>
    labels.some((label) => metric.label.toLowerCase().startsWith(label)),
  );
}

function executionFacts(
  result: StrategyResultPayload,
  parsedStartingCapital: number | undefined,
  copy: ResultCardDisplayCopy,
  locale?: string,
) {
  const assumptions = normalizedAssumptions(result);
  const config = result.configSnapshot;
  const resolvedParameters = recordValue(config?.resolved_parameters);
  const parameters = recordValue(config?.parameters);
  const timeframe =
    stringValue(config?.timeframe) ??
    stringValue(resolvedParameters?.timeframe) ??
    assumptionValue(assumptions, "Timeframe");
  const benchmark =
    stringValue(resolvedParameters?.benchmark_symbol) ??
    stringValue(config?.benchmark_symbol) ??
    assumptionValue(assumptions, "Benchmark") ??
    benchmarkFromMetric(result);
  const contribution = contributionFromStructuredFacts(
    resolvedParameters,
    parameters,
    locale,
    copy,
  );
  const entryRule = assumptionValue(assumptions, "Entry");
  const exitRule = assumptionValue(assumptions, "Exit");
  const side = assumptions.find((assumption) => assumption.toLowerCase() === "long-only");
  const allocation = assumptions.find(
    (assumption) => assumption.toLowerCase() === "equal weight",
  );
  const startingCapital =
    parsedStartingCapital ?? result.chart?.base_value ?? undefined;
  const dateRangeDisplay =
    compactDateRangeDisplay(result.dateRange, locale || "en-US") ?? result.period;
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
    timeframe ? { label: copy.timeframeLabel, value: timeframe } : undefined,
    side ? { label: copy.sideLabel, value: side } : undefined,
    allocation ? { label: copy.allocationLabel, value: allocation } : undefined,
    benchmark ? { label: copy.benchmarkLabel, value: benchmark } : undefined,
    contribution?.cadence ? { label: copy.cadenceLabel, value: contribution.cadence } : undefined,
    contribution?.amount ? { label: copy.contributionLabel, value: contribution.amount } : undefined,
    entryRule ? { label: copy.entryRuleLabel, value: entryRule } : undefined,
    exitRule ? { label: copy.exitRuleLabel, value: exitRule } : undefined,
  ].filter((detail): detail is EvidenceMetric => Boolean(detail));

  return {
    timeframeDisplay: formatTimeframeForDisplay(timeframe, copy),
    benchmark,
    details,
  };
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

function normalizedAssumptions(result: StrategyResultPayload) {
  return (result.assumptions ?? [])
    .map((assumption) => assumption.trim().replace(/[.]+$/, ""))
    .filter(Boolean)
    .filter((assumption) => !assumption.toLowerCase().startsWith("universe:"));
}

function assumptionValue(assumptions: string[], label: string) {
  const prefix = `${label}:`;
  const value = assumptions.find((assumption) =>
    assumption.toLowerCase().startsWith(prefix.toLowerCase()),
  );
  return value?.slice(prefix.length).trim();
}

function contributionFromStructuredFacts(
  resolvedParameters?: Record<string, unknown>,
  parameters?: Record<string, unknown>,
  locale?: string,
  copy = defaultResultCardDisplayCopy,
) {
  const rawCadence =
    stringValue(resolvedParameters?.cadence) ?? stringValue(parameters?.dca_cadence);
  if (!rawCadence) return undefined;

  const cadence = copy.cadenceValueLabel(rawCadence);
  const amount = numberValue(resolvedParameters?.capital_amount);
  return {
    cadence,
    amount: amount == null ? undefined : formatCurrency(amount, locale),
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

function benchmarkFromMetric(result: StrategyResultPayload) {
  const metric = findBenchmarkMetric(result);
  const match = metric?.label.match(/^Compared with\s+(.+)$/i);
  return match?.[1]?.trim() ?? benchmarkSymbolFromMetric(metric);
}

function benchmarkSymbolFromMetric(metric?: EvidenceMetric) {
  const valueSymbol = metric?.value.match(/\bvs\s+([A-Z0-9.-]+)\b/i)?.[1];
  if (valueSymbol) return valueSymbol;
  const labelSymbol = metric?.label.match(/^Compared with\s+(.+)$/i)?.[1]?.trim();
  return labelSymbol;
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
) {
  const returnLabel = totalReturn ?? copy.returnUnavailable;
  if (change == null) return returnLabel;
  if (Math.abs(change) < 0.5) {
    return `${formatCurrency(0, locale)} ${copy.changeNoun} · ${returnLabel} ${copy.totalReturnSuffix}`;
  }
  const sign = change > 0 ? "+" : "-";
  const noun = change > 0 ? copy.gainNoun : copy.lossNoun;
  return `${sign}${formatCurrency(Math.abs(change), locale)} ${noun} · ${returnLabel} ${copy.totalReturnSuffix}`;
}

function evidenceTone(change?: number, totalReturn?: string): EvidenceTone {
  const numericReturn =
    totalReturn == null ? undefined : Number(totalReturn.replace("%", ""));
  const basis = numericReturn ?? change;
  if (basis == null || Math.abs(basis) <= 0.5) return "neutral";
  return basis > 0 ? "positive" : "negative";
}

function benchmarkDisplayValue(
  metric: EvidenceMetric | undefined,
  copy: ResultCardDisplayCopy,
) {
  const value = metric?.value.trim();
  if (!value) return copy.benchmarkUnavailable;
  const benchmarkValue = value.match(
    /^([+-]?\d+(?:\.\d+)?)\s+(?:percentage points|pts)\s+vs\s+([A-Z0-9.-]+)$/i,
  );
  if (benchmarkValue) {
    const numericValue = Number(benchmarkValue[1]);
    const benchmarkSymbol = benchmarkValue[2];
    if (Math.abs(numericValue) < 0.05) return copy.inLineWith(benchmarkSymbol);
    const valueText = copy.percentagePoints(Math.abs(numericValue).toFixed(1));
    return numericValue > 0 ? copy.beatBy(valueText) : copy.laggedBy(valueText);
  }
  const namedBenchmarkValue = value.match(
    /^(Beat|Lagged)\s+(?:[A-Z0-9.-]+\s+)?by\s+([+-]?\d+(?:\.\d+)?)\s+(?:percentage points|pts)$/i,
  );
  if (namedBenchmarkValue) {
    const direction = namedBenchmarkValue[1].toLowerCase();
    const valueText = copy.percentagePoints(
      Math.abs(Number(namedBenchmarkValue[2])).toFixed(1),
    );
    return direction === "beat" ? copy.beatBy(valueText) : copy.laggedBy(valueText);
  }
  return value
    .replace(/^Beat\s+[A-Z0-9.-]+\s+by\s+(.+)$/i, (_, amount: string) =>
      copy.beatBy(amount),
    )
    .replace(/^Lagged\s+[A-Z0-9.-]+\s+by\s+(.+)$/i, (_, amount: string) =>
      copy.laggedBy(amount),
    )
    .replace(/^In line with\s+([A-Z0-9.-]+)$/i, (_, symbol: string) =>
      copy.inLineWith(symbol),
    )
    .replace(/\bpts\b/gi, "percentage points");
}

function formatCurrency(value: number, locale = "en-US", currency = "USD") {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    currencyDisplay: "narrowSymbol",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}
