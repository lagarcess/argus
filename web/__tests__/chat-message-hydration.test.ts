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
});
