// Transcript hydration for the shared chat shell: maps persisted API
// messages into renderable shell messages. Behavior-preserving extraction
// from ChatInterface.tsx.

import {
  type ApiMessage,
  type AssetClass,
  type ConversationResultCard,
  resultCardFromConversationCard,
} from "@/lib/argus-api";
import { visibleComposerActions } from "@/lib/chat-action-ownership";
import { backtestJobMessageFromApi } from "@/lib/chat-backtest-jobs";
import {
  abandonedRecoveryFromApiMessage,
  hydrateTextMessageFromApi,
} from "@/lib/chat-message-hydration";
import { hydrateResultActions } from "@/lib/chat-result-actions";
import { normalizeRetryActionHistory } from "@/lib/chat-retry-action-history";
import {
  applyConfirmationActionEffects,
  applyConsumedResultActions,
  confirmationActionEffectsFromApi,
  consumedResultActionsFromApi,
  hiddenSaveActionMessageIdsFromApi,
  isBreakdownActionMetadata,
  normalizeConfirmationHistory,
} from "./artifact-history";
import { confirmationStatusAllowsActions, confirmationStatusFromPayload } from "./confirmation-display";
import { actionHasCardScopedOwnership } from "@/lib/chat-action-ownership";
import type {
  ChatActionOption,
  Message,
  StrategyConfirmationPayload,
} from "./types";



function stringOrNull(value: unknown) {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function savedStrategyIdFromMetadata(metadata: Record<string, unknown>) {
  return stringOrNull(metadata.saved_strategy_id);
}

function recordOrNull(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function isHydratableResultCard(value: unknown): value is ConversationResultCard {
  const card = recordOrNull(value);
  const dateRange = recordOrNull(card?.date_range);
  return Boolean(
    card &&
      typeof card.title === "string" &&
      typeof card.status_label === "string" &&
      Array.isArray(card.rows) &&
      Array.isArray(card.assumptions) &&
      Array.isArray(card.actions) &&
      dateRange &&
      typeof dateRange.start === "string" &&
      typeof dateRange.end === "string" &&
      typeof dateRange.display === "string",
  );
}

export type HydratedMessages = {
  messages: Message[];
  inputActions: ChatActionOption[];
};

function resultActionContextFromMetadata(
  metadata: Record<string, unknown>,
  card: ReturnType<typeof resultCardFromConversationCard>,
) {
  const factBank = recordOrNull(metadata.result_fact_bank);
  const configSnapshot = recordOrNull(factBank?.config_snapshot);
  const symbols = card.symbols ?? stringArrayOrNull(factBank?.symbols) ?? [];
  return {
    symbols,
    template: stringOrNull(configSnapshot?.template),
    assetClass: assetClassOrUndefined(factBank?.asset_class),
  };
}

function latestInputActions(messages: Message[]) {
  if (hasActiveArtifactActionSet(messages)) {
    return [];
  }
  const latestAi = [...messages].reverse().find((message) => message.role === "ai");
  if (
    latestAi?.kind === "strategy_confirmation" ||
    latestAi?.kind === "strategy_result"
  ) {
    return [];
  }
  return visibleComposerActions(latestAi?.actions ?? []).filter(
    (action) => action.artifactType !== "failed_action",
  );
}

function stringArrayOrNull(value: unknown): string[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const values = value.map(String).filter(Boolean);
  return values.length > 0 ? values : null;
}

function assetClassOrUndefined(value: unknown): AssetClass | undefined {
  return value === "crypto" || value === "equity" || value === "currency_pair"
    ? value
    : undefined;
}

function hasActiveArtifactActionSet(messages: Message[]) {
  return messages.some((message) => {
    if (message.kind === "strategy_confirmation" && message.confirmation) {
      if (
        message.confirmation.confirmation_state &&
        message.confirmation.confirmation_state !== "active"
      ) {
        return false;
      }
      const confirmationStatus = confirmationStatusFromPayload(message.confirmation);
      if (!confirmationStatusAllowsActions(confirmationStatus)) {
        return false;
      }
      const activeActions = message.confirmation.actions ?? message.actions ?? [];
      return activeActions.some(actionHasCardScopedOwnership);
    }
    if (message.kind === "strategy_result" && message.result) {
      const activeActions = message.result.actions ?? message.actions ?? [];
      return activeActions.some(actionHasCardScopedOwnership);
    }
    return false;
  });
}

export function hydrateMessagesFromApi(items: ApiMessage[]): HydratedMessages {
  const consumedResultActions = consumedResultActionsFromApi(items);
  const confirmationActionEffects = confirmationActionEffectsFromApi(items);
  const hiddenMessageIds = new Set([
    ...hiddenSaveActionMessageIdsFromApi(items),
    ...confirmationActionEffects.hiddenMessageIds,
  ]);
  const messages: Message[] = items.filter((m) => !hiddenMessageIds.has(m.id)).map((m) => {
    const metadata = m.metadata ?? {};
    const chatAction = metadata.chat_action as ChatActionOption | undefined;
    const confirmation = metadata.confirmation_card as StrategyConfirmationPayload | undefined;
    const resultCard = metadata.result_card;
    if (m.role === "user" && chatAction && typeof chatAction === "object") {
      return {
        id: m.id,
        role: "user",
        kind: "action",
        content: m.content,
        selectedAction: chatAction,
        // #240: a structured abandoned action keeps its action-row
        // presentation and still carries its recovery attachment.
        abandonedRecovery: abandonedRecoveryFromApiMessage(m),
      };
    }
    if (
      m.role !== "user" &&
      !isBreakdownActionMetadata(metadata) &&
      isHydratableResultCard(resultCard)
    ) {
      const runId = String(metadata.result_run_id ?? metadata.latest_run_id ?? "");
      const conversationId =
        typeof metadata.result_conversation_id === "string"
          ? metadata.result_conversation_id
          : m.conversation_id;
      const resultStrategyId = stringOrNull(metadata.result_strategy_id);
      const savedStrategyId = savedStrategyIdFromMetadata(metadata);
      const factBank = recordOrNull(metadata.result_fact_bank);
      const configSnapshot = recordOrNull(factBank?.config_snapshot);
      const card = resultCardFromConversationCard(resultCard, {
        id: runId,
        strategy_id: resultStrategyId,
        benchmark_symbol: stringOrNull(factBank?.benchmark_symbol) ?? undefined,
        config_snapshot: configSnapshot ?? undefined,
      });
      const resultActionContext = resultActionContextFromMetadata(metadata, card);
      const restoredActions = hydrateResultActions(card.actions ?? [], {
        runId: card.runId,
        strategyId: card.strategyId,
        conversationId,
        strategyName: card.strategyName,
        symbols: resultActionContext.symbols,
        template: resultActionContext.template ?? undefined,
        assetClass: resultActionContext.assetClass,
      });
      return {
        id: m.id,
        role: "ai",
        kind: "strategy_result",
        content: m.content,
        result: {
          ...card,
          symbols: resultActionContext.symbols,
          template: resultActionContext.template ?? undefined,
          assetClass: resultActionContext.assetClass,
          savedStrategyId,
          actions: restoredActions,
        },
        actions: restoredActions,
        savedStrategyId,
      };
    }
    const backtestJobMessage = backtestJobMessageFromApi(m);
    if (backtestJobMessage) {
      return backtestJobMessage;
    }
    if (m.role !== "user" && confirmation && Array.isArray(confirmation.rows)) {
      return {
        id: m.id,
        role: "ai",
        kind: "strategy_confirmation",
        content: m.content,
        confirmation,
        actions: confirmation.actions ?? [],
      };
    }
    return hydrateTextMessageFromApi(m, {
      contentPresentation:
        m.role !== "user" && isBreakdownActionMetadata(metadata)
          ? "result_breakdown"
          : undefined,
    });
  });

  const normalized = normalizeRetryActionHistory(
    applyConsumedResultActions(
      applyConfirmationActionEffects(
        normalizeConfirmationHistory(messages),
        confirmationActionEffects.effects,
      ),
      consumedResultActions,
    ),
  );
  return { messages: normalized, inputActions: latestInputActions(normalized) };
}
