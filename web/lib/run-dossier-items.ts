import type { TFunction } from "i18next";

import type { RunDossier } from "./run-dossier-contract";

const MAX_DOSSIER_SYMBOLS = 5;
const MAX_DOSSIER_METRICS = 4;

const METRIC_FALLBACKS: Record<string, string> = {
  benchmark_return_pct: "Benchmark return",
  delta_vs_benchmark_pct: "Against benchmark",
  excess_return_pct: "Against benchmark",
  max_drawdown_pct: "Worst drop",
  sharpe_ratio: "Sharpe",
  sortino_ratio: "Sortino",
  total_return_pct: "Total return",
  volatility_pct: "Volatility",
  win_rate: "Win rate",
};

function fallbackCodeLabel(value: string): string {
  const normalized = value.replaceAll("_", " ").trim();
  if (!normalized) return "";
  return normalized.charAt(0).toUpperCase() + normalized.slice(1);
}

function localizedDate(value: string, locale: string): string | null {
  const date = new Date(`${value}T00:00:00.000Z`);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function localizedNumber(
  value: number,
  locale: string,
  maximumFractionDigits: number,
): string {
  return new Intl.NumberFormat(locale, {
    maximumFractionDigits,
    minimumFractionDigits: 0,
  }).format(value);
}

function localizedPercent(value: number, locale: string): string {
  return new Intl.NumberFormat(locale, {
    style: "percent",
    maximumFractionDigits: 1,
    minimumFractionDigits: 0,
  })
    .format(value / 100)
    .replaceAll("\u00a0", " ");
}

export function formatRunDossierSetup(
  dossier: RunDossier,
  t: TFunction,
  locale: string,
): string[] {
  const parts: string[] = [];
  const symbols = dossier.tested.symbols
    .slice(0, MAX_DOSSIER_SYMBOLS)
    .filter(Boolean);
  if (symbols.length > 0) parts.push(symbols.join(", "));

  const family = dossier.tested.strategy_family;
  if (family) {
    const fallback = fallbackCodeLabel(family);
    const label =
      t(
        `command_palette.dossier_values.strategy_families.${family}`,
        fallback,
      ) || fallback;
    if (label) parts.push(label);
  }

  const cadence = dossier.tested.cadence;
  const timeframe = dossier.tested.timeframe;
  const cadenceAndTimeframe = [
    cadence
      ? t(
          `command_palette.dossier_values.cadences.${cadence}`,
          fallbackCodeLabel(cadence),
        )
      : null,
    timeframe,
  ].filter((value): value is string => Boolean(value));
  if (cadenceAndTimeframe.length > 0) {
    parts.push(cadenceAndTimeframe.join(" · "));
  }

  const start = dossier.tested.start_date
    ? localizedDate(dossier.tested.start_date, locale)
    : null;
  const end = dossier.tested.end_date
    ? localizedDate(dossier.tested.end_date, locale)
    : null;
  if (start && end) {
    parts.push(`${start} – ${end}`);
  } else if (start || end) {
    parts.push(start ?? end ?? "");
  }

  return parts;
}

export function formatRunDossierMetrics(
  dossier: RunDossier,
  t: TFunction,
  locale: string,
): Array<{ name: string; value: string }> {
  return dossier.outcome.metrics
    .slice(0, MAX_DOSSIER_METRICS)
    .map((metric) => {
      const name = t(
        `command_palette.metric_labels.${metric.name}`,
        METRIC_FALLBACKS[metric.name] ?? fallbackCodeLabel(metric.name),
      );
      if (typeof metric.value === "string") {
        return { name, value: metric.value };
      }
      if (metric.name.endsWith("_pct")) {
        return { name, value: localizedPercent(metric.value, locale) };
      }
      if (metric.name === "win_rate") {
        return { name, value: localizedPercent(metric.value * 100, locale) };
      }
      return {
        name,
        value: localizedNumber(metric.value, locale, 2),
      };
    });
}
