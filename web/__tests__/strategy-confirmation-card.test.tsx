import { describe, test } from "bun:test";
import assert from "node:assert/strict";
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
      { id: "cancel", type: "cancel_confirmation", label: "Cancel" },
    ];

    const markup = await renderConfirmationMarkup(payload, true);

    assert.match(markup, /<button[^>]*disabled=""[^>]*>.*Cancel/);
  });

  test("reads stored confirmations without offering simulation execution", async () => {
    const payload = confirmation(["AAPL"], "buy_and_hold");
    payload.actions = [
      { id: "run", type: "run_backtest", label: "Run backtest" },
      { id: "retest", type: "retest_run", label: "Retest" },
    ];
    const markup = await renderConfirmationMarkup(payload);
    assert.equal(markup.includes("<button"), false);
    assert.equal(markup.includes("Ready to run"), false);
    assert.ok(markup.includes("AAPL"));
  });

  test("renders a single entity symbol once when no strategy label exists", async () => {
    const text = await renderConfirmation(confirmation(["AAPL"]));

    assert.equal(wordCount(text, "AAPL"), 1);
  });

  test("renders each symbol once for a two-asset confirmation", async () => {
    const text = await renderConfirmation(confirmation(["AAPL", "SPY"]));

    assert.equal(wordCount(text, "AAPL"), 1);
    assert.equal(wordCount(text, "SPY"), 1);
  });

  test("keeps a typed strategy label beside the entity token", async () => {
    const text = await renderConfirmation(
      confirmation(["AAPL"], "buy_and_hold"),
    );

    assert.equal(wordCount(text, "AAPL"), 1);
    assert.ok(text.includes("Buy and Hold"));
  });

  test("keeps the aggregate heading above two assets", async () => {
    const text = await renderConfirmation(confirmation(["AAPL", "MSFT", "SPY"]));

    assert.ok(text.includes("3 assets"));
    assert.equal(wordCount(text, "AAPL"), 1);
    assert.equal(wordCount(text, "MSFT"), 1);
    assert.equal(wordCount(text, "SPY"), 1);
  });
});
