import type { ApiMessage } from "@/lib/argus-api";
import type { ChatActionOption, Message, StrategyConfirmationStatus } from "./types";
import {
  confirmationActionStatus,
  confirmationStatusFromPayload,
  confirmationStatusFromValue,
  confirmationStatusLabel,
} from "./confirmation-display";

export type ConfirmationActionEffect = {
  type: NonNullable<ChatActionOption["type"]>;
  confirmationId?: string;
  status?: StrategyConfirmationStatus;
  statusLabel: string;
};

export type ConsumedResultAction = {
  type: "show_breakdown" | "refine_strategy" | "save_strategy";
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
const IN_PROGRESS_RUN_STATUSES = new Set<StrategyConfirmationStatus>([
  "running",
  "request_sent",
]);
const IN_FLIGHT_ACTION_STATUSES = new Set<StrategyConfirmationStatus>([
  "draft_canceled",
  "editing",
  "request_sent",
  "running",
]);

export function confirmationActionStatusLabel(
  actionOrType: ChatActionOption | NonNullable<ChatActionOption["type"]> | undefined,
) {
  return confirmationStatusLabel(confirmationActionStatus(actionOrType));
}

function completedRunConfirmationStatus(
  message: Message,
  index: number,
  lastResultIndex: number,
): StrategyConfirmationStatus {
  const status = message.confirmation
    ? confirmationStatusFromPayload(message.confirmation)
    : null;
  if (
    index < lastResultIndex &&
    message.confirmation?.confirmation_state === "superseded" &&
    status &&
    IN_PROGRESS_RUN_STATUSES.has(status)
  ) {
    return "run_complete";
  }
  return status ?? (index < lastResultIndex ? "run_complete" : "updated");
}

function completedRunConfirmationStatusLabel(message: Message, index: number, lastResultIndex: number) {
  return confirmationStatusLabel(
    completedRunConfirmationStatus(message, index, lastResultIndex),
  );
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
    status: confirmationActionStatus(action),
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

export function isRefineActionMetadata(metadata: Record<string, unknown>) {
  const chatAction = metadata.chat_action;
  return (
    typeof chatAction === "object" &&
    chatAction !== null &&
    "type" in chatAction &&
    chatAction.type === "refine_strategy"
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
      const runId = resultActionRunId(action);
      return runId ? [{ type: "show_breakdown", runId }] : [];
    }
    if (message.role === "assistant" && isRefineActionMetadata(metadata)) {
      const runId = sourceResultRunIdFromMetadata(metadata) ?? resultActionRunId(action);
      return runId ? [{ type: "refine_strategy", runId }] : [];
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
  if (action?.type !== "show_breakdown" && action?.type !== "refine_strategy") {
    return messages;
  }
  const runId = resultActionRunId(action);
  if (!runId) {
    return messages;
  }
  return applyConsumedResultActions(messages, [
    { type: action.type, runId },
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
          status: completedRunConfirmationStatus(message, index, lastResultIndex),
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
      index < lastResultIndex ? "run_complete" : "updated",
    );
  });
}

export function supersedePriorConfirmations(
  message: Message,
  status: StrategyConfirmationStatus | string = "updated",
): Message {
  if (message.kind !== "strategy_confirmation" || !message.confirmation) {
    return message;
  }
  const resolvedStatus = confirmationStatusFromValue(status) ?? "updated";
  return {
    ...message,
    confirmation: {
      ...message.confirmation,
      confirmation_state: "superseded",
      status: resolvedStatus,
      statusLabel: confirmationStatusLabel(resolvedStatus),
      actions: [],
    },
    actions: [],
  };
}

export function supersedeOpenConfirmations(
  messages: Message[],
  status: StrategyConfirmationStatus | string = "updated",
): Message[] {
  const lastResultIndex = messages.reduce(
    (latest, message, index) =>
      message.kind === "strategy_result" ? index : latest,
    -1,
  );
  return messages.map((message, index) =>
    message.kind === "strategy_confirmation" && index > lastResultIndex
      ? supersedePriorConfirmations(message, status)
      : message,
  );
}

export function settleOpenConfirmationsAfterTextFinal(
  messages: Message[],
  {
    action,
    finalActions = [],
    hasFailedAction = false,
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

  if (!hasConfirmationAction && !hasFailedActionFinal) {
    return messages;
  }

  return supersedeOpenConfirmations(
    messages,
    confirmationTextFinalStatus(action, hasFailedActionFinal),
  );
}

export function settleOpenConfirmationsAfterStreamError(
  messages: Message[],
  action: ChatActionOption | undefined,
): Message[] {
  if (!confirmationActionEffectFromAction(action)) {
    return messages;
  }
  return supersedeOpenConfirmations(messages, "could_not_run");
}

export function settleConfirmationAfterActionTransportError(
  messages: Message[],
  action: ChatActionOption | undefined,
): Message[] {
  const effect = confirmationActionEffectFromAction(action);
  if (!effect) {
    return messages;
  }
  const failedEffect: ConfirmationActionEffect = {
    ...effect,
    status: "could_not_run",
    statusLabel: confirmationStatusLabel("could_not_run"),
  };
  return messages.map((message) => {
    if (message.kind !== "strategy_confirmation" || !message.confirmation) {
      return message;
    }
    const confirmationId = message.confirmation.confirmation_id;
    const ownsAction =
      !effect.confirmationId ||
      !confirmationId ||
      effect.confirmationId === confirmationId;
    const status = confirmationStatusFromPayload(message.confirmation);
    if (!ownsAction || !IN_FLIGHT_ACTION_STATUSES.has(status)) {
      return message;
    }
    return closeConfirmationForAction(message, failedEffect);
  });
}

function closeConfirmationForAction(
  message: Message,
  effect: ConfirmationActionEffect,
): Message {
  if (message.kind !== "strategy_confirmation" || !message.confirmation) {
    return message;
  }
  const status = effect.status ?? confirmationActionStatus(effect.type);
  return {
    ...message,
    confirmation: {
      ...message.confirmation,
      confirmation_state:
        effect.type === "cancel_confirmation" ? "cancelled" : "superseded",
      status,
      statusLabel: effect.statusLabel || confirmationStatusLabel(status),
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

function confirmationTextFinalStatus(
  action: ChatActionOption | undefined,
  hasFailedAction: boolean,
) {
  if (hasFailedAction) {
    return "could_not_run";
  }
  return confirmationActionStatus(action);
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

function sourceResultRunIdFromMetadata(metadata: Record<string, unknown>) {
  const sourceResultRunId = stringOrNull(metadata.source_result_run_id);
  if (sourceResultRunId) {
    return sourceResultRunId;
  }
  const pendingStrategy = recordOrNull(metadata.pending_strategy);
  const sourceResult = recordOrNull(pendingStrategy?.source_result);
  return stringOrNull(sourceResult?.run_id) ?? stringOrNull(sourceResult?.runId);
}

function confirmationIdFromAction(action: ChatActionOption) {
  const rawValue = action.payload?.confirmation_id ?? action.payload?.confirmationId;
  return typeof rawValue === "string" && rawValue.trim() ? rawValue.trim() : undefined;
}

function recordOrNull(value: unknown) {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
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
