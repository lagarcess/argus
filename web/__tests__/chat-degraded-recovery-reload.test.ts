import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { hydrateTextMessageFromApi } from "../lib/chat-message-hydration";
import {
  recoveryDisplayCopyText,
  recoveryDisplayText,
} from "../lib/chat-recovery-display";

const esCatalog = JSON.parse(
  readFileSync(
    join(import.meta.dir, "../public/locales/es-419/common.json"),
    "utf8",
  ),
) as Record<string, unknown>;
const EXACT_LLM_VOICE = "Exact model recovery voice.";

function spanishTranslation(
  key: string,
  options?: Record<string, unknown> | string,
): string {
  const template = key
    .split(".")
    .reduce<unknown>(
      (value, segment) =>
        typeof value === "object" && value !== null && !Array.isArray(value)
          ? (value as Record<string, unknown>)[segment]
          : undefined,
      esCatalog,
    );
  if (typeof template !== "string") {
    return key;
  }
  const values =
    typeof options === "object" && options !== null ? options : {};
  return template.replace(/\{\{(\w+)\}\}/g, (_, name: string) =>
    String(values[name] ?? ""),
  );
}

describe("degraded recovery reload", () => {
  test("renders the Spanish typed fallback while preserving durable actions", () => {
    const hydrated = hydrateTextMessageFromApi({
      id: "assistant-degraded-timeframe",
      conversation_id: "conversation-1",
      role: "assistant",
      content: "5m is not a supported bar size. Choose daily or 1-hour bars.",
      created_at: "2026-07-17T12:00:00Z",
      metadata: {
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
              compatibility_label: "Retry with daily bars",
              replacement_values: { timeframe: "1D" },
            },
          ],
        },
      },
    });

    expect(hydrated.content).toBe(
      "5m is not a supported bar size. Choose daily or 1-hour bars.",
    );
    expect(
      recoveryDisplayText(hydrated.recoveryDisplay, spanishTranslation),
    ).toBe(
      "5m no es un tamaño de barra compatible. Elige barras diarias o de 1 hora.",
    );
    expect(hydrated.actions).toEqual([
      {
        id: "unsupported-timeframe-option-0",
        label: "Retry with daily bars",
        labelKey: "chat.clarification.timeframe_actions.daily",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-degraded-timeframe",
          option_id: "option_0",
          replacement_values: { timeframe: "1D" },
        },
      },
    ]);
  });

  test("copies localized degraded display but exact LLM recovery voice", () => {
    const degraded = hydrateTextMessageFromApi({
      id: "assistant-degraded-copy",
      conversation_id: "conversation-1",
      role: "assistant",
      content: "5m is not a supported bar size. Choose daily or 1-hour bars.",
      created_at: "2026-07-17T12:00:00Z",
      metadata: {
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
              compatibility_label: "Retry with daily bars",
              replacement_values: { timeframe: "1D" },
            },
          ],
        },
      },
    });
    const exactLlm = hydrateTextMessageFromApi({
      id: "assistant-llm-copy",
      conversation_id: "conversation-1",
      role: "assistant",
      content: EXACT_LLM_VOICE,
      created_at: "2026-07-17T12:01:00Z",
      metadata: {
        clarification: {
          kind: "clarification",
          reason_code: "missing_period",
          prompt_source: "llm_generated",
          requested_field: "date_range",
          requested_fields: ["date_range"],
          semantic_needs: ["period"],
          payload: { strategy: { asset_universe: ["AAPL"] } },
          options: [],
        },
      },
    });

    expect(
      recoveryDisplayCopyText(degraded.recoveryDisplay, spanishTranslation),
    ).toBe(
      "5m no es un tamaño de barra compatible. Elige barras diarias o de 1 hora.",
    );
    expect(
      recoveryDisplayCopyText(exactLlm.recoveryDisplay, spanishTranslation) ??
        exactLlm.content,
    ).toBe(EXACT_LLM_VOICE);
  });
});
