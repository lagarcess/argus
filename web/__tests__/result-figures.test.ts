import { describe, expect, test } from "bun:test";
import { createInstance } from "i18next";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";
import { nextExperimentReasonText } from "../lib/chat-next-experiments";
import { resultCardPlaygroundFixtures } from "../lib/result-card-playground-fixtures";
import { resultCardViewModel } from "../lib/result-card-view-model";
import { benchmarkClaim, figureText, signedPercentText } from "../lib/result-figures";
import { resultBreakdownText, resultQuickTakeText } from "../lib/result-readout-display";
import { resultReadoutFacts } from "../lib/result-readout-facts";
import { formatRunDossierMetrics } from "../lib/run-dossier-items";
import type { RunDossier } from "../lib/run-dossier-contract";

const LANGUAGES = ["en", "es-419"] as const;

async function translator(language: string) {
  const i18n = createInstance();
  await i18n.init({ lng: language, resources: { en: { translation: en }, "es-419": { translation: es } }, interpolation: { escapeValue: false } });
  return i18n.t;
}

/** A reader payload as the backend ships it: two-decimal metrics beside the
 * one-decimal figures the reader boundary rounded from them. */
function bank(figures: Record<string, unknown>) {
  return {
    symbols: ["AAPL"], benchmark_symbol: "SPY", asset_class: "equity",
    config_snapshot: { template: "buy_and_hold", start_date: "2023-01-03", end_date: "2024-12-31" },
    metrics: { aggregate: {
      performance: { total_return_pct: 53.44, benchmark_return_pct: 7.1, delta_vs_benchmark_pct: 46.35 },
      risk: { max_drawdown_pct: -18.35 },
    } },
    figures,
  };
}

const ISSUE_FIGURES = {
  total_return_pct: 53.4, benchmark_return_pct: 7.1, delta_vs_benchmark_pct: 46.4,
  benchmark_comparison_claim: "beat_benchmark", max_drawdown_pct: -18.4,
};

describe("result figures are rounded once, by the backend (#533)", () => {
  test("the client prints a figure's digits and only adds locale separators", () => {
    expect(figureText(46.4, "en")).toBe("46.4");
    expect(figureText(46.4, "es-419")).toBe("46.4");
    expect(figureText(1234.6, "en")).toBe("1,234.6");
    expect(figureText(1234.6, "es")).toBe("1234,6");
    expect(signedPercentText(53.4, "en")).toBe("+53.4%");
    expect(signedPercentText(-18.4, "es-419")).toBe("-18.4%");
    expect(benchmarkClaim("lagged_benchmark")).toBe("lagged");
    expect(benchmarkClaim("unknown")).toBeUndefined();
  });

  test("engine metrics without backend figures are not printable, so the client never rounds them", async () => {
    const t = await translator("en");
    const facts = resultReadoutFacts(bank({}))!;
    expect(facts.totalReturnPct).toBeUndefined();
    expect(facts.benchmarkDeltaPct).toBeUndefined();
    expect(facts.maxDrawdownPct).toBeUndefined();
    const view = resultCardViewModel({ ...resultCardPlaygroundFixtures[0].result, readoutFacts: facts }, { t, locale: "en" });
    expect(view.evidence.benchmark.value).toBe(t("chat.result_card.benchmark_unavailable"));
    expect(JSON.stringify(view)).not.toContain("46.3");
    expect(JSON.stringify(view)).not.toContain("53.44");
  });

  test.each(LANGUAGES)("the card, the Quick Take, the breakdown, and the Try next reason quote the backend gap in %s", async (language) => {
    const t = await translator(language);
    for (const [delta, claim] of [[46.4, "beat_benchmark"], [315.6, "beat_benchmark"], [9.4, "lagged_benchmark"], [1234.6, "beat_benchmark"]] as const) {
      const signed = claim === "lagged_benchmark" ? -delta : delta;
      const facts = resultReadoutFacts(bank({ ...ISSUE_FIGURES, delta_vs_benchmark_pct: signed, benchmark_comparison_claim: claim }))!;
      const view = resultCardViewModel({ ...resultCardPlaygroundFixtures[0].result, symbols: ["AAPL"], readoutFacts: facts }, { t, locale: language });
      const magnitude = figureText(delta, language);
      const beat = claim === "beat_benchmark";
      expect(view.evidence.benchmark.value).toBe(t(beat ? "chat.result_card.beat_by" : "chat.result_card.lagged_by", {
        value: t("chat.result_card.percentage_points", { value: magnitude }),
      }));
      expect(view.readout).toContain(t(beat ? "chat.result_readout.beat" : "chat.result_readout.lagged", { symbol: "SPY", value: magnitude }));
      expect(resultBreakdownText(facts, t, language)).toContain(magnitude);
      const reason = nextExperimentReasonText({ code: beat ? "beat_benchmark" : "lost_to_benchmark", params: { points: delta } }, t, language);
      expect(reason).toBe(t(beat ? "chat.next_experiments.why.beat_benchmark" : "chat.next_experiments.why.lost_to_benchmark", { points: magnitude }));
    }
  });

  test.each(LANGUAGES)("returns and the worst drop read the same everywhere in %s", async (language) => {
    const t = await translator(language);
    const facts = resultReadoutFacts(bank(ISSUE_FIGURES))!;
    const view = resultCardViewModel({ ...resultCardPlaygroundFixtures[0].result, readoutFacts: facts }, { t, locale: language });
    expect(view.evidence.hero.detail).toContain("+53.4%");
    expect(view.evidence.worstDrop.value).toBe("-18.4%");
    expect(view.readout).toContain(t("chat.result_readout.total_return", { value: "+53.4%" }));
    expect(view.readout).toContain(t("chat.result_readout.drawdown", { value: "-18.4%" }));
    expect(resultBreakdownText(facts, t, language)).toContain(t("chat.result_readout.benchmark_return", { symbol: "SPY", value: "+7.1%" }));
    for (const raw of ["53.44", "46.35", "18.35"]) expect(JSON.stringify(view)).not.toContain(raw);
  });

  test.each(LANGUAGES)("the backend's in-line claim is in line on every surface in %s", async (language) => {
    const t = await translator(language);
    const facts = resultReadoutFacts(bank({ ...ISSUE_FIGURES, delta_vs_benchmark_pct: 0, benchmark_comparison_claim: "matched_benchmark" }))!;
    const view = resultCardViewModel({ ...resultCardPlaygroundFixtures[0].result, readoutFacts: facts }, { t, locale: language });
    expect(view.evidence.benchmark.value).toBe(t("chat.result_card.in_line_with", { symbol: "SPY" }));
    expect(view.readout).toContain(t("chat.result_readout.matched", { symbol: "SPY" }));
  });

  test("the dossier grid prints the same backend figure as the Quick Take beside it", async () => {
    const t = await translator("en");
    const dossier = {
      outcome: { metrics: [{ name: "delta_vs_benchmark_pct", value: 46.2 }, { name: "max_drawdown_pct", value: -18.4 }, { name: "win_rate", value: 0.57 }] },
    } as unknown as RunDossier;
    expect(formatRunDossierMetrics(dossier, t, "en")).toEqual([
      { name: "Against benchmark", value: "+46.2%" },
      { name: "Worst drop", value: "-18.4%" },
      { name: "Win rate", value: "57.0%" },
    ]);
    const facts = resultReadoutFacts(bank({ ...ISSUE_FIGURES, delta_vs_benchmark_pct: 46.2 }))!;
    expect(resultQuickTakeText(facts, t, "en")).toContain("46.2 percentage points");
  });

  test("the Try next reason prints the backend drop the way the card does", async () => {
    const t = await translator("en");
    expect(nextExperimentReasonText({ code: "deep_drawdown", params: { drawdown: -22.4 } }, t, "en")).toBe("Worst drop was -22.4%");
    expect(nextExperimentReasonText({ code: "beat_benchmark", params: { points: 4.2 } }, t, "en")).toBe("Beat the benchmark by 4.2 points");
    expect(nextExperimentReasonText(null, t, "en")).toBe("");
  });
});
