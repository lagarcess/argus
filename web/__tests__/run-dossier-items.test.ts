import { describe, expect, test } from "bun:test";
import type { TFunction } from "i18next";

import type { RunDossier } from "../lib/run-dossier-contract";
import { withDossierResultFacts } from "../test-fixtures/dossier-result-facts";
import {
  formatRunDossierMetrics,
  formatRunDossierSetup,
} from "../lib/run-dossier-items";

const translations: Record<string, string> = {
  "command_palette.dossier_values.strategy_families.buy_and_hold":
    "Buy and hold",
  "command_palette.dossier_values.cadences.weekly": "Weekly",
  "command_palette.metric_labels.total_return_pct": "Total return",
  "command_palette.metric_labels.max_drawdown_pct": "Worst drop",
  "command_palette.metric_labels.sharpe_ratio": "Sharpe",
};

const t = ((key: string, fallback?: string) =>
  translations[key] ?? fallback ?? key) as TFunction;

const dossier: RunDossier = withDossierResultFacts({
  run_id: "run-7",
  run_label: "Weekly GLD pullback",
  completed_at: "2026-07-31T14:30:00.000Z",
  result_message_id: "message-7",
  tested: {
    symbols: ["GLD"],
    strategy_family: "buy_and_hold",
    cadence: "weekly",
    timeframe: "1D",
    start_date: "2025-01-01",
    end_date: "2025-12-31",
  },
  outcome: {
    run_label: "Weekly GLD pullback",
    completed_at: "2026-07-31T14:30:00.000Z",
    benchmark_symbol: "SPY",
    metrics: [
      { name: "total_return_pct", value: 8.4 },
      { name: "max_drawdown_pct", value: -6.2 },
      { name: "sharpe_ratio", value: 1.234 },
    ],
  },
  decision: {
    state: "watching",
    note: "Hold through earnings.\nReview risk first.",
    run_label: "Weekly GLD pullback",
  },
  actions: [],
});

describe("single-run dossier formatting", () => {
  test("formats only the bounded setup facts supplied by the backend", () => {
    expect(formatRunDossierSetup(dossier, t, "en-US")).toEqual([
      "GLD",
      "Buy and hold",
      "Weekly · 1D",
      "Jan 1, 2025 – Dec 31, 2025",
    ]);

    expect(
      formatRunDossierSetup(
        {
          ...dossier,
          tested: {
            symbols: [],
            strategy_family: null,
            cadence: null,
            timeframe: null,
            start_date: null,
            end_date: null,
          },
        },
        t,
        "en-US",
      ),
    ).toEqual([]);
  });

  test("formats bounded metric values with locale-aware numbers", () => {
    expect(formatRunDossierMetrics(dossier, t, "en-US")).toEqual([
      { name: "Total return", value: "8.4%" },
      { name: "Worst drop", value: "-6.2%" },
      { name: "Sharpe", value: "1.23" },
    ]);

    expect(formatRunDossierMetrics(dossier, t, "es-419")).toEqual([
      { name: "Total return", value: "8.4%" },
      { name: "Worst drop", value: "-6.2%" },
      { name: "Sharpe", value: "1.23" },
    ]);
  });
});
