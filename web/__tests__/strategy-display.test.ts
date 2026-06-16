import { describe, expect, test } from "bun:test";

import type {
  StrategyConfirmationPayload,
  StrategyResultPayload,
} from "../components/chat/types";
import {
  strategyDisplayLabel,
  strategyTypeFromConfirmation,
  strategyTypeFromResult,
} from "../lib/strategy-display";

const spanishT = (key: string, options?: string | { defaultValue?: string }) => {
  const fallback =
    typeof options === "string" ? options : options?.defaultValue ?? key;
  const labels: Record<string, string> = {
    "chat.strategy_type.buy_and_hold": "Comprar y mantener",
    "chat.strategy_type.dca_accumulation": "Compras recurrentes",
  };
  return labels[key] ?? fallback;
};

describe("strategy display labels", () => {
  test("localizes result strategy labels from canonical templates over persisted copy", () => {
    const result: StrategyResultPayload = {
      strategyName: "NVDA DCA Accumulation",
      strategyLabel: "DCA Accumulation",
      template: "dca_accumulation",
      symbols: ["NVDA"],
      period: "June 14, 2025 to June 12, 2026",
      statusLabel: "Simulation Complete",
      metrics: [],
    };

    expect(
      strategyDisplayLabel(
        strategyTypeFromResult(result),
        spanishT,
        result.strategyLabel,
      ),
    ).toBe("Compras recurrentes");
  });

  test("localizes confirmation strategy labels from canonical fields over persisted copy", () => {
    const confirmation: StrategyConfirmationPayload = {
      confirmation_state: "active",
      status: "ready_to_run",
      statusLabel: "Ready to run",
      title: "ETH buy and hold",
      strategy_type: "buy_and_hold",
      summary: "Ready to test buy-and-hold for ETH.",
      rows: [
        {
          key: "strategy",
          label: "Strategy",
          labelKey: "chat.confirmation.rows.strategy",
          value: "Buy and Hold",
        },
        {
          key: "assets",
          label: "Assets",
          labelKey: "chat.confirmation.rows.assets",
          value: "ETH",
        },
      ],
    };

    expect(
      strategyDisplayLabel(
        strategyTypeFromConfirmation(confirmation),
        spanishT,
        confirmation.rows[0]?.value,
      ),
    ).toBe("Comprar y mantener");
  });

  test("preserves legacy display labels when no canonical strategy type exists", () => {
    expect(strategyDisplayLabel(null, spanishT, "Legacy custom idea")).toBe(
      "Legacy custom idea",
    );
  });
});
