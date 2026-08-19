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

  test("final clarification carries its backend-owned strategy path", () => {
    const message = mergeFinalTextMessage(
      {
        id: "assistant-1",
        role: "ai",
        kind: "text",
        content: "Which asset should I test?",
      },
      {
        assistantId: "assistant-1",
        finalText: "Which asset should I test?",
        finalActions: [],
        strategyPathContext: {
          kind: "clarification",
          requestedField: "asset_universe",
          strategy: {
            strategy_type: "buy_and_hold",
            capital_amount: 10_000,
          },
        },
      } as Parameters<typeof mergeFinalTextMessage>[1] & {
        strategyPathContext: {
          kind: "clarification";
          requestedField: string;
          strategy: Record<string, unknown>;
        };
      },
    );

    expect(message.strategyPathContext).toEqual({
      kind: "clarification",
      requestedField: "asset_universe",
      strategy: {
        strategy_type: "buy_and_hold",
        capital_amount: 10_000,
      },
    });
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

describe("chat final frame visibility", () => {
  test("a final frame with no prose and no artifact still yields a visible turn", () => {
    // Production 2026-08-11..13: a Spanish chip click got no assistant reply
    // at all. The backend cannot end a turn silently by construction, so the
    // last silent shape was a final frame carrying neither text nor an
    // artifact; the handler must render the localized turn-failure copy
    // instead of leaving the placeholder empty.
    const { readFileSync } = require("node:fs");
    const { join } = require("node:path");
    const chat = readFileSync(
      join(__dirname, "..", "components/chat/ChatInterface.tsx"),
      "utf-8",
    );
    const finalHandler = chat.slice(
      chat.indexOf("} else if (finalText) {"),
      chat.indexOf("terminalReadiness.accept(event.data, identityAuthorized)"),
    );
    expect(finalHandler).toContain("} else {");
    expect(finalHandler).toContain('content: t("chat.error_backtest")');
    expect(finalHandler).toContain("replaceOrAppendFinalAssistantMessage");
  });
});
