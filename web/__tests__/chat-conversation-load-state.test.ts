import { describe, expect, test } from "bun:test";

import { conversationLoadFailureMessage } from "../lib/chat-conversation-load-state";

describe("chat conversation load state", () => {
  test("builds a retryable assistant message for transient conversation load failures", () => {
    const message = conversationLoadFailureMessage(
      " conversation-1 ",
      "Could not load that conversation. Try again.",
    );

    expect(message).toEqual({
      id: "conversation-load-failed",
      role: "ai",
      kind: "text",
      content: "Could not load that conversation. Try again.",
      actions: [
        {
          id: "retry-load-conversation",
          label: "Retry",
          labelKey: "common.retry",
          value: "Retry",
          type: "retry_load_conversation",
          payload: {
            conversation_id: "conversation-1",
          },
        },
      ],
    });
  });

  test("omits the retry action when there is no conversation id", () => {
    const message = conversationLoadFailureMessage(
      "  ",
      "Could not load that conversation. Try again.",
    );

    expect(message.actions).toBeUndefined();
  });
});
