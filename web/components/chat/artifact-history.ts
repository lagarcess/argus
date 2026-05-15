import type { ApiMessage } from "@/lib/argus-api";
import type { ChatActionOption, Message } from "./types";

export type ConfirmationActionEffect = {
  type: NonNullable<ChatActionOption["type"]>;
  confirmationId?: string;
  statusLabel: string;
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
    return "Draft cancelled";
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

function confirmationIdFromAction(action: ChatActionOption) {
  const rawValue = action.payload?.confirmation_id ?? action.payload?.confirmationId;
  return typeof rawValue === "string" && rawValue.trim() ? rawValue.trim() : undefined;
}
