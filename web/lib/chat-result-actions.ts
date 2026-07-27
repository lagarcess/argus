import type { ChatActionOption, Message } from "@/components/chat/types";
import type { AssetClass, BacktestRun } from "./argus-api";

type ResultActionContext = {
  runId?: string;
  strategyId?: string | null;
  conversationId?: string;
  strategyName?: string;
  symbols?: string[];
  template?: string;
  assetClass?: AssetClass;
};

export const VISIBLE_RESULT_ACTION_TYPES = [
  "show_breakdown",
  "refine_strategy",
  "save_strategy",
] as const;

type VisibleResultActionType = (typeof VISIBLE_RESULT_ACTION_TYPES)[number];

const visibleResultActionTypeSet = new Set<string>(VISIBLE_RESULT_ACTION_TYPES);

export function isVisibleResultAction(
  action: ChatActionOption,
): action is ChatActionOption & { type: VisibleResultActionType } {
  return Boolean(action.type && visibleResultActionTypeSet.has(action.type));
}

export function hydrateResultActions(
  actions: ChatActionOption[],
  context: ResultActionContext,
): ChatActionOption[] {
  return actions
    .filter(isVisibleResultAction)
    .filter(
      (action) =>
        !resultActionRequiresRunContext(action) ||
        hasResultActionContext(context.runId, context.conversationId),
    )
    .map((action) => ({
      id: action.id || action.type || action.label,
      label: action.label,
      labelKey: action.labelKey,
      type: action.type,
      presentation: "result" as const,
      payload: {
        ...(action.payload ?? {}),
        run_id: context.runId ?? "",
        strategy_id: context.strategyId ?? null,
        conversation_id: context.conversationId,
        strategy_name: context.strategyName,
        symbols: context.symbols ?? [],
        ...(context.template !== undefined
          ? { template: context.template }
          : {}),
        ...(context.assetClass ? { asset_class: context.assetClass } : {}),
      },
      value: action.value,
    }));
}

export function hydrateResultActionsForRun(
  actions: ChatActionOption[],
  run: BacktestRun,
): ChatActionOption[] {
  return hydrateResultActions(actions, {
    runId: run.id,
    strategyId: run.strategy_id ?? null,
    conversationId: run.conversation_id ?? undefined,
    strategyName: run.conversation_result_card.title,
    symbols: run.symbols,
    template: String(run.config_snapshot?.template ?? ""),
    assetClass: run.asset_class,
  });
}

export function markResultCardSaved(
  messages: Message[],
  runId: string | null,
  savedStrategyId: string,
): Message[] {
  if (!runId) return messages;
  return messages.map((message) => {
    if (
      message.kind !== "strategy_result" ||
      !message.result ||
      message.result.runId !== runId
    ) {
      return message;
    }
    const resultActions = message.result.actions?.map((action) =>
      action.type === "save_strategy" ? { ...action, savedStrategyId } : action,
    );
    const messageActions = message.actions?.map((action) =>
      action.type === "save_strategy" ? { ...action, savedStrategyId } : action,
    );
    return {
      ...message,
      savedStrategyId,
      savingStrategy: false,
      actions: messageActions ?? resultActions ?? message.actions,
      result: {
        ...message.result,
        savedStrategyId,
        savingStrategy: false,
        strategyId: message.result.strategyId ?? savedStrategyId,
        actions: resultActions ?? message.result.actions,
      },
    };
  });
}

export function markResultCardSaving(
  messages: Message[],
  runId: string | null,
  savingStrategy: boolean,
): Message[] {
  if (!runId) return messages;
  return messages.map((message) => {
    if (
      message.kind !== "strategy_result" ||
      !message.result ||
      message.result.runId !== runId
    ) {
      return message;
    }
    return {
      ...message,
      result: {
        ...message.result,
        savingStrategy,
      },
    };
  });
}

function resultActionRequiresRunContext(action: ChatActionOption): boolean {
  return (
    action.type === "show_breakdown" ||
    action.type === "save_strategy" ||
    action.type === "refine_strategy"
  );
}

function hasResultActionContext(
  runId: string | undefined,
  conversationId: string | undefined,
): boolean {
  return Boolean(runId && conversationId);
}
