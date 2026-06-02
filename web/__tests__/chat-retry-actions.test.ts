import { describe, expect, test } from "bun:test";

import {
  failedActionRetryActionFromMetadata,
  hasFailedActionMetadata,
  retryLastTurnActionFromMessage,
  retryLastTurnMessageFromAction,
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

  test("does not hydrate a retry-last-turn action from empty input", () => {
    expect(retryLastTurnActionFromMessage("   ")).toBeNull();
  });
});
