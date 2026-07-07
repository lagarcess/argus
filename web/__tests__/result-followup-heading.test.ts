import { describe, expect, test } from "bun:test";

import { hydrateTextMessageFromApi } from "../lib/chat-message-hydration";
import { resultFactHeadingKeyFromMetadata } from "../lib/result-followup-heading";
import type { ApiMessage } from "../lib/argus-api";

function apiMessage(overrides: Partial<ApiMessage>): ApiMessage {
  return {
    id: "assistant-1",
    conversation_id: "conversation-1",
    role: "assistant",
    content: "The peak portfolio value was $14,500.25 on 2021-11-09.",
    created_at: "2026-07-01T00:00:00Z",
    metadata: {},
    ...overrides,
  };
}

describe("result followup heading key", () => {
  test("extracts the fact key from a beginner_guidance fact answer", () => {
    expect(
      resultFactHeadingKeyFromMetadata({
        response_intent: {
          kind: "beginner_guidance",
          facts: { fact_key: "peak_date", peak_date: "2021-11-09" },
        },
      }),
    ).toBe("peak_date");
  });

  test("falls back to requested_metric for a typed limitation", () => {
    expect(
      resultFactHeadingKeyFromMetadata({
        response_intent: {
          kind: "unsupported_recovery",
          facts: {
            limitation_code: "latest_result_metric_unavailable",
            requested_metric: "sortino_ratio",
          },
        },
      }),
    ).toBe("sortino_ratio");
  });

  test("extracts frontend chrome heading keys from result followup intent", () => {
    expect(
      resultFactHeadingKeyFromMetadata({
        response_intent: {
          kind: "result_followup_chrome",
          facts: { focus: "next_experiment", heading_key: "next_experiment" },
        },
      }),
    ).toBe("next_experiment");
  });

  test("ignores other intent kinds and malformed payloads", () => {
    expect(
      resultFactHeadingKeyFromMetadata({
        response_intent: { kind: "clarification", facts: { fact_key: "peak_date" } },
      }),
    ).toBeNull();
    expect(resultFactHeadingKeyFromMetadata({})).toBeNull();
    expect(
      resultFactHeadingKeyFromMetadata({ response_intent: "beginner_guidance" }),
    ).toBeNull();
    expect(
      resultFactHeadingKeyFromMetadata({
        response_intent: { kind: "beginner_guidance", facts: { fact_key: "  " } },
      }),
    ).toBeNull();
  });

  test("hydrates the typed heading key from persisted message metadata", () => {
    const message = hydrateTextMessageFromApi(
      apiMessage({
        metadata: {
          response_intent: {
            kind: "beginner_guidance",
            facts: { fact_key: "peak_date" },
          },
        },
      }),
    );

    expect(message.resultFactHeadingKey).toBe("peak_date");
  });

  test("leaves user messages without a heading key", () => {
    const message = hydrateTextMessageFromApi(
      apiMessage({
        role: "user",
        metadata: {
          response_intent: {
            kind: "beginner_guidance",
            facts: { fact_key: "peak_date" },
          },
        },
      }),
    );

    expect(message.resultFactHeadingKey).toBeUndefined();
  });
});
