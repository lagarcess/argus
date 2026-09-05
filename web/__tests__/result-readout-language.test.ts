import { describe, expect, test } from "bun:test";
import { createInstance } from "i18next";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";
import { resultReadoutFacts } from "../lib/result-readout-facts";
import { resultBreakdownText, resultQuickTakeText } from "../lib/result-readout-display";
import { resultCardFromRun } from "../lib/argus-api";
import { resultCardViewModel } from "../lib/result-card-view-model";
import { hydrateMessagesFromApi, messageStreamPresentation } from "../components/chat/chat-message-projection";
import type { BacktestRun } from "../lib/argus-api";

const originalProse = "PRIVATE ENGLISH PROSE MUST NEVER RENDER";
const config = {
  template: "dca_accumulation", timeframe: "1D",
  start_date: "2025-01-02", end_date: "2025-12-31",
  resolved_parameters: { starting_capital: 500, recurring_contribution: 200, cadence: "monthly" },
};
const bank = {
  symbols: ["AAPL"], benchmark_symbol: "SPY", asset_class: "equity",
  config_snapshot: config,
  metrics: { aggregate: {
    performance: { total_return_pct: 12.5, benchmark_return_pct: 8, delta_vs_benchmark_pct: 3.2 },
    risk: { max_drawdown_pct: -7.6 },
  }, by_symbol: {} },
  result_card: { quick_take: originalProse, execution_costs: { fee_bps: 10, slippage_bps: 5 } },
};

async function translator(language: string) {
  const i18n = createInstance();
  await i18n.init({ lng: language, resources: { en: { translation: en }, "es-419": { translation: es } }, interpolation: { escapeValue: false } });
  return i18n.t;
}

describe("persisted result presentation (#531)", () => {
  test.each(["en", "es-419"])("voices the same typed DCA facts in %s", async (language) => {
    const t = await translator(language);
    const facts = resultReadoutFacts(bank);
    const text = resultQuickTakeText(facts, t, language);
    const breakdown = resultBreakdownText(facts, t, language);
    expect(text).toContain("AAPL");
    expect(text).toContain("SPY");
    // The comparison belongs to the engine. Do not recompute 12.5 - 8 here.
    expect(text).toContain("3.2");
    expect(text).not.toContain("4.5");
    expect(text).not.toContain(originalProse);
    expect(breakdown).toContain("500");
    expect(breakdown).toContain("200");
    expect(breakdown).toContain("10");
    expect(breakdown).toContain("5");
    expect(text).toContain(t("chat.strategy_type.dca_accumulation"));
    expect(breakdown).toContain(t("chat.confirmation.contribution_periods.monthly"));
  });

  test("missing metrics stay unavailable instead of reviving private prose", async () => {
    const t = await translator("es-419");
    const text = resultQuickTakeText(resultReadoutFacts({ quick_take: originalProse }), t, "es-419");
    expect(text).toBe(t("chat.result_readout.unavailable"));
    expect(text).not.toContain(originalProse);
  });

  test("typed indicator periods and thresholds remain visible in Spanish", async () => {
    const facts = resultReadoutFacts({ ...bank, config_snapshot: {
      ...config, template: "rsi_mean_reversion",
      resolved_parameters: { indicator: "rsi", indicator_period: 14, entry_threshold: 30, exit_threshold: 70 },
    } });
    const text = resultBreakdownText(facts, await translator("es-419"), "es-419");
    expect(text).toContain("RSI(14) igual o inferior a 30");
    expect(text).toContain("RSI(14) igual o superior a 70");
  });

  test("voices the full typed signal rule group in Spanish", async () => {
    const facts = resultReadoutFacts({ ...bank, config_snapshot: {
      ...config, template: "signal_strategy", resolved_strategy: {
        strategy_type: "signal_strategy", rule_spec: {
          entry: { combinator: "all", conditions: [
            { left: { kind: "indicator", key: "sma", period: 20 }, operator: "cross_above", right: { kind: "indicator", key: "ema", period: 50 } },
            { left: { kind: "price", field: "close" }, operator: "gt", right: 100 },
          ] },
        },
      },
    } });
    const text = resultBreakdownText(facts, await translator("es-419"), "es-419");
    expect(text).toContain("SMA(20) cruza por encima de EMA(50) y Cierre es superior a 100");
    expect(text).not.toContain(originalProse);
  });

  test("legacy breakdown keeps its typed result facts after hydration", async () => {
    const message = hydrateMessagesFromApi([{
      id: "breakdown-language", conversation_id: "conversation-language", role: "assistant",
      content: originalProse, created_at: "2025-12-31T17:00:00Z",
      metadata: { chat_action: { type: "show_breakdown" }, result_fact_bank: bank },
    }]).messages[0];
    expect(message.content).toBeUndefined();
    expect(message.recoveryDisplay).toEqual({ kind: "result_breakdown", facts: resultReadoutFacts(bank) });
  });

  test("a legacy result without card chrome still renders its repaired typed facts", () => {
    const message = hydrateMessagesFromApi([{
      id: "result-no-card", conversation_id: "conversation-language", role: "assistant",
      content: originalProse, created_at: "2025-12-31T17:00:00Z",
      metadata: { result_fact_bank: bank },
    }]).messages[0];
    expect(message.contentPresentation).toBe("result_readout");
    expect(message.resultReadoutFacts).toEqual(resultReadoutFacts(bank));
    expect(message.content).toBeUndefined();
    expect(messageStreamPresentation([message], message, 0, false, false).isWorkingMessage).toBe(false);
  });

  test("live run and historical message carry the same language-neutral facts", async () => {
    const card = {
      title: originalProse, strategy_label: originalProse, status_label: originalProse,
      date_range: { start: config.start_date, end: config.end_date, display: originalProse },
      rows: [], assumptions: [originalProse], actions: [],
      execution_costs: bank.result_card.execution_costs,
    };
    const run = { ...bank, id: "run-language", status: "completed", allocation_method: "equal_weight", conversation_result_card: card, created_at: "2025-12-31T17:00:00Z" } as BacktestRun;
    const live = resultCardFromRun(run);
    const historical = hydrateMessagesFromApi([{
      id: "result-language", conversation_id: "conversation-language", role: "assistant",
      content: originalProse, created_at: run.created_at,
      metadata: { result_card: card, result_fact_bank: bank, result_run_id: run.id },
    }]).messages[0];
    expect(historical.result?.readoutFacts).toEqual(live.readoutFacts);
    const view = resultCardViewModel(live, { t: await translator("es-419"), locale: "es-419" });
    expect(JSON.stringify(view)).not.toContain(originalProse);
  });

  test("failed historical repair renders Spanish unavailable, never permanent working", async () => {
    const message = hydrateMessagesFromApi([{
      id: "missing-run", conversation_id: "conversation-language", role: "assistant",
      content: "", created_at: "2025-12-31T17:00:00Z",
      metadata: { conversation_mode: "result_review", result_run_id: "lost-run", result_fact_bank: {} },
    }]).messages[0];
    const t = await translator("es-419");
    expect(message.contentPresentation).toBe("result_readout");
    expect(resultQuickTakeText(message.resultReadoutFacts, t, "es-419")).toBe(t("chat.result_readout.unavailable"));
    expect(messageStreamPresentation([message], message, 0, false, false).isWorkingMessage).toBe(false);
  });
});
