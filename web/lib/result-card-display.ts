import type { StrategyResultPayload } from "@/components/chat/types";

type MetricLike = {
  key?: string;
  label: string;
  value?: string;
};

type ActionLike = {
  type?: string;
  label?: string;
};

function benchmarkLabel(benchmarkSymbol?: string | null) {
  return benchmarkSymbol ? `Compared with ${benchmarkSymbol}` : "Compared with benchmark";
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
) {
  if (
    metric.key === "total_return_pct" ||
    metric.label === "Total Return (%)" ||
    metric.label === "Total Return"
  ) {
    return "Total return";
  }
  if (
    metric.key === "cash_value" ||
    metric.key === "final_value" ||
    metric.label === "Cash Value ($)" ||
    metric.label === "Final Value ($)"
  ) {
    return "Ending value";
  }
  if (
    metric.key === "max_drawdown_pct" ||
    metric.key === "max_drawdown" ||
    metric.label === "Max Drawdown"
  ) {
    return "Worst drop";
  }
  if (
    metric.key === "benchmark_delta" ||
    metric.key === "benchmark_delta_pct" ||
    metric.label === "Vs benchmark"
  ) {
    if (metric.label.startsWith("Compared with ")) {
      return metric.label;
    }
    return benchmarkLabel(benchmarkSymbol);
  }
  return metric.label;
}

export function displayResultActionLabel(action: ActionLike) {
  if (action.type === "show_breakdown") {
    return "Explain result";
  }
  if (action.type === "refine_strategy") {
    return "Refine idea";
  }
  if (action.type === "save_strategy") {
    return "Save";
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
const TRUST_STRIP = "Historical simulation · No fees/slippage · Not advice";

export function heroDeltaEvidenceView(
  result: StrategyResultPayload,
): HeroDeltaEvidenceView {
  const endingValue = findMetric(result, "Ending value");
  const totalReturn = findMetric(result, "Total return");
  const benchmark = findMetricByPrefix(result, "Compared with");
  const worstDrop = findMetric(result, "Worst drop");
  const parsedEndingValue = parseEndingValue(endingValue?.value);
  const totalReturnValue = normalizeSignedPercent(totalReturn?.value);
  const tone = evidenceTone(parsedEndingValue?.change, totalReturnValue);
  const facts = executionFacts(result, parsedEndingValue?.start);

  return {
    hero: {
      value: parsedEndingValue?.endingDisplay ?? endingValue?.value ?? "Unavailable",
      label: "Ending value",
      detail: heroDetail(parsedEndingValue?.change, totalReturnValue),
      tone,
    },
    benchmark: {
      label: benchmark?.label ?? "Compared with benchmark",
      value: benchmarkDisplayValue(benchmark),
    },
    worstDrop: {
      label: "Worst drop",
      value: worstDrop?.value ?? "Unavailable",
    },
    timeframeDisplay: facts.timeframeDisplay,
    trustGroups: compactTrustGroups(),
    details: facts.details,
  };
}

export function compactTrustGroups() {
  return [TRUST_STRIP];
}

export function compactTrustStrip() {
  return compactTrustGroups().join(" · ");
}

function findMetric(result: StrategyResultPayload, label: string) {
  return result.metrics.find(
    (metric) => metric.label.toLowerCase() === label.toLowerCase(),
  );
}

function findMetricByPrefix(result: StrategyResultPayload, prefix: string) {
  return result.metrics.find((metric) =>
    metric.label.toLowerCase().startsWith(prefix.toLowerCase()),
  );
}

function executionFacts(result: StrategyResultPayload, parsedStartingCapital?: number) {
  const assumptions = normalizedAssumptions(result);
  const config = result.configSnapshot;
  const resolvedParameters = recordValue(config?.resolved_parameters);
  const parameters = recordValue(config?.parameters);
  const timeframe =
    stringValue(config?.timeframe) ??
    stringValue(resolvedParameters?.timeframe) ??
    assumptionValue(assumptions, "Timeframe");
  const benchmark =
    stringValue(config?.benchmark_symbol) ??
    stringValue(resolvedParameters?.benchmark_symbol) ??
    assumptionValue(assumptions, "Benchmark") ??
    benchmarkFromMetric(result);
  const contribution =
    contributionFromStructuredFacts(resolvedParameters, parameters) ??
    contributionFromAssumptions(assumptions);
  const entryRule = assumptionValue(assumptions, "Entry");
  const exitRule = assumptionValue(assumptions, "Exit");
  const side = assumptions.find((assumption) => assumption.toLowerCase() === "long-only");
  const allocation = assumptions.find(
    (assumption) => assumption.toLowerCase() === "equal weight",
  );
  const startingCapital =
    parsedStartingCapital ?? result.chart?.base_value ?? undefined;
  const details: EvidenceMetric[] = [
    startingCapital == null
      ? undefined
      : { label: "Starting capital", value: formatCurrency(startingCapital) },
    { label: "Date range", value: result.period },
    timeframe ? { label: "Timeframe", value: timeframe } : undefined,
    side ? { label: "Side", value: side } : undefined,
    allocation ? { label: "Allocation", value: allocation } : undefined,
    benchmark ? { label: "Benchmark", value: benchmark } : undefined,
    contribution?.cadence ? { label: "Cadence", value: contribution.cadence } : undefined,
    contribution?.amount ? { label: "Contribution", value: contribution.amount } : undefined,
    entryRule ? { label: "Entry rule", value: entryRule } : undefined,
    exitRule ? { label: "Exit rule", value: exitRule } : undefined,
  ].filter((detail): detail is EvidenceMetric => Boolean(detail));

  return {
    timeframeDisplay: formatTimeframeForDisplay(timeframe),
    details,
  };
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

function contributionFromAssumptions(assumptions: string[]) {
  const contribution = assumptions.find((assumption) =>
    /\bcontribution\b/i.test(assumption),
  );
  if (!contribution) return undefined;

  const [rawCadence, rawAmount] = contribution.split(":");
  const cadence = rawCadence?.replace(/\s+contribution$/i, "").trim();
  return {
    cadence: cadence || undefined,
    amount: rawAmount?.trim() || undefined,
  };
}

function contributionFromStructuredFacts(
  resolvedParameters?: Record<string, unknown>,
  parameters?: Record<string, unknown>,
) {
  const rawCadence =
    stringValue(resolvedParameters?.cadence) ?? stringValue(parameters?.dca_cadence);
  if (!rawCadence) return undefined;

  const cadence = sentenceCase(rawCadence.replace(/_/g, " "));
  const amount = numberValue(resolvedParameters?.capital_amount);
  return {
    cadence,
    amount: amount == null ? undefined : formatCurrency(amount),
  };
}

function numberValue(value: unknown) {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

export function formatTimeframeForDisplay(timeframe?: string) {
  const value = timeframe?.trim();
  if (!value) return undefined;

  const normalized = value.toLowerCase().replace(/\s+/g, "");
  if (normalized === "daily" || normalized === "1d" || normalized === "1day") {
    return "Daily data";
  }
  if (normalized === "hourly" || normalized === "1h" || normalized === "1hour") {
    return "Hourly data";
  }

  const compactMatch = normalized.match(/^(\d+)(m|minute|minutes|h|hour|hours|d|day|days|w|week|weeks)$/);
  if (compactMatch) {
    const amount = Number(compactMatch[1]);
    const unit = compactMatch[2][0];
    return `${amount}-${timeframeUnitLabel(unit)} data`;
  }

  return `${value} data`;
}

function timeframeUnitLabel(unit: string) {
  if (unit === "m") return "minute";
  if (unit === "h") return "hour";
  if (unit === "d") return "day";
  if (unit === "w") return "week";
  return "period";
}

function sentenceCase(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return trimmed;
  return `${trimmed[0].toUpperCase()}${trimmed.slice(1).toLowerCase()}`;
}

function benchmarkFromMetric(result: StrategyResultPayload) {
  const metric = findMetricByPrefix(result, "Compared with");
  const match = metric?.label.match(/^Compared with\s+(.+)$/i);
  return match?.[1]?.trim();
}

function parseEndingValue(value?: string) {
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
    endingDisplay: formatCurrency(ending),
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

function heroDetail(change?: number, totalReturn?: string) {
  const returnLabel = totalReturn ?? "return unavailable";
  if (change == null) return returnLabel;
  if (Math.abs(change) < 0.5) {
    return `$0 change · ${returnLabel} total return`;
  }
  const sign = change > 0 ? "+" : "-";
  const noun = change > 0 ? "gain" : "loss";
  return `${sign}${formatCurrency(Math.abs(change))} ${noun} · ${returnLabel} total return`;
}

function evidenceTone(change?: number, totalReturn?: string): EvidenceTone {
  const numericReturn =
    totalReturn == null ? undefined : Number(totalReturn.replace("%", ""));
  const basis = numericReturn ?? change;
  if (basis == null || Math.abs(basis) <= 0.5) return "neutral";
  return basis > 0 ? "positive" : "negative";
}

function benchmarkDisplayValue(metric?: EvidenceMetric) {
  const value = metric?.value.trim();
  if (!value) return "Benchmark unavailable";
  const benchmarkValue = value.match(
    /^([+-]?\d+(?:\.\d+)?)\s+(?:percentage points|pts)\s+vs\s+([A-Z0-9.-]+)$/i,
  );
  if (benchmarkValue) {
    const numericValue = Number(benchmarkValue[1]);
    const benchmarkSymbol = benchmarkValue[2];
    if (Math.abs(numericValue) < 0.05) return `In line with ${benchmarkSymbol}`;
    const direction = numericValue > 0 ? "Beat" : "Lagged";
    return `${direction} by ${Math.abs(numericValue).toFixed(1)} percentage points`;
  }
  return value
    .replace(/^Beat\s+[A-Z0-9.-]+\s+by\s+/i, "Beat by ")
    .replace(/^Lagged\s+[A-Z0-9.-]+\s+by\s+/i, "Lagged by ")
    .replace(/^In line with\s+([A-Z0-9.-]+)$/i, "In line with $1")
    .replace(/\bpts\b/gi, "percentage points");
}

function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}
