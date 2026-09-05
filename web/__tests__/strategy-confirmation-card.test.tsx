import { describe, expect, test } from "bun:test";
import i18next from "i18next";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";

import StrategyConfirmationCard from "../components/chat/StrategyConfirmationCard";
import type { StrategyConfirmationPayload } from "../components/chat/types";
import en from "../public/locales/en/common.json";

function confirmation(
  symbols: string[],
  strategyType?: StrategyConfirmationPayload["strategy_type"],
): StrategyConfirmationPayload {
  return {
    title: "Ready to test",
    status: "ready_to_run",
    statusLabel: "Ready to run",
    summary: "Review this backtest before running it.",
    strategy_type: strategyType,
    rows: [
      { key: "assets", label: "Assets", value: symbols.join(", ") },
      { key: "period", label: "Period", value: "Last 12 months" },
    ],
    assumptions: [],
    actions: [],
  };
}

async function renderConfirmationMarkup(
  payload: StrategyConfirmationPayload,
  disabled = false,
) {
  const i18n = i18next.createInstance();
  await i18n.init({
    lng: "en",
    fallbackLng: false,
    interpolation: { escapeValue: false },
    resources: { en: { translation: en } },
  });
  const html = renderToStaticMarkup(
    createElement(
      I18nextProvider,
      { i18n },
      createElement(StrategyConfirmationCard, { confirmation: payload, disabled }),
    ),
  );
  return html;
}

async function renderConfirmation(payload: StrategyConfirmationPayload) {
  const html = await renderConfirmationMarkup(payload);
  return html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");
}

function wordCount(text: string, value: string) {
  return text.match(new RegExp(`\\b${value}\\b`, "g"))?.length ?? 0;
}

describe("StrategyConfirmationCard asset heading", () => {
  test("keeps confirmation actions disabled while another turn is in flight", async () => {
    const payload = confirmation(["AAPL"], "buy_and_hold");
    payload.actions = [
      { id: "run-fresh", type: "run_backtest", label: "Run backtest" },
    ];

    const markup = await renderConfirmationMarkup(payload, true);

    expect(markup).toMatch(/<button[^>]*disabled=""[^>]*>.*Run backtest/);
  });

  test("renders a single entity symbol once when no strategy label exists", async () => {
    const text = await renderConfirmation(confirmation(["AAPL"]));

    expect(wordCount(text, "AAPL")).toBe(1);
  });

  test("renders each symbol once for a two-asset confirmation", async () => {
    const text = await renderConfirmation(confirmation(["AAPL", "SPY"]));

    expect(wordCount(text, "AAPL")).toBe(1);
    expect(wordCount(text, "SPY")).toBe(1);
  });

  test("keeps a typed strategy label beside the entity token", async () => {
    const text = await renderConfirmation(
      confirmation(["AAPL"], "buy_and_hold"),
    );

    expect(wordCount(text, "AAPL")).toBe(1);
    expect(text).toContain("Buy and Hold");
  });

  test("keeps the aggregate heading above two assets", async () => {
    const text = await renderConfirmation(confirmation(["AAPL", "MSFT", "SPY"]));

    expect(text).toContain("3 assets");
    expect(wordCount(text, "AAPL")).toBe(1);
    expect(wordCount(text, "MSFT")).toBe(1);
    expect(wordCount(text, "SPY")).toBe(1);
  });
});
