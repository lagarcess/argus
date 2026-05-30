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
