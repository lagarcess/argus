import { describe, expect, test } from "bun:test";
import i18next from "i18next";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";

import StrategyConfirmationCard from "../components/chat/StrategyConfirmationCard";
import type { StrategyConfirmationPayload } from "../components/chat/types";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";

type RetestPeriodFixture = {
  original_date_range: { start: string; end: string };
  requested_date_range: { start: string; end: string };
  effective_date_range: { start: string; end: string };
  duration_days: number;
  duration: {
    unit: "year" | "month" | "day";
    count: number;
    approximate: boolean;
  };
};

type RetestConfirmationFixture = StrategyConfirmationPayload & {
  retest_period: RetestPeriodFixture;
};

const EXTENDED_PERIOD: RetestPeriodFixture = {
  original_date_range: { start: "2024-01-01", end: "2024-12-31" },
  requested_date_range: { start: "2024-01-01", end: "2026-07-31" },
  effective_date_range: { start: "2024-01-01", end: "2026-06-30" },
  duration_days: 911,
  duration: { unit: "year", count: 2.5, approximate: true },
};

function confirmation(retestPeriod: RetestPeriodFixture): RetestConfirmationFixture {
  return {
    confirmation_id: "confirmation-retest-1",
    confirmation_state: "active",
    asset_class: "equity",
    title: "AAPL",
    status: "ready_to_run",
    statusLabel: "Ready to run",
    summary: "Review this backtest before running it.",
    strategy_type: "buy_and_hold",
    date_range: retestPeriod.effective_date_range,
    display_facts: {
      benchmark_symbol: "SPY",
      data_through: retestPeriod.effective_date_range.end,
      fees: 0,
      slippage: 0,
      timeframe: "1Day",
    },
    rows: [
      { key: "assets", label: "Assets", value: "AAPL" },
      { key: "strategy", label: "Strategy", value: "Buy and hold" },
      { key: "starting_capital", label: "Starting capital", value: "$10,000" },
      { key: "period", label: "Period", value: "provider-owned period" },
      { key: "cadence", label: "Cadence", value: "monthly" },
    ],
    assumptions: ["This fallback must not replace typed facts"],
    actions: [
      {
        id: "run-backtest-confirmation-retest-1",
        label: "Run backtest",
        labelKey: "chat.confirmation.actions.run_backtest",
        type: "run_backtest",
        payload: { confirmation_id: "confirmation-retest-1" },
      },
      {
        id: "change-dates-confirmation-retest-1",
        label: "Change dates",
        labelKey: "chat.confirmation.actions.change_dates",
        type: "change_dates",
        payload: { confirmation_id: "confirmation-retest-1" },
      },
    ],
    retest_period: retestPeriod,
  };
}

async function renderLocalized(
  payload: RetestConfirmationFixture,
  locale: "en" | "es-419",
): Promise<string> {
  const i18n = i18next.createInstance();
  await i18n.init({
    lng: locale,
    fallbackLng: false,
    interpolation: { escapeValue: false },
    resources: {
      en: { translation: en },
      "es-419": { translation: es },
    },
  });

  return renderToStaticMarkup(
    createElement(
      I18nextProvider,
      { i18n },
      createElement(StrategyConfirmationCard, { confirmation: payload }),
    ),
  );
}

describe("Retest confirmation period disclosure", () => {
  test("renders an extended provider-effective period and keeps the normal Run label", async () => {
    const html = await renderLocalized(confirmation(EXTENDED_PERIOD), "en");

    expect(html).toContain(
      "Jan 1, 2024 – Dec 31, 2024 → Jan 1, 2024 – Jun 30, 2026",
    );
    expect(html).toContain("Updated span: about 2.5 years");
    expect(html).toContain("Run backtest");
    expect(html).not.toContain("Run anyway — no new data");
    expect(html).not.toContain("No new data since the original run.");

    // Retest changes only the period; unrelated rows and assumptions survive.
    expect(html).toContain("$10,000");
    expect(html).toContain("Monthly");
    expect(html).toContain("Daily data");
    expect(html).toContain("No fees");
    expect(html).toContain("No slippage");
    expect(html).toContain("Benchmark: SPY");
    expect(html).toContain("Change dates");
  });

  test("renders an equivalent extended-period disclosure in Spanish", async () => {
    const html = await renderLocalized(confirmation(EXTENDED_PERIOD), "es-419");

    expect(html).toContain(
      "1 ene 2024 – 31 dic 2024 → 1 ene 2024 – 30 jun 2026",
    );
    expect(html).toContain("Duración actualizada: aproximadamente 2.5 años");
    expect(html).toContain("Ejecutar backtest");
    expect(html).not.toContain("Ejecutar de todos modos — no hay datos nuevos");
  });

});
