import { describe, expect, test } from "bun:test";
import { createInstance } from "i18next";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";
import parity from "../test-fixtures/tenth-figure-parity.json";
import { nextExperimentReasonText } from "../lib/chat-next-experiments";
import { resultCardPlaygroundFixtures } from "../lib/result-card-playground-fixtures";
import { benchmarkComparisonView, signedPercentFigure, tenthFigure } from "../lib/result-figures";
import { resultBreakdownText, resultQuickTakeText } from "../lib/result-readout-display";
import { resultReadoutFacts } from "../lib/result-readout-facts";
import { resultCardViewModel } from "../lib/result-card-view-model";

const LANGUAGES = ["en", "es-419"] as const;

async function translator(language: string) {
  const i18n = createInstance();
  await i18n.init({ lng: language, resources: { en: { translation: en }, "es-419": { translation: es } }, interpolation: { escapeValue: false } });
  return i18n.t;
}

/** An engine-shaped fact bank: two-decimal returns beside the engine's own gap. */
function bank(delta: number, totalReturn = 53.44, benchmarkReturn = 7.1, maxDrawdown = -18.35) {
  return {
    symbols: ["AAPL"], benchmark_symbol: "SPY", asset_class: "equity",
    config_snapshot: { template: "buy_and_hold", start_date: "2023-01-03", end_date: "2024-12-31" },
    metrics: { aggregate: {
      performance: { total_return_pct: totalReturn, benchmark_return_pct: benchmarkReturn, delta_vs_benchmark_pct: delta },
      risk: { max_drawdown_pct: maxDrawdown },
    } },
  };
}

describe("one figure formatter for the result surfaces (#533)", () => {
  test("prints exactly what the backend's fixed-point formatting prints", () => {
    for (const row of parity.rows) {
      expect(tenthFigure(row.value)).toBe(row.text);
    }
  });

  test("Intl and toFixed are not that formatter, which is why one owner exists", () => {
    // 46.15 sits below the decimal tie in binary, 46.25 is an exact tie.
    expect(new Intl.NumberFormat("en", { maximumFractionDigits: 1 }).format(46.15)).toBe("46.2");
    expect((46.25).toFixed(1)).toBe("46.3");
    expect(tenthFigure(46.15)).toBe("46.1");
    expect(tenthFigure(46.25)).toBe("46.2");
  });

  test("the in-line claim is exactly the magnitude rounding to nothing", () => {
    expect(benchmarkComparisonView(0.049)).toEqual({ claim: "matched", magnitude: "0.0" });
    expect(benchmarkComparisonView(-0.049)).toEqual({ claim: "matched", magnitude: "0.0" });
    expect(benchmarkComparisonView(0.05)).toEqual({ claim: "beat", magnitude: "0.1" });
    expect(benchmarkComparisonView(-0.05)).toEqual({ claim: "lagged", magnitude: "0.1" });
    expect(signedPercentFigure(53.44)).toBe("+53.4%");
    expect(signedPercentFigure(-18.35)).toBe("-18.4%");
  });

  test.each(LANGUAGES)("the card, the Quick Take, the breakdown, and the Try next reason quote one gap in %s", async (language) => {
    const t = await translator(language);
    for (const delta of [46.35, 46.34, 315.64, 46.25, -9.44, -0.75, 100.25]) {
      const facts = resultReadoutFacts(bank(delta))!;
      const result = { ...resultCardPlaygroundFixtures[0].result, symbols: ["AAPL"], readoutFacts: facts };
      const view = resultCardViewModel(result, { t, locale: language });
      const { magnitude, claim } = benchmarkComparisonView(delta);
      expect(claim).toBe(delta > 0 ? "beat" : "lagged");
      const cardText = view.evidence.benchmark.value;
      expect(cardText).toBe(t(delta > 0 ? "chat.result_card.beat_by" : "chat.result_card.lagged_by", {
        value: t("chat.result_card.percentage_points", { value: magnitude }),
      }));
      const quickTake = resultQuickTakeText(facts, t, language);
      expect(quickTake).toContain(t(delta > 0 ? "chat.result_readout.beat" : "chat.result_readout.lagged", { symbol: "SPY", value: magnitude }));
      expect(resultBreakdownText(facts, t, language)).toContain(magnitude);
      const reason = nextExperimentReasonText({ code: delta > 0 ? "beat_benchmark" : "lost_to_benchmark", params: { points: Math.abs(delta) } }, t);
      expect(reason).toBe(t(delta > 0 ? "chat.next_experiments.why.beat_benchmark" : "chat.next_experiments.why.lost_to_benchmark", { points: magnitude }));
      // No surface may print the two-decimal engine value or a subtraction of
      // the rounded returns (53.44 - 7.1 = 46.34 for the issue's own case).
      for (const text of [cardText, quickTake, reason]) {
        expect(text).not.toContain(String(delta));
        if (delta === 46.35) expect(text).not.toContain("46.3");
      }
    }
  });

  test.each(LANGUAGES)("returns and the worst drop read the same in the card and the Quick Take in %s", async (language) => {
    const t = await translator(language);
    const facts = resultReadoutFacts(bank(46.35))!;
    const view = resultCardViewModel({ ...resultCardPlaygroundFixtures[0].result, readoutFacts: facts }, { t, locale: language });
    expect(view.evidence.hero.detail).toContain("+53.4%");
    expect(view.evidence.worstDrop.value).toBe("-18.4%");
    expect(view.readout).toContain(t("chat.result_readout.total_return", { value: "+53.4%" }));
    expect(view.readout).toContain(t("chat.result_readout.drawdown", { value: "-18.4%" }));
    expect(view.readout).not.toContain("53.44");
    expect(view.readout).not.toContain("18.35");
    expect(resultBreakdownText(facts, t, language)).toContain(t("chat.result_readout.benchmark_return", { symbol: "SPY", value: "+7.1%" }));
  });

  test.each(LANGUAGES)("a gap that rounds to nothing is in line on every surface in %s", async (language) => {
    const t = await translator(language);
    const facts = resultReadoutFacts(bank(0.03))!;
    const view = resultCardViewModel({ ...resultCardPlaygroundFixtures[0].result, readoutFacts: facts }, { t, locale: language });
    expect(view.evidence.benchmark.value).toBe(t("chat.result_card.in_line_with", { symbol: "SPY" }));
    expect(view.readout).toContain(t("chat.result_readout.matched", { symbol: "SPY" }));
    expect(view.readout).not.toContain("0.03");
  });

  test("the Try next reason prints the engine drop the way the card does", async () => {
    const t = await translator("en");
    expect(nextExperimentReasonText({ code: "deep_drawdown", params: { drawdown: -22.35 } }, t)).toBe("Worst drop was -22.4%");
    expect(nextExperimentReasonText({ code: "beat_benchmark", params: { points: 4.2 } }, t)).toBe("Beat the benchmark by 4.2 points");
    expect(nextExperimentReasonText(null, t)).toBe("");
  });
});
