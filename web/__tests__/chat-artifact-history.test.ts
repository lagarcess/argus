import { describe, expect, test } from "bun:test";

import {
  applyConfirmationActionEffects,
  applyConsumedResultActions,
  consumeResultActionOnMessages,
  confirmationActionEffectsFromApi,
  consumedResultActionsFromApi,
  normalizeConfirmationHistory,
  settleConfirmationAfterActionTransportError,
  settleOpenConfirmationsAfterStreamError,
  settleOpenConfirmationsAfterTextFinal,
} from "../components/chat/artifact-history";
import type { ChatActionOption, Message } from "../components/chat/types";
import type { ApiMessage } from "../lib/argus-api";
import { hydrateTextMessageFromApi } from "../lib/chat-message-hydration";
import { normalizeRetryActionHistory } from "../lib/chat-retry-action-history";

type ConfirmationActionType = Extract<
  ChatActionOption["type"],
  | "run_backtest"
  | "change_dates"
  | "change_asset"
  | "adjust_assumptions"
  | "cancel_confirmation"
>;

type ConfirmationTerminalState = "cancelled" | "superseded";

function confirmationMessage(): Message {
  return {
    id: "assistant-confirmation",
    role: "ai",
    kind: "strategy_confirmation",
    confirmation: {
      confirmation_id: "confirm-aapl",
      confirmation_state: "active",
      title: "AAPL buy and hold",
      statusLabel: "Ready to run",
      summary: "I read this as AAPL using a buy and hold approach.",
      rows: [{ label: "Assets", value: "AAPL" }],
      actions: [
        {
          type: "run_backtest",
          label: "Run backtest",
          presentation: "confirmation",
          payload: { confirmation_id: "confirm-aapl" },
        },
        {
          type: "cancel_confirmation",
          label: "Cancel",
          presentation: "confirmation",
          payload: { confirmation_id: "confirm-aapl" },
        },
      ],
    },
    actions: [
      {
        type: "run_backtest",
        label: "Run backtest",
        presentation: "confirmation",
        payload: { confirmation_id: "confirm-aapl" },
      },
    ],
  };
}

function resultMessage(runId: string): Message {
  return {
    id: `assistant-result-${runId}`,
    role: "ai",
    kind: "strategy_result",
    result: {
      strategyName: "AAPL buy and hold",
      period: "past year",
      runId,
      metrics: [],
      actions: [
        {
          type: "show_breakdown",
          label: "Explain result",
          presentation: "result",
          payload: { run_id: runId, conversation_id: "conversation-1" },
        },
      ],
    },
    actions: [
      {
        type: "show_breakdown",
        label: "Explain result",
        presentation: "result",
        payload: { run_id: runId, conversation_id: "conversation-1" },
      },
    ],
  };
}

function resultMessageWithResultActions(runId: string): Message {
  const actions = [
    {
      type: "show_breakdown",
      label: "Explain result",
      presentation: "result",
      payload: { run_id: runId, conversation_id: "conversation-1" },
    },
    {
      type: "refine_strategy",
      label: "Refine idea",
      presentation: "result",
      payload: { run_id: runId, conversation_id: "conversation-1" },
    },
  ] satisfies Message["actions"];

  return {
    id: `assistant-result-actions-${runId}`,
    role: "ai",
    kind: "strategy_result",
    result: {
      strategyName: "AAPL buy and hold",
      period: "past year",
      runId,
      metrics: [],
      actions,
    },
    actions,
  };
}

describe("chat artifact history", () => {
  test.each([
    ["run_backtest", "Running", "superseded"],
    ["change_dates", "Editing", "superseded"],
    ["change_asset", "Editing", "superseded"],
    ["adjust_assumptions", "Editing", "superseded"],
    ["cancel_confirmation", "Draft canceled", "cancelled"],
  ] satisfies readonly [
    ConfirmationActionType,
    string,
    ConfirmationTerminalState,
  ][])(
    "%s closes active confirmation cards with the expected state",
    (
      type: ConfirmationActionType,
      statusLabel: string,
      confirmationState: ConfirmationTerminalState,
    ) => {
      const [message] = applyConfirmationActionEffects([confirmationMessage()], [
        {
          type,
          confirmationId: "confirm-aapl",
          statusLabel,
        },
      ]);

      expect(message.confirmation?.confirmation_state).toBe(confirmationState);
      expect(message.confirmation?.status).toBe(
        type === "run_backtest"
          ? "running"
          : type === "cancel_confirmation"
            ? "draft_canceled"
            : "editing",
      );
      expect(message.confirmation?.statusLabel).toBe(statusLabel);
      expect(message.confirmation?.actions).toEqual([]);
      expect(message.actions).toEqual([]);
    },
  );

  test("cancel confirmation becomes a durable non-runnable card state", () => {
    const [message] = applyConfirmationActionEffects([confirmationMessage()], [
      {
        type: "cancel_confirmation",
        confirmationId: "confirm-aapl",
        statusLabel: "Draft canceled",
      },
    ]);

    expect(message.confirmation?.confirmation_state).toBe("cancelled");
    expect(message.confirmation?.status).toBe("draft_canceled");
    expect(message.confirmation?.statusLabel).toBe("Draft canceled");
    expect(message.confirmation?.actions).toEqual([]);
    expect(message.actions).toEqual([]);
  });

  test("stream errors settle running confirmation cards as failed", () => {
    const action: ChatActionOption = {
      type: "run_backtest",
      label: "Run backtest",
      presentation: "confirmation",
      payload: { confirmation_id: "confirm-aapl" },
    };
    const [running] = applyConfirmationActionEffects([confirmationMessage()], [
      {
        type: "run_backtest",
        confirmationId: "confirm-aapl",
        statusLabel: "Running",
      },
    ]);

    const [settled] = settleOpenConfirmationsAfterStreamError([running], action);

    expect(settled.confirmation?.confirmation_state).toBe("superseded");
    expect(settled.confirmation?.status).toBe("could_not_run");
    expect(settled.confirmation?.statusLabel).toBe("Could not run");
    expect(settled.confirmation?.actions).toEqual([]);
    expect(settled.actions).toEqual([]);
  });

  test("action transport errors settle only the action-owned confirmation", () => {
    const previousCard: Message = {
      ...confirmationMessage(),
      id: "previous-confirmation",
      confirmation: {
        ...confirmationMessage().confirmation!,
        confirmation_id: "confirm-previous-aapl",
        confirmation_state: "superseded",
        status: "updated",
        statusLabel: "Updated",
        actions: [],
      },
      actions: [],
    };
    const [running] = applyConfirmationActionEffects([confirmationMessage()], [
      {
        type: "run_backtest",
        confirmationId: "confirm-aapl",
        statusLabel: "Running",
      },
    ]);

    const messages = settleConfirmationAfterActionTransportError(
      [previousCard, running],
      {
        type: "run_backtest",
        label: "Run backtest",
        presentation: "confirmation",
        payload: { confirmation_id: "confirm-aapl" },
      },
    );

    expect(messages[0].confirmation?.confirmation_state).toBe("superseded");
    expect(messages[0].confirmation?.statusLabel).toBe("Updated");
    expect(messages[1].confirmation?.confirmation_state).toBe("superseded");
    expect(messages[1].confirmation?.status).toBe("could_not_run");
    expect(messages[1].confirmation?.statusLabel).toBe("Could not run");
    expect(messages[1].confirmation?.actions).toEqual([]);
    expect(messages[1].actions).toEqual([]);
  });

  test("cancel action tombstones hide action transcript noise on reload", () => {
    const items: ApiMessage[] = [
      {
        id: "user-action",
        conversation_id: "conversation-1",
        role: "user",
        content: "Cancel",
        created_at: "2026-05-15T00:00:00Z",
        metadata: {
          chat_action: {
            type: "cancel_confirmation",
            label: "Cancel",
            presentation: "confirmation",
            payload: { confirmation_id: "confirm-aapl" },
          },
        },
      },
      {
        id: "assistant-tombstone",
        conversation_id: "conversation-1",
        role: "assistant",
        content: "",
        created_at: "2026-05-15T00:00:01Z",
        metadata: {
          chat_action: {
            type: "cancel_confirmation",
            label: "Cancel",
            presentation: "confirmation",
            payload: { confirmation_id: "confirm-aapl" },
          },
          artifact_event: {
            type: "confirmation_cancelled",
            confirmation_id: "confirm-aapl",
          },
        },
      },
    ];

    const effects = confirmationActionEffectsFromApi(items);

    expect(effects.effects).toEqual([
      {
        type: "cancel_confirmation",
        confirmationId: "confirm-aapl",
        status: "draft_canceled",
        statusLabel: "Draft canceled",
      },
      {
        type: "cancel_confirmation",
        confirmationId: "confirm-aapl",
        status: "draft_canceled",
        statusLabel: "Draft canceled",
      },
    ]);
    expect([...effects.hiddenMessageIds]).toEqual([
      "user-action",
      "assistant-tombstone",
    ]);
  });

  test("stale confirmation action recovery does not mutate card history", () => {
    const items: ApiMessage[] = [
      {
        id: "assistant-recovery",
        conversation_id: "conversation-1",
        role: "assistant",
        content: "That confirmation was updated. Use the latest card action before continuing.",
        created_at: "2026-05-15T00:00:01Z",
        metadata: {
          recovery_reason: "missing_confirmation_checkpoint",
          chat_action: {
            type: "cancel_confirmation",
            label: "Cancel",
            presentation: "confirmation",
            payload: { confirmation_id: "confirm-aapl" },
          },
        },
      },
    ];

    const effects = confirmationActionEffectsFromApi(items);

    expect(effects.effects).toEqual([]);
    expect([...effects.hiddenMessageIds]).toEqual([]);
  });

  test("transient edit actions do not reopen superseded cards during hydration", () => {
    const previousCard: Message = {
      ...confirmationMessage(),
      id: "previous-confirmation",
      confirmation: {
        ...confirmationMessage().confirmation!,
        confirmation_state: "superseded",
        statusLabel: "Updated",
        actions: [],
      },
      actions: [],
    };
    const latestCard: Message = {
      ...confirmationMessage(),
      id: "latest-confirmation",
      confirmation: {
        ...confirmationMessage().confirmation!,
        confirmation_id: "confirm-updated-aapl",
      },
    };

    const messages = applyConfirmationActionEffects([previousCard, latestCard], [
      {
        type: "change_dates",
        confirmationId: "confirm-aapl",
        statusLabel: "Editing",
      },
      {
        type: "cancel_confirmation",
        confirmationId: "confirm-updated-aapl",
        statusLabel: "Draft canceled",
      },
    ]);

    expect(messages[0].confirmation?.confirmation_state).toBe("superseded");
    expect(messages[0].confirmation?.statusLabel).toBe("Updated");
    expect(messages[1].confirmation?.confirmation_state).toBe("cancelled");
    expect(messages[1].confirmation?.status).toBe("draft_canceled");
    expect(messages[1].confirmation?.statusLabel).toBe("Draft canceled");
  });

  test("cancel wins over earlier transient effects for the same active card", () => {
    const [message] = applyConfirmationActionEffects([confirmationMessage()], [
      {
        type: "change_dates",
        confirmationId: "confirm-aapl",
        statusLabel: "Editing",
      },
      {
        type: "cancel_confirmation",
        confirmationId: "confirm-aapl",
        statusLabel: "Draft canceled",
      },
    ]);

    expect(message.confirmation?.confirmation_state).toBe("cancelled");
    expect(message.confirmation?.status).toBe("draft_canceled");
    expect(message.confirmation?.statusLabel).toBe("Draft canceled");
    expect(message.confirmation?.actions).toEqual([]);
  });

  test("normalization preserves cancelled confirmation state after reload", () => {
    const [cancelled] = applyConfirmationActionEffects([confirmationMessage()], [
      {
        type: "cancel_confirmation",
        confirmationId: "confirm-aapl",
        statusLabel: "Draft canceled",
      },
    ]);

    const [normalized] = normalizeConfirmationHistory([cancelled]);

    expect(normalized.confirmation?.confirmation_state).toBe("cancelled");
    expect(normalized.confirmation?.status).toBe("draft_canceled");
    expect(normalized.confirmation?.statusLabel).toBe("Draft canceled");
    expect(normalized.confirmation?.actions).toEqual([]);
    expect(normalized.actions).toEqual([]);
  });

  test("normalization marks a run action complete once the result card exists", () => {
    const [running] = applyConfirmationActionEffects([confirmationMessage()], [
      {
        type: "run_backtest",
        confirmationId: "confirm-aapl",
        statusLabel: "Running",
      },
    ]);
    const result: Message = {
      id: "assistant-result",
      role: "ai",
      kind: "strategy_result",
      result: {
        strategyName: "AAPL buy and hold",
        period: "past year",
        metrics: [],
      },
    };

    const [normalizedConfirmation] = normalizeConfirmationHistory([running, result]);

    expect(normalizedConfirmation.confirmation?.confirmation_state).toBe("superseded");
    expect(normalizedConfirmation.confirmation?.status).toBe("run_complete");
    expect(normalizedConfirmation.confirmation?.statusLabel).toBe("Run complete");
    expect(normalizedConfirmation.confirmation?.actions).toEqual([]);
    expect(normalizedConfirmation.actions).toEqual([]);
  });

  test("normalization closes active run-complete confirmations with stale actions", () => {
    const activeComplete: Message = {
      ...confirmationMessage(),
      confirmation: {
        ...confirmationMessage().confirmation!,
        confirmation_state: "active",
        status: "run_complete",
        statusLabel: "Run complete",
      },
    };
    const result: Message = {
      id: "assistant-result",
      role: "ai",
      kind: "strategy_result",
      result: {
        strategyName: "AAPL buy and hold",
        period: "past year",
        metrics: [],
      },
    };

    const [normalizedConfirmation] = normalizeConfirmationHistory([
      activeComplete,
      result,
    ]);

    expect(normalizedConfirmation.confirmation?.confirmation_state).toBe("superseded");
    expect(normalizedConfirmation.confirmation?.status).toBe("run_complete");
    expect(normalizedConfirmation.confirmation?.statusLabel).toBe("Run complete");
    expect(normalizedConfirmation.confirmation?.actions).toEqual([]);
    expect(normalizedConfirmation.actions).toEqual([]);
  });

  test("normalization treats active run-complete status as terminal without waiting for a result", () => {
    const activeComplete: Message = {
      ...confirmationMessage(),
      confirmation: {
        ...confirmationMessage().confirmation!,
        confirmation_state: "active",
        status: "run_complete",
        statusLabel: "Run complete",
      },
    };

    const [normalizedConfirmation] = normalizeConfirmationHistory([activeComplete]);

    expect(normalizedConfirmation.confirmation?.confirmation_state).toBe("superseded");
    expect(normalizedConfirmation.confirmation?.status).toBe("run_complete");
    expect(normalizedConfirmation.confirmation?.statusLabel).toBe("Run complete");
    expect(normalizedConfirmation.confirmation?.actions).toEqual([]);
    expect(normalizedConfirmation.actions).toEqual([]);
  });

  test("failed run finalization does not leave confirmation status running", () => {
    const [running] = applyConfirmationActionEffects([confirmationMessage()], [
      {
        type: "run_backtest",
        confirmationId: "confirm-aapl",
        statusLabel: "Running",
      },
    ]);

    const [settled] = settleOpenConfirmationsAfterTextFinal([running], {
      action: {
        type: "run_backtest",
        label: "Run backtest",
        presentation: "confirmation",
        payload: { confirmation_id: "confirm-aapl" },
      },
      finalActions: [
        {
          type: "retry_failed_action",
          artifactType: "failed_action",
          artifactStatus: "failed",
          label: "Retry",
        },
      ],
    });

    expect(settled.confirmation?.confirmation_state).toBe("superseded");
    expect(settled.confirmation?.statusLabel).toBe("Could not run");
    expect(settled.confirmation?.actions).toEqual([]);
    expect(settled.actions).toEqual([]);
  });

  test("non-retryable failed run finalization still settles confirmation as failed", () => {
    const [running] = applyConfirmationActionEffects([confirmationMessage()], [
      {
        type: "run_backtest",
        confirmationId: "confirm-aapl",
        statusLabel: "Running",
      },
    ]);

    const [settled] = settleOpenConfirmationsAfterTextFinal([running], {
      action: {
        type: "run_backtest",
        label: "Run backtest",
        presentation: "confirmation",
        payload: { confirmation_id: "confirm-aapl" },
      },
      hasFailedAction: true,
      finalActions: [],
    });

    expect(settled.confirmation?.confirmation_state).toBe("superseded");
    expect(settled.confirmation?.statusLabel).toBe("Could not run");
    expect(settled.confirmation?.actions).toEqual([]);
    expect(settled.actions).toEqual([]);
  });

  test("clarification text finals keep active confirmation cards open", () => {
    const [settled] = settleOpenConfirmationsAfterTextFinal(
      [confirmationMessage()],
      {
        stageOutcome: "needs_clarification",
      },
    );

    expect(settled.confirmation?.confirmation_state).toBe("active");
    expect(settled.confirmation?.statusLabel).toBe("Ready to run");
    expect(settled.confirmation?.actions?.length).toBeGreaterThan(0);
    expect(settled.actions?.length).toBeGreaterThan(0);
  });

  test("hydration closes active confirmation as complete when a result follows it", () => {
    const result: Message = {
      id: "assistant-result",
      role: "ai",
      kind: "strategy_result",
      result: {
        strategyName: "AAPL buy and hold",
        period: "past year",
        metrics: [],
      },
    };

    const [normalizedConfirmation] = normalizeConfirmationHistory([
      confirmationMessage(),
      result,
    ]);

    expect(normalizedConfirmation.confirmation?.confirmation_state).toBe("superseded");
    expect(normalizedConfirmation.confirmation?.statusLabel).toBe("Run complete");
    expect(normalizedConfirmation.confirmation?.actions).toEqual([]);
    expect(normalizedConfirmation.actions).toEqual([]);
  });

  test("hydration preserves unmarked stale failure text while stripping retry", () => {
    const messages = normalizeRetryActionHistory([
      {
        id: "assistant-failed",
        role: "ai",
        kind: "text",
        content: "Something went wrong. Your conversation is saved. Please try again.",
        actions: [
          {
            id: "retry-last-turn",
            label: "Retry",
            type: "retry_last_turn",
            payload: {
              message:
                "Backtest buy and hold AAPL from January 2025 through June 2026",
              failed_assistant_id: "assistant-failed",
            },
          },
        ],
      },
      resultMessage("run-aapl"),
    ]);

    const failedMessage = messages.find(
      (message) => message.id === "assistant-failed",
    );
    expect(failedMessage).toBeDefined();
    expect(failedMessage?.actions).toBeUndefined();
    expect(messages).toHaveLength(2);
    expect(messages[1].kind).toBe("strategy_result");
  });

  test("hydration removes backend-superseded runtime failure text", () => {
    const failedMessage = hydrateTextMessageFromApi({
      id: "assistant-failed",
      conversation_id: "conversation-aapl",
      role: "assistant",
      content: "Something went wrong. Your conversation is saved. Please try again.",
      created_at: "2026-06-01T00:00:00Z",
      metadata: {
        conversation_mode: "recovery",
        agent_runtime_stage_outcome: "agent_runtime_failure",
        agent_runtime_failure_superseded: true,
        recovery: {
          code: "runtime_failure",
          retryable: false,
          language: "en",
        },
      },
    });
    const messages = normalizeRetryActionHistory([
      failedMessage,
      resultMessage("run-aapl"),
    ]);

    expect(messages.find((message) => message.id === "assistant-failed")).toBe(
      undefined,
    );
    expect(messages).toHaveLength(1);
    expect(messages[0].kind).toBe("strategy_result");
  });

  test("specific action effects beat broad fallback effects during hydration", () => {
    const [message] = applyConfirmationActionEffects([confirmationMessage()], [
      {
        type: "change_asset",
        statusLabel: "Editing",
      },
      {
        type: "cancel_confirmation",
        confirmationId: "confirm-aapl",
        statusLabel: "Draft canceled",
      },
    ]);

    expect(message.confirmation?.confirmation_state).toBe("cancelled");
    expect(message.confirmation?.statusLabel).toBe("Draft canceled");
  });

  test("breakdown action metadata without canonical run id does not consume result actions", () => {
    const items: ApiMessage[] = [
      {
        id: "assistant-breakdown",
        conversation_id: "conversation-1",
        role: "assistant",
        content: "I could not find the completed backtest to explain.",
        created_at: "2026-05-15T00:00:01Z",
        metadata: {
          chat_action: {
            type: "show_breakdown",
            label: "Explain result",
            presentation: "result",
            payload: {},
          },
          result_breakdown_source: "missing_result",
        },
      },
    ];

    const consumedActions = consumedResultActionsFromApi(items);
    const messages = applyConsumedResultActions(
      [resultMessage("run-a"), resultMessage("run-b")],
      consumedActions,
    );

    expect(consumedActions).toEqual([]);
    expect(messages[0].result?.actions?.map((action) => action.type)).toEqual([
      "show_breakdown",
    ]);
    expect(messages[1].result?.actions?.map((action) => action.type)).toEqual([
      "show_breakdown",
    ]);
  });

  test("optimistic breakdown action without canonical run id does not consume result actions", () => {
    const messages = consumeResultActionOnMessages(
      [resultMessage("run-a"), resultMessage("run-b")],
      {
        type: "show_breakdown",
        label: "Explain result",
        presentation: "result",
        payload: {},
      },
    );

    expect(messages[0].result?.actions?.map((action) => action.type)).toEqual([
      "show_breakdown",
    ]);
    expect(messages[1].result?.actions?.map((action) => action.type)).toEqual([
      "show_breakdown",
    ]);
  });

  test("refine action metadata consumes only the source result refine action", () => {
    const items: ApiMessage[] = [
      {
        id: "assistant-refine",
        conversation_id: "conversation-1",
        role: "assistant",
        content: "What would you like to change next for AAPL?",
        created_at: "2026-05-15T00:00:01Z",
        metadata: {
          chat_action: {
            type: "refine_strategy",
            label: "Refine idea",
            presentation: "result",
            payload: { run_id: "run-a", conversation_id: "conversation-1" },
          },
          pending_strategy: {
            requested_field: "refinement",
            source_result: {
              run_id: "run-a",
              conversation_id: "conversation-1",
            },
          },
          source_result_run_id: "run-a",
        },
      },
    ];

    const messages = applyConsumedResultActions(
      [
        resultMessageWithResultActions("run-a"),
        resultMessageWithResultActions("run-b"),
      ],
      consumedResultActionsFromApi(items),
    );

    expect(messages[0].result?.actions?.map((action) => action.type)).toEqual([
      "show_breakdown",
    ]);
    expect(messages[1].result?.actions?.map((action) => action.type)).toEqual([
      "show_breakdown",
      "refine_strategy",
    ]);
  });

  test("optimistic refine action consumes only the matching result refine action", () => {
    const messages = consumeResultActionOnMessages(
      [
        resultMessageWithResultActions("run-a"),
        resultMessageWithResultActions("run-b"),
      ],
      {
        type: "refine_strategy",
        label: "Refine idea",
        presentation: "result",
        payload: { run_id: "run-a", conversation_id: "conversation-1" },
      },
    );

    expect(messages[0].result?.actions?.map((action) => action.type)).toEqual([
      "show_breakdown",
    ]);
    expect(messages[1].result?.actions?.map((action) => action.type)).toEqual([
      "show_breakdown",
      "refine_strategy",
    ]);
  });
});
