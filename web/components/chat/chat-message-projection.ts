import {
  resultCardFromConversationCard,
  type ApiMessage,
  type AssetClass,
  type ChatActionRequest,
} from "@/lib/argus-api";
import { actionHasCardScopedOwnership } from "@/lib/chat-action-ownership";
import { discoverySidecarFromMetadata } from "@/lib/chat-discovery-sidecar";
import {
  applyHydratedBacktestJobTruth,
  backtestJobMessageFromApi,
} from "@/lib/chat-backtest-jobs";
import {
  hydrateTextMessageFromApi,
  isHydratableResultCard,
  recordOrNull,
  retryRequestMessageForAssistant,
  stringArrayOrNull,
  stringOrNull,
} from "@/lib/chat-message-hydration";
import {
  normalizeDurableRetryActionHistory,
} from "@/lib/chat-retry-actions";
import {
  hydrateResultActions,
} from "@/lib/chat-result-actions";
import { retainCanonicalResultProjectionOwners } from "@/lib/chat-result-projection-ownership";
import { visibleComposerResponseActions } from "@/lib/chat-recovery-display";
import {
  applyConsumedResultActions,
  applyConfirmationActionEffects,
  confirmationActionEffectFromAction,
  confirmationActionEffectsFromApi,
  consumedResultActionsFromApi,
  hiddenSaveActionMessageIdsFromApi,
  isBreakdownActionMetadata,
  normalizeConfirmationHistory,
  settleOpenConfirmationsAfterTextFinal,
} from "./artifact-history";
import {
  confirmationStatusAllowsActions,
  confirmationStatusFromPayload,
} from "./confirmation-display";
import type {
  ChatActionOption,
  Message,
  StrategyConfirmationPayload,
} from "./types";

export type HydratedMessages = {
  messages: Message[];
  inputActions: ChatActionOption[];
};

export function chatActionRequestFromAction(
  action: ChatActionOption,
): ChatActionRequest {
  return {
    type: action.type as NonNullable<ChatActionOption["type"]>,
    label: action.label,
    labelKey: action.labelKey,
    payload: action.payload,
    presentation: action.presentation,
  };
}

export function settleOpenConfirmationsFromFinalPayload(
  messages: Message[],
  finalPayload: Record<string, unknown>,
  options: Omit<
    Parameters<typeof settleOpenConfirmationsAfterTextFinal>[1],
    "stageOutcome" | "recoveryCode"
  >,
): Message[] {
  return settleOpenConfirmationsAfterTextFinal(messages, {
    ...options,
    stageOutcome: finalPayload.stage_outcome,
    recoveryCode: stringOrNull(recordOrNull(finalPayload.recovery)?.code),
  });
}

export function latestInputActions(messages: Message[]): ChatActionOption[] {
  if (hasActiveArtifactActionSet(messages)) return [];
  const latestAi = [...messages]
    .reverse()
    .find((message) => message.role === "ai");
  if (
    latestAi?.kind === "strategy_confirmation" ||
    latestAi?.kind === "strategy_result"
  ) {
    return [];
  }
  return visibleComposerResponseActions(latestAi?.actions ?? []).filter(
    (action) => action.artifactType !== "failed_action",
  );
}

export function hasActiveArtifactActionSet(messages: Message[]): boolean {
  return messages.some((message) => {
    if (message.kind === "strategy_confirmation" && message.confirmation) {
      if (
        message.confirmation.confirmation_state &&
        message.confirmation.confirmation_state !== "active"
      ) {
        return false;
      }
      const status = confirmationStatusFromPayload(message.confirmation);
      if (!confirmationStatusAllowsActions(status)) return false;
      const actions = message.confirmation.actions ?? message.actions ?? [];
      return actions.some(actionHasCardScopedOwnership);
    }
    if (message.kind === "strategy_result" && message.result) {
      const actions = message.result.actions ?? message.actions ?? [];
      return actions.some(actionHasCardScopedOwnership);
    }
    return false;
  });
}

export function isFailedActionRetry(
  action: ChatActionOption | undefined,
): boolean {
  return Boolean(
    action &&
      (action.type === "retry_failed_action" ||
        action.artifactType === "failed_action"),
  );
}

export function consumeConfirmationActionOnMessages(
  messages: Message[],
  action: ChatActionOption | undefined,
): Message[] {
  const effect = confirmationActionEffectFromAction(action);
  return effect ? applyConfirmationActionEffects(messages, [effect]) : messages;
}

function assetClassOrUndefined(value: unknown): AssetClass | undefined {
  return value === "crypto" || value === "equity" || value === "currency_pair"
    ? value
    : undefined;
}

function resultActionContextFromMetadata(
  metadata: Record<string, unknown>,
  card: ReturnType<typeof resultCardFromConversationCard>,
) {
  const factBank = recordOrNull(metadata.result_fact_bank);
  const configSnapshot = recordOrNull(factBank?.config_snapshot);
  return {
    symbols: card.symbols ?? stringArrayOrNull(factBank?.symbols) ?? [],
    template: stringOrNull(configSnapshot?.template),
    assetClass: assetClassOrUndefined(factBank?.asset_class),
  };
}

function savedStrategyIdFromMetadata(
  metadata: Record<string, unknown>,
): string | null {
  return stringOrNull(metadata.saved_strategy_id);
}

export function savedStrategyIdFromFinalPayload(
  payload: Record<string, unknown>,
): string | null {
  return stringOrNull(payload.saved_strategy_id);
}

export function resultRunIdFromFinalPayload(
  payload: Record<string, unknown>,
  action?: ChatActionOption,
): string | null {
  const run = payload.run;
  const runId =
    typeof run === "object" && run !== null && "id" in run
      ? stringOrNull(run.id)
      : null;
  return (
    stringOrNull(payload.result_run_id) ??
    stringOrNull(payload.latest_run_id) ??
    runId ??
    stringOrNull(action?.payload?.run_id)
  );
}

export function markComposerActionsInactive(messages: Message[]): Message[] {
  return messages.map((message) => {
    if (message.kind === "strategy_result" && message.result) {
      const resultActions = message.result.actions ?? message.actions;
      return {
        ...message,
        actions: undefined,
        result: { ...message.result, actions: resultActions },
      };
    }
    if (message.kind === "strategy_confirmation" && message.confirmation) {
      const actions = message.confirmation.actions ?? message.actions;
      return {
        ...message,
        actions: undefined,
        confirmation: { ...message.confirmation, actions },
      };
    }
    // Retry belongs to the turn that failed, so a newer send supersedes it the
    // same way a newer card supersedes an older one. Conversational next moves
    // belong to the conversation, not to an artifact: whether a clarify option
    // is still answerable is decided by the row renderer, which is also the only
    // owner that survives reload -- hydration rebuilds actions for every
    // historical message, not just the newest.
    if (!message.actions) return message;
    const conversational = message.actions.filter(
      (action) => action.type === "select_response_option",
    );
    if (conversational.length === message.actions.length) return message;
    return {
      ...message,
      actions: conversational.length > 0 ? conversational : undefined,
    };
  });
}

export function hydrateMessagesFromApi(
  items: ApiMessage[],
): HydratedMessages {
  const consumedResultActions = consumedResultActionsFromApi(items);
  const confirmationActionEffects = confirmationActionEffectsFromApi(items);
  const hiddenMessageIds = new Set([
    ...hiddenSaveActionMessageIdsFromApi(items),
    ...confirmationActionEffects.hiddenMessageIds,
  ]);
  const messages: Message[] = retainCanonicalResultProjectionOwners(items)
    .filter((message) => !hiddenMessageIds.has(message.id))
    .map((message) => {
      const metadata = message.metadata ?? {};
      const chatAction = metadata.chat_action as ChatActionOption | undefined;
      const confirmation = metadata.confirmation_card as
        | StrategyConfirmationPayload
        | undefined;
      const projectedJob =
        message.role === "user" ? backtestJobMessageFromApi(message) : null;
      if (projectedJob) return projectedJob;
      if (
        message.role === "user" &&
        chatAction &&
        typeof chatAction === "object"
      ) {
        return {
          ...hydrateTextMessageFromApi(message),
          kind: "action",
          selectedAction: chatAction,
        };
      }
      if (
        message.role !== "user" &&
        !isBreakdownActionMetadata(metadata) &&
        isHydratableResultCard(metadata.result_card)
      ) {
        const runId = String(
          metadata.result_run_id ?? metadata.latest_run_id ?? "",
        );
        const conversationId =
          typeof metadata.result_conversation_id === "string"
            ? metadata.result_conversation_id
            : message.conversation_id;
        const resultStrategyId = stringOrNull(metadata.result_strategy_id);
        const savedStrategyId = savedStrategyIdFromMetadata(metadata);
        const factBank = recordOrNull(metadata.result_fact_bank);
        const configSnapshot = recordOrNull(factBank?.config_snapshot);
        const card = resultCardFromConversationCard(metadata.result_card, {
          id: runId,
          strategy_id: resultStrategyId,
          benchmark_symbol:
            stringOrNull(factBank?.benchmark_symbol) ?? undefined,
          config_snapshot: configSnapshot ?? undefined,
        });
        const context = resultActionContextFromMetadata(metadata, card);
        const actions = hydrateResultActions(card.actions ?? [], {
          runId: card.runId,
          strategyId: card.strategyId,
          conversationId,
          strategyName: card.strategyName,
          symbols: context.symbols,
          template: context.template ?? undefined,
          assetClass: context.assetClass,
        });
        return {
          id: message.id,
          role: "ai",
          kind: "strategy_result",
          content: message.content,
          result: {
            ...card,
            symbols: context.symbols,
            template: context.template ?? undefined,
            assetClass: context.assetClass,
            savedStrategyId,
            actions,
          },
          actions,
          savedStrategyId,
        };
      }
      const jobMessage = backtestJobMessageFromApi(message);
      if (jobMessage) return jobMessage;
      if (
        message.role !== "user" &&
        confirmation &&
        Array.isArray(confirmation.rows) &&
        // A discovery answer owns its message: if confirmation chrome ever
        // co-arrives, the rows the user asked for must not silently drop.
        !discoverySidecarFromMetadata(metadata)
      ) {
        return {
          id: message.id,
          role: "ai",
          kind: "strategy_confirmation",
          content: message.content,
          confirmation,
          actions: confirmation.actions ?? [],
        };
      }
      const hydratedText = hydrateTextMessageFromApi(message, {
        contentPresentation:
          message.role !== "user" && isBreakdownActionMetadata(metadata)
            ? "result_breakdown"
            : undefined,
        retryRequestMessage: retryRequestMessageForAssistant(items, message),
      });
      if (message.role !== "user") {
        const discovery = discoverySidecarFromMetadata(metadata);
        if (discovery) return { ...hydratedText, discovery };
      }
      return hydratedText;
    });

  const normalized = normalizeDurableRetryActionHistory(
    applyConsumedResultActions(
      applyHydratedBacktestJobTruth(
        applyConfirmationActionEffects(
          normalizeConfirmationHistory(messages),
          confirmationActionEffects.effects,
        ),
      ),
      consumedResultActions,
    ),
  );
  return { messages: normalized, inputActions: latestInputActions(normalized) };
}

export function chatStreamErrorText(
  detail: string | undefined,
  fallback: string,
): string {
  return detail || fallback;
}
