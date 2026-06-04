import { describe, expect, test } from "bun:test";

import type { Message } from "../components/chat/types";
import { appendOrReplacePendingAssistantMessage } from "../lib/chat-send-state";

describe("chat send state", () => {
  test("retry replaces the failed assistant turn instead of appending a second assistant reply", () => {
    const failed: Message = {
      id: "assistant-failed-1",
      role: "ai",
      kind: "text",
      content: "Something went wrong.",
      actions: [
        {
          id: "retry-last-turn",
          label: "Retry",
          type: "retry_last_turn",
        },
      ],
    };

    const messages = appendOrReplacePendingAssistantMessage(
      [{ id: "user-1", role: "user", kind: "text", content: "test AAPL" }, failed],
      {
        assistantId: "assistant-failed-1",
        pendingAssistant: {
          id: "assistant-failed-1",
          role: "ai",
          kind: "text",
          content: "",
        },
        userMessage: {
          id: "user-retry-1",
          role: "user",
          kind: "text",
          content: "test AAPL",
        },
        renderUserMessage: false,
      },
    );

    expect(messages).toEqual([
      { id: "user-1", role: "user", kind: "text", content: "test AAPL" },
      { id: "assistant-failed-1", role: "ai", kind: "text", content: "" },
    ]);
  });
});
