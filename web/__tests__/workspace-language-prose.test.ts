/**
 * The presentation-boundary half of the workspace-language invariant.
 *
 * `docs/CONVERSATIONAL_RUNTIME.md` binds prose to the workspace language, and
 * the backend keeps its side of the bargain by emitting typed codes with
 * English compatibility text beside them. This suite asserts the other side:
 * given what the backend actually sends, an `es-419` reader sees Spanish.
 *
 * The assertions are properties, not string lists. #434, #489 and #482 were
 * each a different string, and enumerating the three that were reported is how
 * the fourth one ships.
 */

import { describe, expect, test } from "bun:test";
import type { TFunction } from "i18next";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { confirmationAssumptionDisplay } from "../lib/confirmation-assumptions-display";
import {
  recoveryDisplayFromMetadata,
  recoveryDisplayText,
} from "../lib/chat-recovery-display";

const root = join(import.meta.dir, "..");
const catalogs = {
  en: JSON.parse(
    readFileSync(join(root, "public/locales/en/common.json"), "utf8"),
  ) as Record<string, unknown>,
  "es-419": JSON.parse(
    readFileSync(join(root, "public/locales/es-419/common.json"), "utf8"),
  ) as Record<string, unknown>,
};

function tFromCatalog(catalog: Record<string, unknown>): TFunction {
  return ((key: string, options?: Record<string, unknown> | string) => {
    const template = key
      .split(".")
      .reduce<unknown>(
        (value, segment) =>
          typeof value === "object" && value !== null && !Array.isArray(value)
            ? (value as Record<string, unknown>)[segment]
            : undefined,
        catalog,
      );
    if (typeof template !== "string") {
      return typeof options === "string" ? options : key;
    }
    const values =
      typeof options === "object" && options !== null
        ? options
        : ({} as Record<string, unknown>);
    return template.replace(/\{\{(\w+)\}\}/g, (_, name: string) =>
      String(values[name] ?? ""),
    );
  }) as unknown as TFunction;
}

const tEn = tFromCatalog(catalogs.en);
const tEs = tFromCatalog(catalogs["es-419"]);

/**
 * The shapes the backend can persist on a degraded turn, each paired with the
 * English compatibility prose it ships alongside. The prose is what a Spanish
 * reader must never see.
 */
const DEGRADED_METADATA_SHAPES: Array<{
  label: string;
  metadata: Record<string, unknown>;
  englishCompatProse: string;
}> = [
  {
    label: "coverage recovery without options",
    metadata: {
      clarification: {
        kind: "coverage_recovery",
        reason_code: "no_common_data_window",
        prompt_source: "degraded_fallback",
        payload: { strategy: { asset_universe: ["AAPL"] }, coverage: {} },
        options: [],
      },
    },
    englishCompatProse:
      "Those assets and the benchmark do not share a usable data window. Would you like to change the dates, an asset, or the benchmark?",
  },
  {
    label: "coverage recovery with a generic reason code",
    metadata: {
      clarification: {
        kind: "coverage_recovery",
        reason_code: "insufficient_common_data",
        prompt_source: "degraded_fallback",
        payload: { strategy: {}, coverage: {} },
        options: [],
      },
    },
    englishCompatProse:
      "The shared data window is not sufficient for a trustworthy test. Would you like to change the dates, an asset, or the benchmark?",
  },
  {
    label: "future performance without options",
    metadata: {
      clarification: {
        kind: "unsupported_recovery",
        reason_code: "future_performance",
        prompt_source: "degraded_fallback",
        payload: { strategy: { asset_universe: ["NVDA"] } },
        options: [],
      },
    },
    englishCompatProse: "I cannot predict future performance.",
  },
  {
    label: "unsupported bar size without options",
    metadata: {
      clarification: {
        kind: "unsupported_recovery",
        reason_code: "unsupported_time_granularity",
        prompt_source: "degraded_fallback",
        payload: { strategy: {}, raw_value: "cada 5 minutos" },
        options: [],
      },
    },
    englishCompatProse: "is not a supported bar size",
  },
  {
    label: "starting capital bounds without options",
    metadata: {
      clarification: {
        kind: "unsupported_recovery",
        reason_code: "unsupported_starting_capital",
        prompt_source: "degraded_fallback",
        payload: { strategy: {}, minimum: 1000, maximum: 10000000 },
        options: [],
      },
    },
    englishCompatProse: "Starting capital must be between",
  },
  {
    label: "unsupported rule with options",
    metadata: {
      clarification: {
        kind: "unsupported_recovery",
        reason_code: "unsupported_strategy_logic",
        prompt_source: "degraded_fallback",
        payload: { strategy: { asset_universe: ["AAPL"] } },
        options: [
          {
            id: "buy_and_hold",
            replacement_values: { strategy_type: "buy_and_hold" },
          },
        ],
      },
    },
    englishCompatProse: "Argus can't run that rule directly yet",
  },
  {
    label: "clarification asking for a period",
    metadata: {
      clarification: {
        kind: "clarification",
        reason_code: "missing_period",
        prompt_source: "degraded_fallback",
        semantic_needs: ["period"],
        payload: { strategy: { asset_universe: ["AAPL"] } },
        options: [],
      },
    },
    englishCompatProse: "What date window should I use",
  },
  {
    label: "capacity refusal",
    metadata: {
      recovery: { code: "backtest_capacity_exceeded", retryable: true },
    },
    englishCompatProse: "Argus is already running as many backtests as it can",
  },
];

describe("workspace language prose", () => {
  test.each(DEGRADED_METADATA_SHAPES)(
    "$label renders in Spanish on an es-419 workspace",
    ({ metadata, englishCompatProse }) => {
      const display = recoveryDisplayFromMetadata(metadata);
      expect(display).not.toBeNull();

      const spanish = recoveryDisplayText(display, tEs);
      const english = recoveryDisplayText(display, tEn);

      // Something was rendered: an empty string drops the reader back onto the
      // persisted English, which is the failure #489 describes.
      expect(spanish.trim().length).toBeGreaterThan(0);
      // It is the Spanish copy, not the English one.
      expect(spanish).not.toBe(english);
      // And it is not the backend's compatibility prose leaking through.
      expect(spanish).not.toContain(englishCompatProse);
      // No key fell through unresolved.
      expect(spanish).not.toContain("chat.");
    },
  );

  test("the confirmation card localizes zero execution costs", () => {
    // What the backend sends today: typed facts own fees and slippage, and the
    // English strip no longer carries a second copy of them (#434).
    const displayFacts = { fees: 0, slippage: 0, timeframe: "1D" };
    const spanish = confirmationAssumptionDisplay({
      displayFacts,
      fallbackAssumptions: ["$10,000 starting capital", "Datos diarios"],
      locale: "es-419",
      promotedValues: [],
      t: tEs,
    });

    expect(spanish).toContain("Sin comisiones");
    expect(spanish).toContain("Sin deslizamiento");
    expect(spanish).not.toContain("No fees");
    expect(spanish).not.toContain("No slippage");
  });

  test("a card persisted before typed facts still avoids English cost prose", () => {
    // Older rows carry only the strip. Nothing in it should be English cost
    // prose, because the backend stopped writing that.
    const spanish = confirmationAssumptionDisplay({
      displayFacts: null,
      fallbackAssumptions: ["Datos diarios", "Benchmark: SPY"],
      locale: "es-419",
      promotedValues: [],
      t: tEs,
    });

    expect(spanish.join(" ")).not.toContain("No fees");
    expect(spanish.join(" ")).not.toContain("No slippage");
  });

  test("every recovery code the backend can emit has distinct Spanish copy", () => {
    // The tell of an untranslated key is copy that is identical in both
    // bundles: it reads as coverage and proves nothing (#489).
    const enRecovery = (catalogs.en as Record<string, Record<string, unknown>>)
      .chat.recovery as Record<string, unknown>;
    const esRecovery = (
      catalogs["es-419"] as Record<string, Record<string, unknown>>
    ).chat.recovery as Record<string, unknown>;

    for (const [code, english] of Object.entries(enRecovery)) {
      if (typeof english !== "string") continue;
      const spanish = esRecovery[code];
      expect(typeof spanish).toBe("string");
      expect(spanish).not.toBe(english);
    }
  });
});
