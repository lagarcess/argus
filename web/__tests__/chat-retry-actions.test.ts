import { describe, expect, test } from "bun:test";

import {
  conversationLoadRetryActionFromConversationId,
  failedActionRetryActionFromMetadata,
  hasFailedActionMetadata,
  retryLastTurnActionFromMetadata,
  retryLastTurnActionFromMessage,
  retryLastTurnChatActionFromAction,
  retryLoadConversationIdFromAction,
  retryLastTurnMessageFromAction,
  isRetryAction,
} from "../lib/chat-retry-actions";

describe("failed-action retry UI contract", () => {
  test("hydrates a retry action from retryable failed-action metadata", () => {
    const action = failedActionRetryActionFromMetadata({
      latest_failed_action_reference: {
        artifact_kind: "failed_action",
        artifact_id: "failed-1",
        artifact_status: "failed",
        metadata: {
          retryable: true,
          launch_payload: {
            strategy_type: "buy_and_hold",
            symbols: ["AAPL"],
          },
        },
      },
    });

    expect(action).toEqual({
      id: "retry-failed-action-failed-1",
      label: "Retry",
      labelKey: "common.retry",
      value: "Retry",
      type: "retry_failed_action",
      artifactId: "failed-1",
      artifactType: "failed_action",
      artifactStatus: "failed",
      payload: { failed_action_id: "failed-1" },
    });
  });

  test("does not hydrate retry when failed action can only reopen its confirmation", () => {
    const metadata = {
      latest_failed_action_reference: {
        artifact_kind: "failed_action",
        artifact_id: "failed-invalid-date",
        artifact_status: "failed",
        metadata: {
          retryable: false,
          recovery_mode: "reopen_confirmation",
          launch_payload: {
            strategy_type: "buy_and_hold",
            symbols: ["AAPL"],
          },
        },
      },
    };
    const action = failedActionRetryActionFromMetadata(metadata);

    expect(action).toBeNull();
    expect(hasFailedActionMetadata(metadata)).toBe(true);
  });

  test("does not hydrate retry when metadata has no recoverable launch context", () => {
    expect(
      failedActionRetryActionFromMetadata({
        latest_failed_action_reference: {
          artifact_kind: "failed_action",
          artifact_id: "failed-2",
          artifact_status: "failed",
          metadata: {
            retryable: false,
            recovery_mode: "none",
            launch_payload: {
              strategy_type: "buy_and_hold",
              symbols: ["MSFT"],
            },
          },
        },
      }),
    ).toBeNull();

    expect(
      failedActionRetryActionFromMetadata({
        failed_action: {
          artifact_id: "failed-3",
          retryable: true,
        },
      }),
    ).toBeNull();
  });

  test("hydrates from legacy fallback failed_action metadata without prose matching", () => {
    const action = failedActionRetryActionFromMetadata({
      failed_action: {
        artifact_id: "failed-legacy",
        artifact_status: "failed",
        retryable: true,
        launch_payload: {
          strategy_type: "dca_accumulation",
          symbols: ["NVDA"],
        },
      },
    });

    expect(action?.artifactId).toBe("failed-legacy");
    expect(action?.artifactType).toBe("failed_action");
    expect(action?.type).toBe("retry_failed_action");
    expect(action?.value).toBe("Retry");
  });

  test("does not hydrate retryable failed-action metadata without an artifact id", () => {
    const metadata = {
      failed_action: {
        artifact_status: "failed",
        retryable: true,
        launch_payload: {
          strategy_type: "dca_accumulation",
          symbols: ["NVDA"],
        },
      },
    };

    expect(failedActionRetryActionFromMetadata(metadata)).toBeNull();
    expect(hasFailedActionMetadata(metadata)).toBe(true);
  });

  test("does not treat unrelated metadata as a failed action", () => {
    expect(hasFailedActionMetadata({ stage_outcome: "needs_clarification" })).toBe(
      false,
    );
  });

  test("hydrates a local retry action for a failed user turn without backend payload", () => {
    const action = retryLastTurnActionFromMessage(
      " what if I bought $125 of BTC every two weeks in 2022? ",
      { assistantMessageId: "assistant-failed-1" },
    );

    expect(action).toEqual({
      id: "retry-last-turn",
      label: "Retry",
      labelKey: "common.retry",
      value: "Retry",
      type: "retry_last_turn",
      payload: {
        message: "what if I bought $125 of BTC every two weeks in 2022?",
        failed_assistant_id: "assistant-failed-1",
      },
    });
    expect(retryLastTurnMessageFromAction(action)).toBe(
      "what if I bought $125 of BTC every two weeks in 2022?",
    );
  });

  test("hydrates a retry-last-turn action from persisted failure metadata", () => {
    const action = retryLastTurnActionFromMetadata(
      {
        retry_last_turn: {
          message: "what if I bought $125 of BTC every two weeks in 2022?",
        },
      },
      { assistantMessageId: "assistant-failed-persisted" },
    );

    expect(action).toEqual({
      id: "retry-last-turn",
      label: "Retry",
      labelKey: "common.retry",
      value: "Retry",
      type: "retry_last_turn",
      payload: {
        message: "what if I bought $125 of BTC every two weeks in 2022?",
        failed_assistant_id: "assistant-failed-persisted",
      },
    });
  });

  test("keys the retry action by the persisted request_message_id", () => {
    // #240: the stable retry action is keyed by request_message_id from the
    // abandoned-turn overlay, never derived from display prose.
    const action = retryLastTurnActionFromMetadata({
      retry_last_turn: {
        request_message_id: "user-turn-1",
        message: "test AAPL momentum",
        action: {
          type: "show_breakdown",
          label: "Show breakdown",
          payload: { run_id: "run-77" },
        },
      },
    });

    expect(action?.payload?.request_message_id).toBe("user-turn-1");
    expect(action?.payload?.message).toBe("test AAPL momentum");
    expect(retryLastTurnChatActionFromAction(action)).toEqual({
      type: "show_breakdown",
      label: "Show breakdown",
      payload: { run_id: "run-77" },
    });
  });

  test("preserves a typed chat action for finalization retry", () => {
    const action = retryLastTurnActionFromMetadata(
      {
        retry_last_turn: {
          message: "run backtest",
          action: {
            type: "run_backtest",
            label: "Run backtest",
            payload: { confirmation_id: "confirmation-1" },
            presentation: "confirmation",
          },
        },
      },
      { assistantMessageId: "assistant-finalization-failed" },
    );

    expect(retryLastTurnChatActionFromAction(action)).toEqual({
      type: "run_backtest",
      label: "Run backtest",
      payload: { confirmation_id: "confirmation-1" },
      presentation: "confirmation",
    });
  });

  test("does not hydrate retry-last-turn from malformed persisted metadata", () => {
    expect(retryLastTurnActionFromMetadata({ retry_last_turn: {} })).toBeNull();
    expect(
      retryLastTurnActionFromMetadata({
        retry_last_turn: { message: "   " },
      }),
    ).toBeNull();
  });

  test("does not hydrate a retry-last-turn action from empty input", () => {
    expect(retryLastTurnActionFromMessage("   ")).toBeNull();
  });

  test("hydrates a structured retry action for conversation load failures", () => {
    const action = conversationLoadRetryActionFromConversationId(
      " conversation-load-1 ",
    );

    expect(action).toEqual({
      id: "retry-load-conversation",
      label: "Retry",
      labelKey: "common.retry",
      value: "Retry",
      type: "retry_load_conversation",
      payload: {
        conversation_id: "conversation-load-1",
      },
    });
    expect(retryLoadConversationIdFromAction(action)).toBe("conversation-load-1");
    expect(isRetryAction(action)).toBe(true);
  });

  test("does not hydrate a conversation-load retry without a conversation id", () => {
    expect(conversationLoadRetryActionFromConversationId("  ")).toBeNull();
    expect(retryLoadConversationIdFromAction(undefined)).toBeNull();
  });
});
