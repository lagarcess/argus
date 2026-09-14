import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { TFunction } from "i18next";

import { directEditErrorText } from "../components/chat/ConfirmationDirectEdit";
import { formatChartCurrency } from "../components/chat/ResultEquityChart";
import type { StrategyResultPayload } from "../components/chat/types";
import {
  recoveryDisplayFromMetadata,
  recoveryDisplayText,
} from "../lib/chat-recovery-display";
import { formatCurrency, heroDeltaEvidenceView } from "../lib/result-card-display";

const root = join(import.meta.dir, "..");

function translator(language: "en" | "es-419"): TFunction {
  const bundle = JSON.parse(
    readFileSync(join(root, `public/locales/${language}/common.json`), "utf8"),
  ) as Record<string, unknown>;
  const translate = (key: string, options?: Record<string, unknown> | string) => {
    const template = key
      .split(".")
      .reduce<unknown>(
        (node, part) =>
          typeof node === "object" && node !== null
            ? (node as Record<string, unknown>)[part]
            : undefined,
        bundle,
      );
    if (typeof template !== "string") return key;
    const values = typeof options === "object" && options !== null ? options : {};
    return template.replace(/\{\{(\w+)\}\}/g, (_, name: string) =>
      String(values[name] ?? ""),
    );
  };
  return translate as unknown as TFunction;
}

function resultWith(
  cashValue: string,
  totalReturn: string,
  series: number[],
): StrategyResultPayload {
  return {
    title: "AAPL Buy and Hold",
    metrics: [
      { key: "cash_value", label: "Ending value", value: cashValue },
      { key: "total_return_pct", label: "Total return", value: totalReturn },
    ],
    chart: {
      kind: "portfolio_equity",
      series: series.map((value, index) => ({
        time: `2024-01-${String(index + 2).padStart(2, "0")}`,
        value,
      })),
    },
  } as unknown as StrategyResultPayload;
}

describe("the $10 starting-capital floor", () => {
  for (const [language, expected] of [
    [
      "en",
      "Starting capital must be between $10 and $100,000,000. What amount in that range should I use?",
    ],
    [
      "es-419",
      "El capital inicial debe estar entre $10 y $100,000,000. ¿Qué monto dentro de ese rango quieres usar?",
    ],
  ] as const) {
    test(`the chat recovery for $9.99 names $10 in ${language}`, () => {
      const metadata = {
        clarification: {
          kind: "unsupported_recovery",
          reason_code: "unsupported_starting_capital",
          prompt_source: "degraded_fallback",
          requested_field: "capital_amount",
          semantic_needs: ["simplification_choice"],
          payload: {
            minimum: 10,
            maximum: 100_000_000,
            strategy: { asset_universe: ["NFLX"] },
          },
          options: [
            {
              id: "option_0",
              compatibility_label: "Use $10",
              replacement_values: { capital_amount: 10 },
            },
          ],
        },
      };
      expect(
        recoveryDisplayText(recoveryDisplayFromMetadata(metadata), translator(language)),
      ).toBe(expected);
    });

    test(`the in-place capital refusal names the card's $10 floor in ${language}`, () => {
      const text = directEditErrorText("invalid_starting_capital", translator(language), {
        capital: { min: 10, max: 100_000_000 },
      });
      expect(text).toContain("$10 ");
      expect(text).toContain(`$${(100_000_000).toLocaleString()}`);
    });

    test(`a card without bounds never restates a floor in ${language}`, () => {
      const t = translator(language);
      const text = directEditErrorText("invalid_starting_capital", t, undefined);
      expect(text).toBe(t("chat.confirmation.direct_edit.failed"));
      expect(text).not.toContain("1,000");
    });
  }
});

describe("a $10 result reads in cents", () => {
  test("the hero, its change, and the starting capital", () => {
    const view = heroDeltaEvidenceView(resultWith("$10 -> $12.05", "+20.5%", [10, 11.2, 12.05]));
    expect(view.hero.value).toBe("$12.05");
    expect(view.hero.detail).toBe("+$2.05 gain · +20.5% total return");
    expect(view.details).toContainEqual({ label: "Starting capital", value: "$10" });
  });

  test("a change under a dollar is not rounded away", () => {
    const view = heroDeltaEvidenceView(resultWith("$10 -> $10.40", "+4.0%", [10, 10.4]));
    expect(view.hero.detail).toBe("+$0.40 gain · +4.0% total return");
    expect(view.hero.tone).toBe("positive");
  });

  test("the equity chart axis and tooltip", () => {
    expect(formatChartCurrency(12.05, "USD", "en-US", 12.05)).toBe("$12.05");
    expect(formatChartCurrency(10, "USD", "en-US", 12.05)).toBe("$10");
  });

  test("Spanish money keeps its cents with the viewer's separators", () => {
    expect(formatCurrency(12.05, "es-419", "USD", 12.05)).toBe(
      new Intl.NumberFormat("es-419", {
        style: "currency",
        currency: "USD",
        currencyDisplay: "narrowSymbol",
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      }).format(12.05),
    );
  });

  test("a run that reached $1,000 keeps whole dollars", () => {
    const view = heroDeltaEvidenceView(
      resultWith("$1,000 -> $1,350", "+35.0%", [1000, 850.37, 1350]),
    );
    expect(view.hero.value).toBe("$1,350");
    expect(view.hero.detail).toBe("+$350 gain · +35.0% total return");
    expect(formatChartCurrency(850.37, "USD", "en-US", 1350)).toBe("$850");
  });
});
