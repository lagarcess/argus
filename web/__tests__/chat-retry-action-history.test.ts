import { describe, expect, test } from "bun:test";

import { normalizeRetryActionHistory } from "../lib/chat-retry-action-history";
import type { ChatActionOption, Message } from "../components/chat/types";

const retryAction: ChatActionOption = {
  id: "retry-failed-action-failed-1",
  label: "Retry",
  value: "Retry",
  type: "retry_failed_action",
  artifactType: "failed_action",
  artifactStatus: "failed",
  payload: { failed_action_id: "failed-1" },
};

function failedMessage(id = "failed-message"): Message {
  return {
    id,
    role: "ai",
    kind: "text",
    content: "I could not run this.",
    actions: [retryAction],
  };
}

describe("chat retry action history", () => {
  test("keeps retry visible on the latest unresolved failed assistant message", () => {
    const [message] = normalizeRetryActionHistory([failedMessage()]);

    expect(message.actions).toEqual([retryAction]);
  });

  test("strips stale retry actions after a later result artifact exists", () => {
    const messages = normalizeRetryActionHistory([
      failedMessage(),
      {
        id: "result-message",
        role: "ai",
        kind: "strategy_result",
        result: {
          strategyName: "AAPL buy and hold",
          period: "2024",
          metrics: [],
        },
      },
    ]);

    expect(messages[0].actions).toBeUndefined();
    expect(messages[1].kind).toBe("strategy_result");
  });

  test("strips stale retry actions after a later assistant answer exists", () => {
    const messages = normalizeRetryActionHistory([
      failedMessage(),
      {
        id: "answer-message",
        role: "ai",
        kind: "text",
        content: "I rebuilt the draft.",
      },
    ]);

    expect(messages[0].actions).toBeUndefined();
    expect(messages[1].actions).toBeUndefined();
  });

  test("preserves non-retry actions while stripping stale retry actions", () => {
    const breakdownAction: ChatActionOption = {
      id: "show-breakdown",
      label: "Show breakdown",
      value: "Show breakdown",
      type: "show_breakdown",
      presentation: "result",
      payload: { run_id: "run-1" },
    };
    const messages = normalizeRetryActionHistory([
      {
        ...failedMessage(),
        actions: [retryAction, breakdownAction],
      },
      {
        id: "user-followup",
        role: "user",
        kind: "text",
        content: "try something else",
      },
    ]);

    expect(messages[0].actions).toEqual([breakdownAction]);
  });
});
