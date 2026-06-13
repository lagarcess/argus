import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  legacyPersistedRunFixture,
  resultCardPlaygroundFixtures,
} from "../lib/result-card-playground-fixtures";
import { resultCardFromConversationCard } from "../lib/argus-api";
import {
  compactTrustGroups,
  compactTrustStrip,
  defaultResultCardDisplayCopy,
  formatTimeframeForDisplay,
  heroDeltaEvidenceView,
} from "../lib/result-card-playground-display";
import type { ChatActionOption } from "../components/chat/types";

const root = join(import.meta.dir, "..");

describe("result card playground", () => {
  test("keeps the playground route dev-only and outside product navigation", () => {
    const page = readFileSync(join(root, "app/dev/result-card/page.tsx"), "utf-8");
    const proxy = readFileSync(join(root, "proxy.ts"), "utf-8");
    const sidebar = readFileSync(join(root, "components/sidebar/ChatSidebar.tsx"), "utf-8");
    const landing = readFileSync(join(root, "app/page.tsx"), "utf-8");

    expect(page).toContain('process.env.NODE_ENV === "production"');
    expect(page).toContain('export const dynamic = "force-dynamic"');
    expect(page).toContain("notFound()");
    expect(proxy).toContain('"/dev/result-card/:path*"');
    expect(proxy).toContain('process.env.NODE_ENV === "production"');
    expect(proxy).toContain("status: 404");
    expect(sidebar).not.toContain("/dev/result-card");
    expect(landing).not.toContain("/dev/result-card");
  });

  test("covers the required static card states without persistence or network code", () => {
    expect(resultCardPlaygroundFixtures.map((fixture) => fixture.id)).toEqual([
      "positive-single-symbol",
      "negative-single-symbol",
      "benchmark-underperformance-positive",
      "dca-result",
      "trade-based-strategy",
      "multi-symbol-same-asset",
      "old-persisted-card-shape",
    ]);

    for (const fixture of resultCardPlaygroundFixtures) {
      expect(fixture.result.strategyName.length).toBeGreaterThan(0);
      expect(fixture.result.metrics.length).toBeGreaterThanOrEqual(4);
      expect(fixture.result.actions?.some((action) => action.type === "show_breakdown")).toBe(true);
      expect(fixture.result.actions?.some((action) => action.type === "refine_strategy")).toBe(true);
    }

    const client = readFileSync(
      join(root, "app/dev/result-card/ResultCardPlaygroundClient.tsx"),
      "utf-8",
    );
    const productionCard = readFileSync(
      join(root, "components/chat/StrategyResultCard.tsx"),
      "utf-8",
    );
    expect(client).toContain("document.documentElement");
    expect(client).toContain('root.classList.remove("dark")');
    expect(client).toContain('root.classList.add("dark")');
    expect(client).toContain('className: "dark bg-[#141517] text-white"');
    expect(client).toContain("<StrategyResultCard");
    expect(client).not.toContain("<HeroDeltaEvidenceCard");
    expect(productionCard).toContain("Hero + Delta Evidence Card");
    expect(productionCard).toContain('presentation="heroDeltaEvidence"');
    expect(productionCard).toContain("view.timeframeDisplay");
    expect(productionCard).toContain("ExecutionDetails");
    expect(productionCard).toContain("StatRail");
    expect(productionCard).toContain("TrustRail");
    expect(productionCard).toContain("strategiesEnabled");
    expect(productionCard).not.toContain("function MetricBlock");
    expect(productionCard).not.toContain('bg-[#f4f4f4] px-4 py-4');
    expect(productionCard).not.toContain("shadow");
    expect(client).not.toContain("fetch(");
    expect(client).not.toContain("loginWithEmail");
    expect(client).not.toContain("signupWithEmail");
    expect(client).not.toContain("saveStrategy");
  });

  test("uses the existing hydration mapper for the old persisted card shape", () => {
    const legacyRows = legacyPersistedRunFixture.conversation_result_card.rows;
    expect(legacyRows.map((row) => row.label)).toEqual([
      "Cash Value ($)",
      "Total Return (%)",
      "Vs benchmark",
      "Max Drawdown",
    ]);

    const legacyFixture = resultCardPlaygroundFixtures.find(
      (fixture) => fixture.id === "old-persisted-card-shape",
    );
    expect(legacyFixture?.result.metrics).toEqual([
      { label: "Ending value", value: "$1,000 -> $2,002" },
      { label: "Total return", value: "+100.2%" },
      { label: "Compared with SPY", value: "Beat SPY by 46.4 percentage points" },
      { label: "Worst drop", value: "-16.8%" },
    ]);
  });

  test("builds hero delta evidence from mapped fixture rows without new runtime fields", () => {
    const positive = heroDeltaEvidenceView(resultCardPlaygroundFixtures[0].result);
    expect(positive.hero.value).toBe("$1,560");
    expect(positive.hero.detail).toBe("+$560 gain · +56.0% total return");
    expect(positive.hero.tone).toBe("positive");
    expect(positive.benchmark.label).toBe("Compared with SPY");
    expect(positive.benchmark.value).toBe("Beat by 27.9 percentage points");
    expect(positive.timeframeDisplay).toBe("Daily data");
    expect(positive.worstDrop.value).toBe("-12.4%");
    expect(positive.details).toContainEqual({ label: "Timeframe", value: "1D" });
    expect(positive.details).toContainEqual({ label: "Benchmark", value: "SPY" });

    const negative = heroDeltaEvidenceView(resultCardPlaygroundFixtures[1].result);
    expect(negative.hero.value).toBe("$820");
    expect(negative.hero.detail).toBe("-$180 loss · -18.0% total return");
    expect(negative.hero.tone).toBe("negative");
    expect(negative.benchmark.value).toBe("Lagged by 9.4 percentage points");

    const dca = heroDeltaEvidenceView(
      resultCardPlaygroundFixtures.find((fixture) => fixture.id === "dca-result")!.result,
    );
    expect(dca.hero.value).toBe("$1,000");
    expect(dca.hero.detail).toBe("$0 change · 0.0% total return");
    expect(dca.hero.tone).toBe("neutral");
    expect(dca.benchmark.value).toBe("In line with SPY");
    expect(dca.timeframeDisplay).toBe("Daily data");
    expect(dca.details).toContainEqual({ label: "Total contributed", value: "$1,000" });
    expect(dca.details).not.toContainEqual({ label: "Starting capital", value: "$1,000" });
    expect(dca.details).toContainEqual({ label: "Cadence", value: "Monthly" });
    expect(dca.details).toContainEqual({ label: "Contribution", value: "$250" });

    const compactProductionShape = heroDeltaEvidenceView({
      ...resultCardPlaygroundFixtures[0].result,
      metrics: [
        { label: "Ending value", value: "$1K -> $1.37K" },
        { label: "Total return", value: "+37.1%" },
        { label: "Compared with SPY", value: "+8.4 percentage points vs SPY" },
        { label: "Worst drop", value: "-18.9%" },
      ],
    });
    expect(compactProductionShape.hero.value).toBe("$1,370");
    expect(compactProductionShape.hero.detail).toBe(
      "+$370 gain · +37.1% total return",
    );
    expect(compactProductionShape.benchmark.value).toBe(
      "Beat by 8.4 percentage points",
    );
  });

  test("does not infer recurring contribution mode from display prose", () => {
    const proseOnlyRecurring = heroDeltaEvidenceView({
      ...resultCardPlaygroundFixtures[0].result,
      strategyName: "Recurring buys display text",
      assumptions: [
        "Long-only",
        "Equal weight",
        "Monthly contribution: $250",
        "Benchmark: SPY",
      ],
      configSnapshot: {
        template: "buy_and_hold",
        benchmark_symbol: "SPY",
        resolved_parameters: {
          timeframe: "1D",
          benchmark_symbol: "SPY",
        },
      },
    });

    expect(proseOnlyRecurring.details).toContainEqual({
      label: "Starting capital",
      value: "$1,000",
    });
    expect(proseOnlyRecurring.details).not.toContainEqual({
      label: "Total contributed",
      value: "$1,000",
    });
    expect(proseOnlyRecurring.details.some((detail) => detail.label === "Contribution")).toBe(
      false,
    );
  });

  test("uses structured run timeframe facts before assumption text", () => {
    const structured = heroDeltaEvidenceView({
      ...resultCardPlaygroundFixtures[0].result,
      assumptions: ["Long-only", "Equal weight", "No fees/slippage", "Benchmark: SPY"],
      configSnapshot: {
        timeframe: "4h",
        benchmark_symbol: "SPY",
        resolved_parameters: {
          timeframe: "1D",
        },
      },
    });

    expect(structured.timeframeDisplay).toBe("4-hour data");
    expect(structured.details).toContainEqual({ label: "Timeframe", value: "4h" });
    expect(formatTimeframeForDisplay("1h")).toBe("Hourly data");
    expect(formatTimeframeForDisplay("2h")).toBe("2-hour data");
    expect(formatTimeframeForDisplay("12h")).toBe("12-hour data");
    expect(formatTimeframeForDisplay("15m")).toBe("15-minute data");
  });

  test("uses structured benchmark facts before stale assumption text", () => {
    const structured = heroDeltaEvidenceView({
      ...resultCardPlaygroundFixtures[0].result,
      metrics: [
        { label: "Ending value", value: "$1,000 -> $1,350" },
        { label: "Total return", value: "+35.0%" },
        { label: "Compared with QQQ", value: "+8.1 percentage points vs QQQ" },
        { label: "Worst drop", value: "-15.5%" },
      ],
      assumptions: ["Long-only", "Equal weight", "No fees/slippage", "Benchmark: SPY"],
      configSnapshot: {
        timeframe: "1D",
        benchmark_symbol: "QQQ",
        resolved_parameters: {
          timeframe: "1D",
          benchmark_symbol: "QQQ",
        },
      },
    });

    expect(structured.benchmark.label).toBe("Compared with QQQ");
    expect(structured.benchmark.value).toBe("Beat by 8.1 percentage points");
    expect(structured.details).toContainEqual({ label: "Benchmark", value: "QQQ" });
    expect(structured.details).not.toContainEqual({ label: "Benchmark", value: "SPY" });
  });

  test("prefers resolved explicit benchmark over stale top-level default", () => {
    const structured = heroDeltaEvidenceView({
      ...resultCardPlaygroundFixtures[0].result,
      metrics: [
        { label: "Ending value", value: "$1,000 -> $1,350" },
        { label: "Total return", value: "+35.0%" },
        { label: "Compared with QQQ", value: "+8.1 percentage points vs QQQ" },
        { label: "Worst drop", value: "-15.5%" },
      ],
      assumptions: ["Long-only", "Equal weight", "No fees/slippage", "Benchmark: SPY"],
      configSnapshot: {
        timeframe: "1D",
        benchmark_symbol: "SPY",
        resolved_parameters: {
          timeframe: "1D",
          benchmark_symbol: "QQQ",
        },
      },
    });

    expect(structured.benchmark.label).toBe("Compared with QQQ");
    expect(structured.details).toContainEqual({ label: "Benchmark", value: "QQQ" });
    expect(structured.details).not.toContainEqual({ label: "Benchmark", value: "SPY" });
  });

  test("uses structured benchmark facts before stale persisted metric labels", () => {
    const mapped = resultCardFromConversationCard(
      {
        ...legacyPersistedRunFixture.conversation_result_card,
        rows: [
          { key: "cash_value", label: "Cash Value ($)", value: "$1,000 -> $1,350" },
          { key: "total_return_pct", label: "Total Return (%)", value: "+35.0%" },
          {
            key: "benchmark_delta",
            label: "Compared with SPY",
            value: "Beat by 8.1 percentage points",
          },
          { key: "max_drawdown_pct", label: "Max Drawdown", value: "-15.5%" },
        ],
        assumptions: [
          "Long-only",
          "Equal weight",
          "No fees/slippage",
          "Benchmark: SPY",
        ],
      },
      {
        id: "run-with-qqq",
        strategy_id: null,
        benchmark_symbol: "QQQ",
        config_snapshot: {
          timeframe: "1D",
          benchmark_symbol: "QQQ",
          resolved_parameters: {
            benchmark_symbol: "QQQ",
            timeframe: "1D",
          },
        },
      },
    );

    expect(mapped.metrics[2].label).toBe("Compared with QQQ");

    const structured = heroDeltaEvidenceView(mapped);
    expect(structured.benchmark.label).toBe("Compared with QQQ");
    expect(structured.details).toContainEqual({ label: "Benchmark", value: "QQQ" });
    expect(structured.details).not.toContainEqual({ label: "Benchmark", value: "SPY" });
  });

  test("keeps result card display copy configurable while Spanish is disabled", () => {
    const spanish = heroDeltaEvidenceView(resultCardPlaygroundFixtures[0].result, {
      copy: {
        ...defaultResultCardDisplayCopy,
        endingValueLabel: "Valor final",
        comparedWithSymbolLabel: (symbol) => `Comparado con ${symbol}`,
        worstDropLabel: "Peor caída",
        gainNoun: "ganancia",
        totalReturnSuffix: "rendimiento total",
        percentagePoints: (value) => `${value} puntos porcentuales`,
        beatBy: (value) => `Superó por ${value}`,
        startingCapitalLabel: "Capital inicial",
        timeframeLabel: "Temporalidad",
        benchmarkLabel: "Referencia",
        dailyData: "Datos diarios",
      },
      locale: "es-419",
    });

    expect(spanish.hero.label).toBe("Valor final");
    expect(spanish.hero.detail).toContain("ganancia");
    expect(spanish.hero.detail).toContain("rendimiento total");
    expect(spanish.benchmark.label).toBe("Comparado con SPY");
    expect(spanish.benchmark.value).toBe("Superó por 27.9 puntos porcentuales");
    expect(spanish.worstDrop.label).toBe("Peor caída");
    expect(spanish.timeframeDisplay).toBe("Datos diarios");
    expect(spanish.details).toContainEqual({
      label: "Capital inicial",
      value: "$1,000",
    });
  });

  test("builds calm trust and detail groups without duplicate universe prose", () => {
    const legacy = resultCardPlaygroundFixtures.find(
      (fixture) => fixture.id === "old-persisted-card-shape",
    )!.result;
    expect(compactTrustGroups()).toEqual([
      "Historical simulation · No fees/slippage · Not advice",
    ]);
    expect(compactTrustStrip()).not.toContain("Universe:");
    expect(compactTrustStrip()).not.toContain("Benchmark: SPY");
    expect(heroDeltaEvidenceView(legacy).details).toContainEqual({
      label: "Benchmark",
      value: "SPY",
    });
    expect(heroDeltaEvidenceView(legacy).details).toContainEqual({
      label: "Timeframe",
      value: "1D",
    });
  });

  test("exposes trade parameters in lightweight details when fixture facts exist", () => {
    const trade = heroDeltaEvidenceView(
      resultCardPlaygroundFixtures.find((fixture) => fixture.id === "trade-based-strategy")!.result,
    );
    expect(trade.details).toContainEqual({ label: "Entry rule", value: "RSI below 30" });
    expect(trade.details).toContainEqual({ label: "Exit rule", value: "RSI above 55" });
  });

  test("hydrates missing run facts and normalizes action labels correctly via resultCardFromConversationCard", () => {
    const card: Parameters<typeof resultCardFromConversationCard>[0] = {
      title: "Test Strategy",
      symbols: ["AAPL", "MSFT"],
      strategy_label: "Test Label",
      date_range: { start: "2023-01-01", end: "2024-01-01", display: "2023-01-01 to 2024-01-01" },
      status_label: "Completed",
      rows: [{ key: "metric1", label: "Metric 1", value: "100" }],
      benchmark_note: "Test Benchmark Note",
      assumptions: ["Assumption 1", "Assumption 2"],
      actions: [
        { id: "action-1", type: "show_breakdown", presentation: "result" },
        {
          id: "action-2",
          type: "custom_type" as ChatActionOption["type"],
          label: "Custom Action",
          presentation: "result",
        }
      ],
      // chart is omitted intentionally
    };

    // 1. Without run argument
    const mappedWithoutRun = resultCardFromConversationCard(card, undefined);
    expect(mappedWithoutRun.strategyName).toBe("Test Strategy");
    expect(mappedWithoutRun.symbols).toEqual(["AAPL", "MSFT"]);
    expect(mappedWithoutRun.statusLabel).toBe("Completed");
    expect(mappedWithoutRun.assumptions).toEqual(["Assumption 1", "Assumption 2"]);
    expect(mappedWithoutRun.chart).toBeNull();
    expect(mappedWithoutRun.runId).toBeUndefined();
    expect(mappedWithoutRun.strategyId).toBeNull();
    expect(mappedWithoutRun.configSnapshot).toBeUndefined();

    // 2. Actions label normalization
    expect(mappedWithoutRun.actions).toHaveLength(2);
    expect(mappedWithoutRun.actions[0].label).toBe("Explain result");
    expect(mappedWithoutRun.actions[1].label).toBe("Custom Action");

    // 3. With run argument
    const run: Parameters<typeof resultCardFromConversationCard>[1] = {
      id: "run-123",
      strategy_id: "strat-456",
      benchmark_symbol: "SPY",
      config_snapshot: { template: "buy_and_hold" }
    };
    const mappedWithRun = resultCardFromConversationCard(card, run);
    expect(mappedWithRun.runId).toBe("run-123");
    expect(mappedWithRun.strategyId).toBe("strat-456");
    expect(mappedWithRun.configSnapshot).toEqual({ template: "buy_and_hold" });
  });

});
