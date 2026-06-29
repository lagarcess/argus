import { describe, expect, test } from "bun:test";

import {
  confirmationAssumptionDisplay,
  type ConfirmationDisplayFacts,
} from "../lib/confirmation-assumptions-display";

const englishT = (
  key: string,
  options?: string | { defaultValue?: string; date?: string; symbol?: string },
) => {
  const fallback =
    typeof options === "string" ? options : options?.defaultValue ?? key;
  const values: Record<string, string> = {
    "chat.asset_class.equity": "Stocks",
    "chat.result_card.timeframe.daily": "Daily data",
    "chat.confirmation.assumptions.through": `Through ${typeof options === "object" ? options.date : ""}`,
    "chat.confirmation.assumptions.no_fees": "No fees",
    "chat.confirmation.assumptions.no_slippage": "No slippage",
    "chat.confirmation.assumptions.modeled_costs": "Modeled costs: 10 bps fee + 5 bps slippage",
    "chat.confirmation.assumptions.benchmark": `Benchmark: ${typeof options === "object" ? options.symbol : ""}`,
  };
  return values[key] ?? fallback;
};

describe("confirmation assumption display", () => {
  test("renders canonical display facts in the selected locale over persisted copy", () => {
    const facts: ConfirmationDisplayFacts = {
      benchmark_symbol: "SPY",
      data_through: "2026-06-12",
      fees: 0,
      slippage: 0,
      timeframe: "1D",
    };

    expect(
      confirmationAssumptionDisplay({
        assetClass: "equity",
        displayFacts: facts,
        fallbackAssumptions: [
          "Datos diarios",
          "Hasta 12 jun",
          "Sin comisiones",
          "Referencia: SPY",
        ],
        locale: "en-US",
        promotedValues: [],
        t: englishT,
      }),
    ).toEqual([
      "Stocks",
      "Daily data",
      "Through Jun 12",
      "No fees",
      "No slippage",
      "Benchmark: SPY",
    ]); 
  });

  test("renders non-zero modeled fees and slippage as one cost line", () => {
    const facts: ConfirmationDisplayFacts = {
      benchmark_symbol: "SPY",
      fees: 0.001,
      slippage: 0.0005,
      timeframe: "1D",
    };

    expect(
      confirmationAssumptionDisplay({
        assetClass: "equity",
        displayFacts: facts,
        fallbackAssumptions: ["No fees", "No slippage", "Benchmark: SPY"],
        locale: "en-US",
        promotedValues: [],
        t: englishT,
      }),
    ).toEqual([
      "Stocks",
      "Daily data",
      "Modeled costs: 10 bps fee + 5 bps slippage",
      "Benchmark: SPY",
    ]);
  });

  test("preserves filtered legacy assumptions when canonical facts are absent", () => {
    expect(
      confirmationAssumptionDisplay({
        assetClass: "equity",
        displayFacts: undefined,
        fallbackAssumptions: ["$100 starting capital", "Daily data"],
        locale: "en-US",
        promotedValues: ["$100"],
        t: englishT,
      }),
    ).toEqual(["Stocks", "Daily data"]);
  });
});
