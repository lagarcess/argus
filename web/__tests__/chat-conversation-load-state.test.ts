import { describe, expect, test } from "bun:test";

import {
  conversationLoadFailureMessage,
  shouldShowEmptyChatSurface,
  shouldShowConversationDisclaimer,
} from "../lib/chat-conversation-load-state";

describe("chat conversation load state", () => {
  test("routes every settled empty conversation through its account landing surface", () => {
    expect(
      shouldShowEmptyChatSurface({
        messages: [],
        isHydratingConversation: false,
        hasConversationLoadFailure: false,
      }),
    ).toBe(true);
  });

  test("keeps loading failures and non-empty transcripts off the empty surface", () => {
    expect(
      shouldShowEmptyChatSurface({
        messages: [],
        isHydratingConversation: true,
        hasConversationLoadFailure: false,
      }),
    ).toBe(false);
    expect(
      shouldShowEmptyChatSurface({
        messages: [],
        isHydratingConversation: false,
        hasConversationLoadFailure: true,
      }),
    ).toBe(false);
    expect(
      shouldShowEmptyChatSurface({
        messages: [
          {
            id: "user-message",
            role: "user",
            kind: "text",
            content: "Compare Apple with SPY",
          },
        ],
        isHydratingConversation: false,
        hasConversationLoadFailure: false,
      }),
    ).toBe(false);
  });

  test("builds a retryable assistant message for transient conversation load failures", () => {
    const message = conversationLoadFailureMessage(
      " conversation-1 ",
      "Could not load that conversation. Try again.",
    );

    expect(message).toEqual({
      id: "conversation-load-failed",
      role: "ai",
      kind: "text",
      contentPresentation: "conversation_load_failure",
      content: "Could not load that conversation. Try again.",
      assistantRecoveryCode: "conversation_load_failure",
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

  test("does not treat a synthetic load failure as disclaimer-worthy activity", () => {
    const message = conversationLoadFailureMessage(
      "conversation-1",
      "Could not load that conversation. Try again.",
    );

    expect(shouldShowConversationDisclaimer([message], false)).toBe(false);
  });

  test("shows the disclaimer after real chat activity or streaming starts", () => {
    expect(
      shouldShowConversationDisclaimer(
        [{ id: "user-1", role: "user", kind: "text", content: "Test Apple" }],
        false,
      ),
    ).toBe(true);
    expect(shouldShowConversationDisclaimer([], true)).toBe(true);
  });
});
