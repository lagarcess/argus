import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  confirmationPeriodAdjustmentText,
} from "../lib/confirmation-period-adjustment";
import type { StrategyConfirmationPeriodAdjustment } from "../components/chat/types";

const adjustment: StrategyConfirmationPeriodAdjustment = {
  code: "effective_window_adjusted",
  requested_date_range: { start: "2024-01-01", end: "2024-01-05" },
  effective_date_range: { start: "2024-01-03", end: "2024-01-05" },
};

const translations: Record<string, string> = {
  en: "I adjusted the test period to {{period}} because every asset and the benchmark need a shared data window.",
  "es-419": "Ajusté el período de la prueba a {{period}} porque cada activo y la referencia necesitan un rango de datos compartido.",
};

const translate = (locale: string) => (
  _key: string,
  options: { period: string },
) => translations[locale].replace("{{period}}", options.period);

describe("confirmation period adjustment", () => {
  test("renders a provider-neutral English lead-in from typed dates", () => {
    const text = confirmationPeriodAdjustmentText(
      adjustment,
      translate("en"),
      "en",
    );

    expect(text).toBe(
      "I adjusted the test period to Jan 3, 2024 – Jan 5, 2024 because every asset and the benchmark need a shared data window.",
    );
    expect(text).not.toContain("Alpaca");
  });

  test("renders the same typed contract in Spanish", () => {
    expect(
      confirmationPeriodAdjustmentText(
        adjustment,
        translate("es-419"),
        "es-419",
      ),
    ).toBe(
      "Ajusté el período de la prueba a 3 ene 2024 – 5 ene 2024 porque cada activo y la referencia necesitan un rango de datos compartido.",
    );
  });

  test("renders no lead-in for an unknown adjustment", () => {
    expect(
      confirmationPeriodAdjustmentText(
        { ...adjustment, code: "unknown" },
        translate("en"),
        "en",
      ),
    ).toBeNull();
  });

  test("places the lead-in immediately above the corrected confirmation card", () => {
    const source = readFileSync(
      join(import.meta.dir, "../components/chat/ChatMessage.tsx"),
      "utf8",
    );
    const branchStart = source.indexOf(
      'message.kind === "strategy_confirmation"',
    );
    const branchEnd = source.indexOf(
      'message.contentPresentation === "result_breakdown"',
      branchStart,
    );
    const branch = source.slice(branchStart, branchEnd);

    expect(branch.indexOf("{confirmationPeriodLeadIn ? (")).toBeGreaterThan(-1);
    expect(branch.indexOf("<StrategyConfirmationCard")).toBeGreaterThan(
      branch.indexOf("{confirmationPeriodLeadIn ? ("),
    );
  });
});
