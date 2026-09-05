import { describe, expect, test } from "bun:test";
import type { TFunction } from "i18next";

import en from "../public/locales/en/common.json";
import es419 from "../public/locales/es-419/common.json";
import type {
  StrategyConfirmationPayload,
  StrategyResultPayload,
} from "../components/chat/types";
import {
  confirmationCardCopyText,
  resultCardCopyText,
} from "../lib/chat-card-copy-text";
import { confirmationCardViewModel } from "../lib/confirmation-card-view-model";
import { resultCardViewModel } from "../lib/result-card-view-model";

/** Translates against the real shipped catalog, so the assertions prove the
 * strings a Spanish workspace actually renders reach the clipboard. */
function localeTranslator(tree: Record<string, unknown>): TFunction {
  const translate = (key: string, second?: unknown, third?: unknown) => {
    const entry = key
      .split(".")
      .reduce<unknown>(
        (node, part) =>
          node && typeof node === "object"
            ? (node as Record<string, unknown>)[part]
            : undefined,
        tree,
      );
    const options = (typeof second === "object" ? second : third) as
      | Record<string, unknown>
      | undefined;
    const fallback =
      typeof second === "string"
        ? second
        : ((options?.defaultValue as string | undefined) ?? key);
    const resolved = typeof entry === "string" ? entry : fallback;
    return resolved.replace(/\{\{(\w+)\}\}/g, (match, name: string) =>
      options && name in options ? String(options[name]) : match,
    );
  };
  return translate as unknown as TFunction;
}

const spanish = localeTranslator(es419 as Record<string, unknown>);
const english = localeTranslator(en as Record<string, unknown>);

// A card the backend built the way it really does: English `label` strings
// carried alongside the typed `key`/`labelKey` the frontend localizes.
const confirmation: StrategyConfirmationPayload = {
  confirmation_state: "active",
  status: "ready_to_run",
  statusLabel: "Ready to run",
  title: "AAPL Buy and Hold",
  summary: "Ready to test buy-and-hold for AAPL over the last year.",
  strategy_type: "buy_and_hold",
  asset_class: "equity",
  rows: [
    {
      key: "assets",
      label: "Assets",
      labelKey: "chat.confirmation.rows.assets",
      value: "AAPL",
    },
    {
      key: "starting_capital",
      label: "Starting capital",
      labelKey: "chat.confirmation.rows.starting_capital",
      value: "$10,000",
    },
    {
      key: "buy_rule",
      label: "Buy rule",
      labelKey: "chat.confirmation.rows.buy_rule",
      value: "Buy at the open",
    },
  ],
  assumptions: ["No fees", "No slippage"],
  actions: [],
};

const result: StrategyResultPayload = {
  strategyName: "AAPL Buy and Hold",
  strategyLabel: "Buy and Hold",
  template: "buy_and_hold",
  symbols: ["AAPL"],
  assetClass: "equity",
  period: "June 14, 2025 to June 12, 2026",
  statusLabel: "Simulation Complete",
  metrics: [
    { key: "ending_value", label: "Ending value", value: "$12,500" },
    { key: "total_return_pct", label: "Total return", value: "+25.0%" },
    { key: "max_drawdown_pct", label: "Worst drop", value: "-8.2%" },
  ],
};

describe("card copy reads the language the card renders (#509)", () => {
  test("confirmation copy carries localized row labels, never the backend English", () => {
    const copy = confirmationCardCopyText(
      confirmationCardViewModel(confirmation, spanish, "es-419"),
      spanish,
      "es-419",
    );

    expect(copy).toContain("Capital inicial: $10,000");
    expect(copy).toContain("Regla de compra: Buy at the open");
    expect(copy).toContain("Activos: AAPL");
    expect(copy).toContain("Supuestos:");
    expect(copy).not.toContain("Starting capital");
    expect(copy).not.toContain("Buy rule");
    expect(copy).not.toContain("Assumptions:");
  });

  test("confirmation copy omits the summary the card never renders", () => {
    const copy = confirmationCardCopyText(
      confirmationCardViewModel(confirmation, spanish, "es-419"),
      spanish,
      "es-419",
    );

    // The backend composes `summary` in English regardless of workspace
    // language, and the card does not paint it. Copy must not resurrect it.
    expect(copy).not.toContain("Ready to test buy-and-hold");
  });

  test("confirmation copy still matches the card in English", () => {
    const copy = confirmationCardCopyText(
      confirmationCardViewModel(confirmation, english, "en"),
      english,
      "en",
    );

    expect(copy).toContain("Starting capital: $10,000");
    expect(copy).toContain("Buy rule: Buy at the open");
    expect(copy).toContain("Assumptions:");
  });

  test("result copy carries localized metric labels, never the backend English", () => {
    const copy = resultCardCopyText(
      resultCardViewModel(result, { t: spanish, locale: "es-419" }),
      spanish,
    );

    expect(copy).toContain("Comprar y mantener");
    expect(copy).toContain("Activos: AAPL");
    expect(copy).toContain("Valor final:");
    expect(copy).toContain("Peor caída: -8.2%");
    expect(copy).toContain("Simulación completa");
    expect(copy).not.toContain("Ending value");
    expect(copy).not.toContain("Worst drop");
    expect(copy).not.toContain("Symbols:");
    expect(copy).not.toContain("Period:");
  });

  test("result copy still matches the card in English", () => {
    const copy = resultCardCopyText(
      resultCardViewModel(result, { t: english, locale: "en" }),
      english,
    );

    expect(copy).toContain("Buy and Hold");
    expect(copy).toContain("Assets: AAPL");
    expect(copy).toContain("Worst drop: -8.2%");
    expect(copy).toContain(`Assistant explanation:\n${english("chat.result_readout.unavailable")}`);
  });

  test("the assistant explanation heading is localized too", () => {
    const copy = resultCardCopyText(
      resultCardViewModel(result, { t: spanish, locale: "es-419" }),
      spanish,
    );

    expect(copy).toContain(`Explicación del asistente:\n${spanish("chat.result_readout.unavailable")}`);
    expect(copy).not.toContain("Assistant explanation");
  });
});
