import { describe, expect, test } from "bun:test";

import type { Message } from "../components/chat/types";
import {
  appendOrReplacePendingAssistantMessage,
  replaceOrAppendFinalAssistantMessage,
} from "../lib/chat-send-state";

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

  test("appends final assistant artifact when route hydration removed the pending placeholder", () => {
    const hydratedUser: Message = {
      id: "user-persisted-1",
      role: "user",
      kind: "text",
      content: "Backtest AAPL",
    };
    const finalAssistant: Message = {
      id: "assistant-persisted-1",
      role: "ai",
      kind: "strategy_confirmation",
      confirmation: {
        confirmation_id: "confirmation-1",
        confirmation_state: "active",
        title: "AAPL buy and hold",
        summary: "Ready to test AAPL.",
        status: "ready_to_run",
        statusLabel: "Ready to run",
        strategy_type: "buy_and_hold",
        asset_class: "equity",
        rows: [],
        actions: [{ label: "Run backtest", type: "run_backtest" }],
      },
      actions: [{ label: "Run backtest", type: "run_backtest" }],
    };

    expect(
      replaceOrAppendFinalAssistantMessage(
        [hydratedUser],
        "local-pending-assistant",
        finalAssistant,
      ),
    ).toEqual([hydratedUser, finalAssistant]);
  });
});
