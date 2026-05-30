import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  legacyPersistedRunFixture,
  resultCardPlaygroundFixtures,
} from "../lib/result-card-playground-fixtures";
import {
  compactTrustGroups,
  compactTrustStrip,
  formatTimeframeForDisplay,
  heroDeltaEvidenceView,
} from "../lib/result-card-playground-display";

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
});
