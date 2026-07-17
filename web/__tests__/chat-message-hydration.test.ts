import { describe, expect, test } from "bun:test";

import { hydrateTextMessageFromApi } from "../lib/chat-message-hydration";
import type { ApiMessage } from "../lib/argus-api";

function apiMessage(overrides: Partial<ApiMessage>): ApiMessage {
  return {
    id: "assistant-failed-1",
    conversation_id: "conversation-1",
    role: "assistant",
    content: "Something went wrong. Your conversation is saved. Please try again.",
    created_at: "2026-06-01T00:00:00Z",
    metadata: {},
    ...overrides,
  };
}

describe("chat message hydration", () => {
  test("hydrates a retry action from persisted assistant failure metadata", () => {
    const message = hydrateTextMessageFromApi(
      apiMessage({
        metadata: {
          recovery: {
            code: "runtime_failure",
            retryable: true,
          },
          retry_last_turn: {
            message: "what if I bought $125 of BTC every two weeks in 2022?",
          },
        },
      }),
    );

    expect(message.role).toBe("ai");
    expect(message.kind).toBe("text");
    expect(message.recoveryDisplay).toEqual({
      kind: "recovery_code",
      code: "runtime_failure",
      values: undefined,
    });
    expect(message.actions).toEqual([
      {
        id: "retry-last-turn",
        label: "Retry",
        labelKey: "common.retry",
        value: "Retry",
        type: "retry_last_turn",
        payload: {
          message: "what if I bought $125 of BTC every two weeks in 2022?",
          failed_assistant_id: "assistant-failed-1",
        },
      },
    ]);
  });

  test("does not expose retry actions on user messages", () => {
    const message = hydrateTextMessageFromApi(
      apiMessage({
        id: "user-1",
        role: "user",
        content: "Retry",
        metadata: {
          retry_last_turn: {
            message: "should stay server-side only",
          },
        },
      }),
    );

    expect(message.role).toBe("user");
    expect(message.actions).toBeUndefined();
  });

  test("hydrates coverage recovery actions from persisted typed metadata", () => {
    const message = hydrateTextMessageFromApi(
      apiMessage({
        id: "assistant-coverage-1",
        content: "Compatibility coverage recovery copy.",
        metadata: {
          clarification: {
            kind: "coverage_recovery",
            reason_code: "insufficient_common_data",
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
                code: "insufficient_common_data",
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
        },
      }),
    );

    expect(message.recoveryDisplay).toEqual({
      kind: "coverage_recovery",
      code: "insufficient_common_data",
    });
    expect(message.actions?.map((action) => action.labelKey)).toEqual([
      "chat.coverage_recovery.actions.change_dates",
      "chat.coverage_recovery.actions.change_asset",
      "chat.coverage_recovery.actions.change_benchmark",
    ]);
  });

  test("preserves persisted LLM coverage voice while hydrating all typed actions", () => {
    const exactLlmPrompt =
      "AAPL and SPY do not share enough history for one trustworthy test. Which part should we change?";
    const message = hydrateTextMessageFromApi(
      apiMessage({
        id: "assistant-coverage-llm",
        content: exactLlmPrompt,
        metadata: {
          clarification: {
            kind: "coverage_recovery",
            reason_code: "no_common_data_window",
            prompt_source: "llm_generated",
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
                replacement_values: {
                  requested_field: "comparison_baseline",
                },
              },
            ],
          },
        },
      }),
    );

    expect(message.content).toBe(exactLlmPrompt);
    expect(message.recoveryDisplay).toBeNull();
    expect(message.actions?.map((action) => action.labelKey)).toEqual([
      "chat.coverage_recovery.actions.change_dates",
      "chat.coverage_recovery.actions.change_asset",
      "chat.coverage_recovery.actions.change_benchmark",
    ]);
  });

  test("preserves LLM timeframe voice while hydrating safe correction actions", () => {
    const exactLlmPrompt =
      "Five-minute bars are not supported. Choose daily or one-hour bars.";
    const message = hydrateTextMessageFromApi(
      apiMessage({
        id: "assistant-timeframe-llm",
        content: exactLlmPrompt,
        metadata: {
          clarification: {
            kind: "unsupported_recovery",
            reason_code: "unsupported_time_granularity",
            prompt_source: "llm_generated",
            requested_field: "timeframe",
            requested_fields: ["timeframe"],
            semantic_needs: ["simplification_choice"],
            payload: { raw_value: "5m" },
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
            ],
          },
        },
      }),
    );

    expect(message.content).toBe(exactLlmPrompt);
    expect(message.recoveryDisplay).toBeNull();
    expect(message.actions).toEqual([
      {
        id: "unsupported-timeframe-option-0",
        label: "Retry with daily bars",
        labelKey: "chat.clarification.timeframe_actions.daily",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-timeframe-llm",
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
          source_assistant_id: "assistant-timeframe-llm",
          option_id: "option_1",
          replacement_values: { timeframe: "1h" },
        },
      },
    ]);
  });
});
