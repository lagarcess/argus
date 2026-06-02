import type { ApiMessage } from "@/lib/argus-api";
import type { ChatActionOption, Message } from "./types";

export type ConfirmationActionEffect = {
  type: NonNullable<ChatActionOption["type"]>;
  confirmationId?: string;
  statusLabel: string;
};

export type ConsumedResultAction = {
  type: "show_breakdown" | "save_strategy";
  runId?: string;
  savedStrategyId?: string | null;
};

const CONFIRMATION_ACTION_TYPES = new Set<NonNullable<ChatActionOption["type"]>>([
  "run_backtest",
  "change_dates",
  "change_asset",
  "adjust_assumptions",
  "cancel_confirmation",
]);

export function confirmationActionStatusLabel(
  actionOrType: ChatActionOption | NonNullable<ChatActionOption["type"]> | undefined,
) {
  const type = typeof actionOrType === "string" ? actionOrType : actionOrType?.type;
  if (type === "cancel_confirmation") {
    return "Draft canceled";
  }
  if (type === "run_backtest") {
    return "Running";
  }
  if (
    type === "change_dates" ||
    type === "change_asset" ||
    type === "adjust_assumptions"
  ) {
    return "Editing";
  }
  return "Updated";
}

function completedRunConfirmationStatusLabel(message: Message, index: number, lastResultIndex: number) {
  if (
    index < lastResultIndex &&
    message.confirmation?.confirmation_state === "superseded" &&
    message.confirmation.statusLabel === "Running"
  ) {
    return "Run complete";
  }
  return message.confirmation?.statusLabel ?? (index < lastResultIndex ? "Run complete" : "Updated");
}

export function confirmationActionEffectFromAction(
  action: ChatActionOption | undefined,
): ConfirmationActionEffect | null {
  if (!action?.type || !CONFIRMATION_ACTION_TYPES.has(action.type)) {
    return null;
  }
  return {
    type: action.type,
    confirmationId: confirmationIdFromAction(action),
    statusLabel: confirmationActionStatusLabel(action),
  };
}

export function confirmationActionEffectsFromApi(items: ApiMessage[]) {
  const effects: ConfirmationActionEffect[] = [];
  const hiddenMessageIds = new Set<string>();
  for (const item of items) {
    const metadata = item.metadata ?? {};
    if (metadata.recovery_reason) {
      continue;
    }
    const action = chatActionFromMetadata(metadata);
    const effect = confirmationActionEffectFromAction(action);
    if (!effect) {
      continue;
    }
    effects.push(effect);
    if (effect.type === "cancel_confirmation") {
      hiddenMessageIds.add(item.id);
    }
  }
  return { effects, hiddenMessageIds };
}

export function isBreakdownActionMetadata(metadata: Record<string, unknown>) {
  const chatAction = metadata.chat_action;
  return (
    typeof chatAction === "object" &&
    chatAction !== null &&
    "type" in chatAction &&
    chatAction.type === "show_breakdown"
  );
}

export function isSaveActionMetadata(metadata: Record<string, unknown>) {
  const chatAction = metadata.chat_action;
  return (
    typeof chatAction === "object" &&
    chatAction !== null &&
    "type" in chatAction &&
    chatAction.type === "save_strategy"
  );
}

export function resultActionRunId(action: ChatActionOption | undefined) {
  const rawRunId = action?.payload?.run_id ?? action?.payload?.runId;
  return typeof rawRunId === "string" && rawRunId.trim() ? rawRunId.trim() : undefined;
}

export function consumedResultActionsFromApi(items: ApiMessage[]): ConsumedResultAction[] {
  return items.flatMap((message): ConsumedResultAction[] => {
    const metadata = message.metadata ?? {};
    const action = chatActionFromMetadata(metadata);
    if (isBreakdownActionMetadata(metadata)) {
      return [{ type: "show_breakdown", runId: resultActionRunId(action) }];
    }
    if (message.role === "assistant" && isSaveActionMetadata(metadata)) {
      const savedStrategyId = savedStrategyIdFromMetadata(metadata);
      if (!savedStrategyId) {
        return [];
      }
      return [
        {
          type: "save_strategy",
          runId: stringOrNull(metadata.result_run_id) ?? resultActionRunId(action),
          savedStrategyId,
        },
      ];
    }
    return [];
  });
}

export function hiddenSaveActionMessageIdsFromApi(items: ApiMessage[]) {
  const hiddenIds = new Set<string>();
  items.forEach((message, index) => {
    const metadata = message.metadata ?? {};
    if (message.role !== "assistant" || !isSaveActionMetadata(metadata)) {
      return;
    }
    if (!savedStrategyIdFromMetadata(metadata)) {
      return;
    }
    const action = chatActionFromMetadata(metadata);
    const runId = stringOrNull(metadata.result_run_id) ?? resultActionRunId(action);
    hiddenIds.add(message.id);
    for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
      const candidate = items[cursor];
      const candidateMetadata = candidate.metadata ?? {};
      if (candidate.role !== "user" || !isSaveActionMetadata(candidateMetadata)) {
        continue;
      }
      const candidateAction = chatActionFromMetadata(candidateMetadata);
      if (!runId || resultActionRunId(candidateAction) === runId) {
        hiddenIds.add(candidate.id);
        return;
      }
    }
  });
  return hiddenIds;
}

export function applyConfirmationActionEffects(
  messages: Message[],
  effects: ConfirmationActionEffect[],
): Message[] {
  if (effects.length === 0) {
    return messages;
  }
  const lastResultIndex = messages.reduce(
    (latest, message, index) =>
      message.kind === "strategy_result" ? index : latest,
    -1,
  );
  return messages.map((message, index) => {
    if (
      message.kind !== "strategy_confirmation" ||
      !message.confirmation ||
      index < lastResultIndex
    ) {
      return message;
    }
    const confirmationId = message.confirmation.confirmation_id;
    if (
      message.confirmation.confirmation_state &&
      message.confirmation.confirmation_state !== "active"
    ) {
      return message;
    }
    const effect = strongestEffectForConfirmation(confirmationId, effects);
    if (!effect) {
      return message;
    }
    return closeConfirmationForAction(message, effect);
  });
}

export function applyConsumedResultActions(
  messages: Message[],
  consumedActions: ConsumedResultAction[],
): Message[] {
  if (consumedActions.length === 0) {
    return messages;
  }
  return messages.map((message) => {
    if (message.kind !== "strategy_result" || !message.result) {
      return message;
    }
    const resultRunId = message.result.runId;
    const savedEffect = consumedActions.find(
      (consumed) =>
        consumed.type === "save_strategy" &&
        (!consumed.runId || consumed.runId === resultRunId),
    );
    const savedStrategyId = savedEffect?.savedStrategyId ?? message.savedStrategyId ?? null;
    const resultActions = (message.result.actions ?? []).filter(
      (action) => !resultActionWasConsumed(action, resultRunId, consumedActions),
    );
    const messageActions = (message.actions ?? []).filter(
      (action) => !resultActionWasConsumed(action, resultRunId, consumedActions),
    );
    return {
      ...message,
      savedStrategyId,
      actions: messageActions,
      result: {
        ...message.result,
        savedStrategyId,
        strategyId: message.result.strategyId ?? savedStrategyId,
        actions: resultActions,
      },
    };
  });
}

export function consumeResultActionOnMessages(
  messages: Message[],
  action: ChatActionOption | undefined,
): Message[] {
  if (action?.type !== "show_breakdown") {
    return messages;
  }
  return applyConsumedResultActions(messages, [
    { type: "show_breakdown", runId: resultActionRunId(action) },
  ]);
}

export function normalizeConfirmationHistory(messages: Message[]): Message[] {
  const lastResultIndex = messages.reduce(
    (latest, message, index) =>
      message.kind === "strategy_result" ? index : latest,
    -1,
  );
  const latestConfirmationIndex = messages.reduce(
    (latest, message, index) =>
      message.kind === "strategy_confirmation" &&
      !isTerminalConfirmation(message) &&
      index > lastResultIndex
        ? index
        : latest,
    -1,
  );
  return messages.map((message, index) => {
    if (message.kind !== "strategy_confirmation" || !message.confirmation) {
      return message;
    }
    if (isTerminalConfirmation(message)) {
      return {
        ...message,
        confirmation: {
          ...message.confirmation,
          statusLabel: completedRunConfirmationStatusLabel(message, index, lastResultIndex),
          actions: [],
        },
        actions: [],
      };
    }
    const shouldSupersede =
      index < lastResultIndex ||
      (latestConfirmationIndex >= 0 && index !== latestConfirmationIndex);
    if (!shouldSupersede) {
      return {
        ...message,
        confirmation: {
          ...message.confirmation,
          confirmation_state: "active",
        },
        actions: message.confirmation.actions ?? message.actions,
      };
    }
    return supersedePriorConfirmations(
      message,
      index < lastResultIndex ? "Run complete" : "Updated",
    );
  });
}

export function supersedePriorConfirmations(
  message: Message,
  statusLabel = "Updated",
): Message {
  if (message.kind !== "strategy_confirmation" || !message.confirmation) {
    return message;
  }
  return {
    ...message,
    confirmation: {
      ...message.confirmation,
      confirmation_state: "superseded",
      statusLabel,
      actions: [],
    },
    actions: [],
  };
}

export function supersedeOpenConfirmations(
  messages: Message[],
  statusLabel = "Updated",
): Message[] {
  const lastResultIndex = messages.reduce(
    (latest, message, index) =>
      message.kind === "strategy_result" ? index : latest,
    -1,
  );
  return messages.map((message, index) =>
    message.kind === "strategy_confirmation" && index > lastResultIndex
      ? supersedePriorConfirmations(message, statusLabel)
      : message,
  );
}

export function settleOpenConfirmationsAfterTextFinal(
  messages: Message[],
  {
    action,
    finalActions = [],
    hasFailedAction = false,
    stageOutcome,
  }: {
    action?: ChatActionOption;
    finalActions?: ChatActionOption[];
    hasFailedAction?: boolean;
    stageOutcome?: unknown;
  },
): Message[] {
  const hasConfirmationAction = Boolean(confirmationActionEffectFromAction(action));
  const hasFailedActionFinal =
    hasFailedAction || finalActions.some(isFailedActionRetry);
  const hasClarifyingOutcome =
    stageOutcome === "await_user_reply" || stageOutcome === "needs_clarification";

  if (!hasConfirmationAction && !hasFailedActionFinal && !hasClarifyingOutcome) {
    return messages;
  }

  return supersedeOpenConfirmations(
    messages,
    confirmationTextFinalStatusLabel(action, hasFailedActionFinal),
  );
}

function closeConfirmationForAction(
  message: Message,
  effect: ConfirmationActionEffect,
): Message {
  if (message.kind !== "strategy_confirmation" || !message.confirmation) {
    return message;
  }
  return {
    ...message,
    confirmation: {
      ...message.confirmation,
      confirmation_state:
        effect.type === "cancel_confirmation" ? "cancelled" : "superseded",
      statusLabel: effect.statusLabel,
      actions: [],
    },
    actions: [],
  };
}

function strongestEffectForConfirmation(
  confirmationId: string | undefined,
  effects: ConfirmationActionEffect[],
) {
  const matchingEffects = effects.filter(
    (candidate) =>
      !candidate.confirmationId ||
      !confirmationId ||
      candidate.confirmationId === confirmationId,
  );
  if (matchingEffects.length === 0) {
    return null;
  }
  const exactEffects =
    confirmationId === undefined
      ? []
      : matchingEffects.filter(
          (candidate) => candidate.confirmationId === confirmationId,
        );
  const candidates = exactEffects.length > 0 ? exactEffects : matchingEffects;
  return candidates.reduce((strongest, candidate) => {
    const strongestRank = confirmationActionStateRank(strongest.type);
    const candidateRank = confirmationActionStateRank(candidate.type);
    return candidateRank >= strongestRank ? candidate : strongest;
  });
}

function confirmationActionStateRank(
  type: ConfirmationActionEffect["type"],
): number {
  if (type === "cancel_confirmation") {
    return 30;
  }
  if (type === "run_backtest") {
    return 20;
  }
  return 10;
}

function chatActionFromMetadata(
  metadata: Record<string, unknown>,
): ChatActionOption | undefined {
  const chatAction = metadata.chat_action;
  if (typeof chatAction !== "object" || chatAction === null) {
    return undefined;
  }
  return chatAction as ChatActionOption;
}

function confirmationTextFinalStatusLabel(
  action: ChatActionOption | undefined,
  hasFailedAction: boolean,
) {
  if (hasFailedAction) {
    return "Could not run";
  }
  return confirmationActionStatusLabel(action);
}

function isFailedActionRetry(action: ChatActionOption | undefined) {
  return action?.type === "retry_failed_action" || action?.artifactType === "failed_action";
}

function resultActionWasConsumed(
  action: ChatActionOption,
  resultRunId: string | undefined,
  consumedActions: ConsumedResultAction[],
) {
  return consumedActions.some((consumed) => {
    if (consumed.type !== action.type) {
      return false;
    }
    if (!consumed.runId) {
      return true;
    }
    return consumed.runId === resultRunId;
  });
}

function savedStrategyIdFromMetadata(metadata: Record<string, unknown>) {
  return stringOrNull(metadata.saved_strategy_id);
}

function confirmationIdFromAction(action: ChatActionOption) {
  const rawValue = action.payload?.confirmation_id ?? action.payload?.confirmationId;
  return typeof rawValue === "string" && rawValue.trim() ? rawValue.trim() : undefined;
}

function stringOrNull(value: unknown) {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function isTerminalConfirmation(message: Message) {
  return (
    message.kind === "strategy_confirmation" &&
    (message.confirmation?.confirmation_state === "cancelled" ||
      message.confirmation?.confirmation_state === "superseded")
  );
}
