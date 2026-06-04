import { describe, expect, test } from "bun:test";

import { mergeFinalTextMessage } from "../lib/chat-final-message";

describe("chat final message merge", () => {
  test("adds final retry actions to an already-streamed assistant message", () => {
    const retryAction = {
      id: "retry-failed-action-1",
      label: "Retry",
      value: "Retry",
      type: "retry_failed_action" as const,
      artifactType: "failed_action" as const,
    };

    const message = mergeFinalTextMessage(
      {
        id: "assistant-1",
        role: "ai",
        kind: "text",
        content: "I could not run this because one detail is not valid.",
      },
      {
        assistantId: "assistant-1",
        finalText: "I could not run this because one detail is not valid.",
        finalActions: [retryAction],
      },
    );

    expect(message.content).toBe(
      "I could not run this because one detail is not valid.",
    );
    expect(message.actions).toEqual([retryAction]);
  });

  test("final runtime text replaces provisional streamed text", () => {
    const message = mergeFinalTextMessage(
      {
        id: "assistant-1",
        role: "ai",
        kind: "text",
        content: "I can show you a confirmation if you want.",
      },
      {
        assistantId: "assistant-1",
        finalText: "Ready to test AAPL buy and hold.",
        finalActions: [],
      },
    );

    expect(message.content).toBe("Ready to test AAPL buy and hold.");
  });

  test("leaves unrelated messages unchanged", () => {
    const message = {
      id: "other",
      role: "ai" as const,
      kind: "text" as const,
      content: "Existing message",
    };

    expect(
      mergeFinalTextMessage(message, {
        assistantId: "assistant-1",
        finalText: "Final",
        finalActions: [],
      }),
    ).toBe(message);
  });
});
