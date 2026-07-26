import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  coverageRecoveryActionsFromMetadata,
  noProgressActionsFromMetadata,
  recoveryDisplayFromMetadata,
  recoveryDisplayFromRecoveryState,
  recoveryDisplayText,
  unsupportedStrategyActionsFromMetadata,
  unsupportedTimeframeActionsFromMetadata,
} from "../lib/chat-recovery-display";

const root = join(import.meta.dir, "..");
const enCatalog = JSON.parse(
  readFileSync(join(root, "public/locales/en/common.json"), "utf8"),
) as Record<string, unknown>;
const esCatalog = JSON.parse(
  readFileSync(join(root, "public/locales/es-419/common.json"), "utf8"),
) as Record<string, unknown>;

function tFromCatalog(catalog: Record<string, unknown>) {
  return (key: string, options?: Record<string, unknown> | string) => {
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
      return key;
    }
    const values =
      typeof options === "object" && options !== null
        ? options
        : ({} as Record<string, unknown>);
    return template.replace(/\{\{(\w+)\}\}/g, (_, name: string) =>
      String(values[name] ?? ""),
    );
  };
}

function flattenedKeys(value: unknown, prefix = ""): string[] {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return prefix ? [prefix] : [];
  }
  return Object.entries(value as Record<string, unknown>).flatMap(([key, nested]) =>
    flattenedKeys(nested, prefix ? `${prefix}.${key}` : key),
  );
}

describe("chat recovery display", () => {
  test("hydrates only the safe typed no-progress choices", () => {
    const metadata = {
      response_intent: {
        kind: "clarification",
        facts: { progress_outcome: "no_progress" },
        requested_fields: ["date_range"],
        options: [
          {
            id: "supply_missing_value",
            label: "Provide the missing value",
            replacement_values: { requested_field: "date_range" },
          },
          {
            id: "keep_unchanged",
            label: "Keep the idea unchanged",
            replacement_values: { no_progress_action: "keep_unchanged" },
          },
          {
            id: "cancel",
            label: "Cancel this flow",
            replacement_values: { no_progress_action: "cancel" },
          },
          {
            id: "unsafe",
            label: "Run it anyway",
            replacement_values: { run_backtest: true },
          },
        ],
      },
    };

    expect(
      noProgressActionsFromMetadata(metadata, "assistant-no-progress"),
    ).toEqual([
      {
        id: "no-progress-supply-missing-value",
        label: "Provide the missing value",
        labelKey:
          "chat.clarification.no_progress_actions.supply_missing_value",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-no-progress",
          option_id: "supply_missing_value",
          replacement_values: { requested_field: "date_range" },
        },
      },
      {
        id: "no-progress-keep-unchanged",
        label: "Keep the idea unchanged",
        labelKey: "chat.clarification.no_progress_actions.keep_unchanged",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-no-progress",
          option_id: "keep_unchanged",
          replacement_values: { no_progress_action: "keep_unchanged" },
        },
      },
      {
        id: "no-progress-cancel",
        label: "Cancel this flow",
        labelKey: "chat.clarification.no_progress_actions.cancel",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-no-progress",
          option_id: "cancel",
          replacement_values: { no_progress_action: "cancel" },
        },
      },
    ]);
  });

  test("fails closed on conflicting or malformed no-progress metadata", () => {
    const validIntent = {
      kind: "clarification",
      facts: { progress_outcome: "no_progress" },
      requested_fields: ["date_range"],
      options: [
        {
          id: "supply_missing_value",
          label: "Provide the missing value",
          replacement_values: { requested_field: "date_range" },
        },
      ],
    };

    expect(
      noProgressActionsFromMetadata(
        {
          response_intent: validIntent,
          pending_strategy: {
            response_intent: {
              ...validIntent,
              requested_fields: ["asset_universe"],
            },
          },
        },
        "assistant-no-progress",
      ),
    ).toEqual([]);
    expect(
      noProgressActionsFromMetadata(
        {
          response_intent: {
            ...validIntent,
            options: [
              {
                id: "supply_missing_value",
                label: "Provide the missing value",
                replacement_values: {
                  requested_field: "date_range",
                  run_backtest: true,
                },
              },
            ],
          },
        },
        "assistant-no-progress",
      ),
    ).toEqual([]);
  });

  test("renders recovery codes through locale catalogs", () => {
    const display = recoveryDisplayFromMetadata({
      recovery: {
        code: "runtime_failure",
        retryable: true,
      },
    });

    expect(recoveryDisplayText(display, tFromCatalog(enCatalog))).toBe(
      "Something went wrong. Your conversation is saved. Please try again.",
    );
    expect(recoveryDisplayText(display, tFromCatalog(esCatalog))).toBe(
      "Algo salió mal. Tu conversación está guardada. Intenta de nuevo.",
    );
  });

  test("renders abandoned owning-row recovery in English and Spanish", () => {
    const display = recoveryDisplayFromMetadata({
      agent_runtime_turn: {
        status: "abandoned",
        failure_code: "turn_abandoned",
        retryable: true,
      },
      recovery: {
        code: "turn_abandoned",
        retryable: true,
      },
    });

    expect(recoveryDisplayText(display, tFromCatalog(enCatalog))).toBe(
      "That turn stopped before finishing. Your message is saved, so you can retry.",
    );
    expect(recoveryDisplayText(display, tFromCatalog(esCatalog))).toBe(
      "Ese turno se detuvo antes de terminar. Tu mensaje está guardado, así que puedes reintentarlo.",
    );
  });

  test("does not replace live clarification prompts with generic recovery text", () => {
    const display = recoveryDisplayFromMetadata({
      response_intent: {
        kind: "clarification",
        semantic_needs: ["period"],
        facts: {
          strategy: {
            asset_universe: ["AAPL"],
          },
        },
      },
    });

    expect(display).toBeNull();
  });

  test("renders typed clarification sidecars through locale catalogs", () => {
    const display = recoveryDisplayFromMetadata({
      clarification: {
        kind: "clarification",
        reason_code: "missing_period",
        prompt_source: "degraded_fallback",
        requested_field: "date_range",
        semantic_needs: ["period"],
        payload: {
          strategy: {
            asset_universe: ["AAPL"],
          },
        },
        options: [],
      },
    });

    expect(recoveryDisplayText(display, tFromCatalog(enCatalog))).toBe(
      "What date window should I use for AAPL?",
    );
    expect(recoveryDisplayText(display, tFromCatalog(esCatalog))).toBe(
      "¿Qué periodo quieres usar para AAPL?",
    );
  });

  test("renders unsupported recovery options from typed replacement values", () => {
    const display = recoveryDisplayFromMetadata({
      response_intent: {
        kind: "unsupported_recovery",
        facts: {
          strategy: {
            asset_universe: ["NVDA"],
          },
          unsupported_constraints: [
            {
              raw_value: "invalid_chronological_date_range",
            },
          ],
        },
        options: [
          {
            replacement_values: {
              simplify_logic: "rsi_only",
            },
          },
          {
            replacement_values: {
              strategy_type: "buy_and_hold",
            },
          },
        ],
      },
    });

    const text = recoveryDisplayText(display, tFromCatalog(esCatalog));

    expect(text).toBe(
      "Argus todavía no puede ejecutar esa regla directamente para NVDA. ¿Qué camino quieres usar: Usar una regla RSI compatible o Comparar con comprar y mantener?",
    );
    expect(text).not.toContain("invalid_chronological_date_range");
  });

  test("renders unsupported recovery from typed clarification sidecars", () => {
    const display = recoveryDisplayFromMetadata({
      clarification: {
        kind: "unsupported_recovery",
        reason_code: "unsupported_strategy_logic",
        prompt_source: "degraded_fallback",
        requested_field: "unsupported_constraints",
        semantic_needs: ["simplification_choice"],
        payload: {
          raw_value: "ATR 14",
          strategy: {
            asset_universe: ["TSLA"],
          },
        },
        options: [
          {
            id: "rsi_threshold",
            replacement_values: {
              simplify_logic: "rsi_only",
            },
          },
          {
            id: "buy_and_hold",
            replacement_values: {
              strategy_type: "buy_and_hold",
            },
          },
        ],
      },
    });

    expect(recoveryDisplayText(display, tFromCatalog(esCatalog))).toBe(
      "Argus todavía no puede ejecutar ATR 14 directamente para TSLA. ¿Qué camino quieres usar: Usar una regla RSI compatible o Comparar con comprar y mantener?",
    );
  });

  test("renders degraded timeframe recovery truthfully in English and Spanish", () => {
    const display = recoveryDisplayFromMetadata({
      clarification: {
        kind: "unsupported_recovery",
        reason_code: "unsupported_time_granularity",
        prompt_source: "degraded_fallback",
        requested_field: "timeframe",
        requested_fields: ["timeframe"],
        semantic_needs: ["simplification_choice"],
        payload: {
          raw_value: "5m",
          strategy: { asset_universe: ["AAPL"], timeframe: "5m" },
        },
        options: [
          {
            id: "option_0",
            replacement_values: { timeframe: "1D" },
          },
          {
            id: "option_1",
            replacement_values: { timeframe: "1h" },
          },
        ],
      },
    });

    expect(recoveryDisplayText(display, tFromCatalog(enCatalog))).toBe(
      "5m is not a supported bar size. Choose daily or 1-hour bars.",
    );
    expect(recoveryDisplayText(display, tFromCatalog(esCatalog))).toBe(
      "5m no es un tamaño de barra compatible. Elige barras diarias o de 1 hora.",
    );
  });

  test("renders degraded future-performance recovery truthfully in English and Spanish", () => {
    const display = recoveryDisplayFromMetadata({
      clarification: {
        kind: "unsupported_recovery",
        reason_code: "future_performance",
        prompt_source: "degraded_fallback",
        requested_field: "unsupported_constraints",
        requested_fields: ["unsupported_constraints"],
        semantic_needs: ["simplification_choice"],
        payload: {
          raw_value: "in ten years",
          strategy: { asset_universe: ["NVDA"], capital_amount: 10000 },
        },
        options: [
          {
            id: "historical_period",
            replacement_values: { requested_field: "date_range" },
          },
          {
            id: "buy_and_hold",
            replacement_values: {
              strategy_type: "buy_and_hold",
              requested_field: "date_range",
            },
          },
        ],
      },
    });

    expect(recoveryDisplayText(display, tFromCatalog(enCatalog))).toBe(
      "I can't predict future performance. I can test how the same idea performed over a historical period instead: Test it over a historical period or Compare with buy and hold?",
    );
    expect(recoveryDisplayText(display, tFromCatalog(esCatalog))).toBe(
      "No puedo predecir el rendimiento futuro. Puedo probar cómo se comportó la misma idea en un período histórico: Probarlo en un período histórico o Comparar con comprar y mantener?",
    );
  });

  test("invalid historical date repair keeps its distinct backend labels", () => {
    const display = recoveryDisplayFromMetadata({
      clarification: {
        kind: "unsupported_recovery",
        reason_code: "invalid_date_range",
        prompt_source: "degraded_fallback",
        requested_field: "unsupported_constraints",
        semantic_needs: ["simplification_choice"],
        payload: {
          raw_value: "January 2025 through January 2020",
          strategy: { asset_universe: ["AAPL"] },
        },
        options: [
          {
            id: "option_0",
            compatibility_label: "Choose an end date after the start date",
            replacement_values: { requested_field: "date_range" },
          },
          {
            id: "option_1",
            compatibility_label: "Choose a start date before the end date",
            replacement_values: { requested_field: "date_range" },
          },
          {
            id: "option_2",
            compatibility_label: "Use a different date window",
            replacement_values: { requested_field: "date_range" },
          },
        ],
      },
    });

    const en = recoveryDisplayText(display, tFromCatalog(enCatalog));
    expect(en).toContain("Choose an end date after the start date");
    expect(en).toContain("Choose a start date before the end date");
    expect(en).toContain("Use a different date window");
    expect(en).not.toContain("Test it over a historical period");

    const es = recoveryDisplayText(display, tFromCatalog(esCatalog));
    expect(es).toContain("Choose an end date after the start date");
    expect(es).not.toContain("Probarlo en un período histórico");
  });

  test("degraded momentum recovery is capability-honest in English and Spanish", () => {
    const display = recoveryDisplayFromMetadata({
      clarification: {
        kind: "unsupported_recovery",
        reason_code: "unsupported_strategy_logic",
        prompt_source: "degraded_fallback",
        requested_field: "unsupported_constraints",
        semantic_needs: ["simplification_choice"],
        payload: {
          raw_value: "a momentum breakout strategy",
          strategy: { asset_universe: ["AAPL"] },
        },
        options: [
          {
            id: "rsi_threshold",
            replacement_values: { simplify_logic: "rsi_only" },
          },
          {
            id: "buy_and_hold",
            replacement_values: { strategy_type: "buy_and_hold" },
          },
        ],
      },
    });

    const en = recoveryDisplayText(display, tFromCatalog(enCatalog));
    expect(en).toContain("a momentum breakout strategy");
    expect(en).not.toContain("does not define");
    const es = recoveryDisplayText(display, tFromCatalog(esCatalog));
    expect(es).toContain("a momentum breakout strategy");
    expect(es).not.toContain("no define");
  });

  test("renders provider-neutral coverage recovery in English and Spanish", () => {
    const metadata = {
      clarification: {
        kind: "coverage_recovery",
        reason_code: "no_common_data_window",
        prompt_source: "degraded_fallback",
        requested_field: null,
        requested_fields: [
          "date_range",
          "asset_universe",
          "comparison_baseline",
        ],
        semantic_needs: ["simplification_choice"],
        payload: {
          strategy: { asset_universe: ["AAPL"] },
          coverage: {
            code: "no_common_data_window",
            benchmark_symbol: "SPY",
          },
        },
        options: [
          {
            id: "change_dates",
            replacement_values: { requested_field: "date_range" },
          },
          {
            id: "change_asset",
            replacement_values: { requested_field: "asset_universe" },
          },
          {
            id: "change_benchmark",
            replacement_values: { requested_field: "comparison_baseline" },
          },
        ],
      },
    };
    const display = recoveryDisplayFromMetadata(metadata);

    expect(recoveryDisplayText(display, tFromCatalog(enCatalog))).toBe(
      "Those assets and the benchmark do not share a usable data window for one trustworthy test. Change the dates, an asset, or the benchmark.",
    );
    expect(recoveryDisplayText(display, tFromCatalog(esCatalog))).toBe(
      "Esos activos y la referencia no comparten un rango de datos utilizable para una prueba confiable. Cambia las fechas, un activo o la referencia.",
    );
    expect(
      coverageRecoveryActionsFromMetadata(metadata, "assistant-coverage"),
    ).toEqual([
      {
        id: "coverage-change-dates",
        label: "Change dates",
        labelKey: "chat.coverage_recovery.actions.change_dates",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-coverage",
          option_id: "change_dates",
          replacement_values: { requested_field: "date_range" },
        },
      },
      {
        id: "coverage-change-asset",
        label: "Change asset",
        labelKey: "chat.coverage_recovery.actions.change_asset",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-coverage",
          option_id: "change_asset",
          replacement_values: { requested_field: "asset_universe" },
        },
      },
      {
        id: "coverage-change-benchmark",
        label: "Change benchmark",
        labelKey: "chat.coverage_recovery.actions.change_benchmark",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-coverage",
          option_id: "change_benchmark",
          replacement_values: { requested_field: "comparison_baseline" },
        },
      },
    ]);
  });

  test("hydrates only safe typed unsupported-timeframe actions", () => {
    const metadata = {
      clarification: {
        kind: "unsupported_recovery",
        reason_code: "unsupported_time_granularity",
        prompt_source: "llm_generated",
        requested_field: "timeframe",
        requested_fields: ["timeframe"],
        semantic_needs: ["simplification_choice"],
        payload: { raw_value: "5m", strategy: { asset_universe: ["AAPL"] } },
        options: [
          {
            id: "option_0",
            compatibility_label: "Retry with daily bars",
            replacement_values: { timeframe: "1D" },
          },
          {
            id: "option_1",
            compatibility_label: "Retry with 1-hour bars",
            replacement_values: { timeframe: "1h" },
          },
          {
            id: "option_unsafe",
            compatibility_label: "Unsafe",
            replacement_values: { timeframe: "5m", provider: "internal" },
          },
        ],
      },
    };

    expect(
      unsupportedTimeframeActionsFromMetadata(metadata, "assistant-timeframe"),
    ).toEqual([
      {
        id: "unsupported-timeframe-option-0",
        label: "Retry with daily bars",
        labelKey: "chat.clarification.timeframe_actions.daily",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-timeframe",
          option_id: "option_0",
          replacement_values: { timeframe: "1D" },
        },
      },
      {
        id: "unsupported-timeframe-option-1",
        label: "Retry with 1-hour bars",
        labelKey: "chat.clarification.timeframe_actions.hour_1",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-timeframe",
          option_id: "option_1",
          replacement_values: { timeframe: "1h" },
        },
      },
    ]);
    expect(
      recoveryDisplayFromMetadata({
        ...metadata,
        response_intent: {
          kind: "unsupported_recovery",
          options: metadata.clarification.options,
          facts: {
            unsupported_constraints: [
              {
                category: "unsupported_time_granularity",
                raw_value: "5m",
              },
            ],
          },
        },
      }),
    ).toBeNull();
  });

  test("projects supported strategy options with exact server replacement values", () => {
    const movingAverageReplacementValues = {
      strategy_type: "signal_strategy",
      rule_family: "moving_average_crossover",
    };
    const metadata = {
      clarification: {
        kind: "unsupported_recovery",
        reason_code: "unsupported_strategy_logic",
        prompt_source: "llm_generated",
        options: [
          {
            id: "rsi_threshold",
            replacement_values: { simplify_logic: "rsi_only" },
          },
          {
            id: "buy_and_hold",
            replacement_values: { strategy_type: "buy_and_hold" },
          },
          {
            id: "moving_average_crossover",
            replacement_values: movingAverageReplacementValues,
          },
        ],
      },
    };

    expect(
      unsupportedStrategyActionsFromMetadata(metadata, "assistant-strategy"),
    ).toEqual([
      {
        id: "unsupported-strategy-rsi-threshold",
        label: "Use a supported RSI threshold rule",
        labelKey: "chat.simplification_options.rsi_threshold",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-strategy",
          option_id: "rsi_threshold",
          replacement_values: { simplify_logic: "rsi_only" },
        },
      },
      {
        id: "unsupported-strategy-buy-and-hold",
        label: "Compare with buy and hold",
        labelKey: "chat.simplification_options.buy_and_hold",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-strategy",
          option_id: "buy_and_hold",
          replacement_values: { strategy_type: "buy_and_hold" },
        },
      },
      {
        id: "unsupported-strategy-moving-average-crossover",
        label: "Use a supported moving-average crossover",
        labelKey: "chat.simplification_options.moving_average_crossover",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-strategy",
          option_id: "moving_average_crossover",
          replacement_values: movingAverageReplacementValues,
        },
      },
    ]);
  });

  test("does not project unknown or untyped unsupported strategy options", () => {
    const metadata = {
      clarification: {
        kind: "unsupported_recovery",
        reason_code: "unsupported_strategy_logic",
        options: [
          {
            id: "unknown_strategy",
            replacement_values: { strategy_type: "buy_and_hold" },
          },
          {
            id: "rsi_threshold",
          },
          {
            replacement_values: { simplify_logic: "rsi_only" },
          },
          {
            id: "buy_and_hold",
            replacement_values: { simplify_logic: "rsi_only" },
          },
        ],
      },
    };

    expect(
      unsupportedStrategyActionsFromMetadata(metadata, "assistant-strategy"),
    ).toEqual([]);
  });

  test("recovery locale keys stay in parity", () => {
    for (const namespace of [
      "chat.recovery",
      "chat.clarification",
      "chat.coverage_recovery",
      "chat.simplification_options",
    ]) {
      const enKeys = flattenedKeys(
        namespace
          .split(".")
          .reduce<unknown>(
            (value, segment) =>
              typeof value === "object" &&
              value !== null &&
              !Array.isArray(value)
                ? (value as Record<string, unknown>)[segment]
                : undefined,
            enCatalog,
          ),
      );
      const esKeys = flattenedKeys(
        namespace
          .split(".")
          .reduce<unknown>(
            (value, segment) =>
              typeof value === "object" &&
              value !== null &&
              !Array.isArray(value)
                ? (value as Record<string, unknown>)[segment]
                : undefined,
            esCatalog,
          ),
      );

      expect(esKeys).toEqual(enKeys);
    }
  });
});

describe("recoveryDisplayFromRecoveryState llm_generated prose ownership", () => {
  test("llm_generated recovery keeps the voiced prose as the display owner", () => {
    expect(
      recoveryDisplayFromRecoveryState({
        code: "discovery_search_failed",
        retryable: true,
        prompt_source: "llm_generated",
      }),
    ).toBeNull();
  });

  test("typed fallback recovery still renders from the localized code", () => {
    expect(
      recoveryDisplayFromRecoveryState({
        code: "discovery_search_failed",
        retryable: true,
      }),
    ).toEqual({
      kind: "recovery_code",
      code: "discovery_search_failed",
      values: undefined,
    });
  });
});
