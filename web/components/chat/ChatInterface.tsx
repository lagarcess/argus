"use client";

import { useMemo, useEffect, useRef, useState } from "react";
import {
  Archive,
  ArrowDown,
  ChevronRight,
  History,
  PanelLeft,
  MessageSquarePlus,
  MoreHorizontal,
  Plus,
  Search,
  Settings,
  Trash2,
  TrendingUp,
  Bitcoin,
  LineChart,
  Layers,
  Compass,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { ArgusLogo } from "@/components/ArgusLogo";

import {
  createConversation,
  deleteCollection,
  deleteConversation,
  deleteStrategy,
  formatRelativeDate,
  getBacktestRun,
  getMe,
  getConversationMessages,
  getStarterPrompts,
  listHistory,
  searchGlobal,
  patchCollection,
  patchConversation,
  patchMe,
  patchStrategy,
  resultCardFromConversationCard,
  resultCardFromRun,
  streamChatMessage,
  type ApiMessage,
  type AssetClass,
  ChatStreamError,
  type ChatStreamEvent,
  type ChatActionRequest,
  type ConversationResultCard,
  type HistoryItem,
  type BacktestRun,
  type PrimaryGoal,
  type SearchItem,
} from "@/lib/argus-api";
import CollectionPicker from "./CollectionPicker";
import CollectionsView from "../views/CollectionsView";
import SettingsView from "../views/SettingsView";
import StrategiesView from "../views/StrategiesView";
import ChatInput from "./ChatInput";
import ChatMessage from "./ChatMessage";
import FeedbackDialog from "../feedback/FeedbackDialog";
import { type ChatActionOption, type ChatMention, type Message, type StrategyConfirmationPayload } from "./types";

// ─── Constants ────────────────────────────────────────────────────────────────

type View = "chat" | "strategies" | "collections" | "settings";
type OnboardingChoice = {
  goal: PrimaryGoal;
  title: string;
  description: string;
};

const JUMP_TO_LATEST_THRESHOLD_PX = 240;
const ACTIVE_CONVERSATION_STORAGE_KEY = "argus.activeConversationId";

type HydratedMessages = {
  messages: Message[];
  inputActions: ChatActionOption[];
};

type ConsumedResultAction = {
  type: "show_breakdown" | "save_strategy";
  runId?: string;
  savedStrategyId?: string | null;
};

function readActiveConversationId() {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY);
  } catch {
    return null;
  }
}

function persistActiveConversationId(conversationId: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, conversationId);
  } catch {
    // Storage can be unavailable in restricted browser contexts.
  }
}

function clearActiveConversationId() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(ACTIVE_CONVERSATION_STORAGE_KEY);
  } catch {
    // Storage can be unavailable in restricted browser contexts.
  }
}

function latestInputActions(messages: Message[]) {
  const latestAi = [...messages].reverse().find((message) => message.role === "ai");
  if (
    latestAi?.kind === "strategy_confirmation" ||
    latestAi?.kind === "strategy_result"
  ) {
    return [];
  }
  return (latestAi?.actions ?? []).filter((action) => action.type !== "save_strategy");
}

const CARD_SCOPED_ACTION_TYPES = new Set<NonNullable<ChatActionOption["type"]>>([
  "run_backtest",
  "change_dates",
  "change_asset",
  "adjust_assumptions",
  "cancel_confirmation",
  "show_breakdown",
  "refine_strategy",
  "save_strategy",
]);

function isCardScopedAction(action: ChatActionOption) {
  return Boolean(action.type && CARD_SCOPED_ACTION_TYPES.has(action.type));
}

function visibleInputActions(actions: ChatActionOption[]) {
  return actions.filter((action) => action.type !== "save_strategy");
}

function visibleComposerActions(actions: ChatActionOption[]) {
  return visibleInputActions(actions).filter((action) => !isCardScopedAction(action));
}

function hasActiveArtifactActionSet(messages: Message[]) {
  const latestAi = [...messages].reverse().find((message) => message.role === "ai");
  if (!latestAi) {
    return false;
  }
  if (latestAi.kind === "strategy_confirmation" && latestAi.confirmation) {
    const activeActions = latestAi.confirmation.confirmation_state !== "superseded"
      ? latestAi.confirmation.actions ?? latestAi.actions ?? []
      : [];
    return activeActions.length > 0;
  }
  if (latestAi.kind === "strategy_result" && latestAi.result) {
    const activeActions = latestAi.result.actions ?? latestAi.actions ?? [];
    return activeActions.length > 0;
  }
  return false;
}

function isBreakdownActionMetadata(metadata: Record<string, unknown>) {
  const chatAction = metadata.chat_action;
  return (
    typeof chatAction === "object" &&
    chatAction !== null &&
    "type" in chatAction &&
    chatAction.type === "show_breakdown"
  );
}

function isSaveActionMetadata(metadata: Record<string, unknown>) {
  const chatAction = metadata.chat_action;
  return (
    typeof chatAction === "object" &&
    chatAction !== null &&
    "type" in chatAction &&
    chatAction.type === "save_strategy"
  );
}

function consumeInputAction(action: ChatActionOption, actions: ChatActionOption[]) {
  if (action.type === "show_breakdown") {
    return actions.filter((candidate) => candidate.type !== "show_breakdown");
  }
  return [];
}

function resultActionRequiresRunContext(action: ChatActionOption) {
  return action.type === "show_breakdown" || action.type === "save_strategy";
}

function resultActionRunId(action: ChatActionOption | undefined) {
  const rawRunId = action?.payload?.run_id ?? action?.payload?.runId;
  return typeof rawRunId === "string" && rawRunId.trim() ? rawRunId.trim() : undefined;
}

function consumedResultActionsFromApi(items: ApiMessage[]): ConsumedResultAction[] {
  return items.flatMap((message) => {
    const metadata = message.metadata ?? {};
    const action = metadata.chat_action as ChatActionOption | undefined;
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

function hiddenSaveActionMessageIdsFromApi(items: ApiMessage[]) {
  const hiddenIds = new Set<string>();
  items.forEach((message, index) => {
    const metadata = message.metadata ?? {};
    if (message.role !== "assistant" || !isSaveActionMetadata(metadata)) {
      return;
    }
    if (!savedStrategyIdFromMetadata(metadata)) {
      return;
    }
    const action = metadata.chat_action as ChatActionOption | undefined;
    const runId = stringOrNull(metadata.result_run_id) ?? resultActionRunId(action);
    hiddenIds.add(message.id);
    for (let cursor = index - 1; cursor >= 0; cursor -= 1) {
      const candidate = items[cursor];
      const candidateMetadata = candidate.metadata ?? {};
      if (candidate.role !== "user" || !isSaveActionMetadata(candidateMetadata)) {
        continue;
      }
      const candidateAction = candidateMetadata.chat_action as ChatActionOption | undefined;
      if (!runId || resultActionRunId(candidateAction) === runId) {
        hiddenIds.add(candidate.id);
        return;
      }
    }
  });
  return hiddenIds;
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

function applyConsumedResultActions(
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

function consumeResultActionOnMessages(
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

function hasResultActionContext(runId: string | undefined, conversationId: string | undefined) {
  return Boolean(runId && conversationId);
}

function hydrateResultActions(
  actions: ChatActionOption[],
  context: {
    runId?: string;
    strategyId?: string | null;
    conversationId?: string;
    strategyName?: string;
    symbols?: string[];
    template?: string;
    assetClass?: AssetClass;
  },
) {
  return actions
    .filter(
      (action) =>
        !resultActionRequiresRunContext(action) ||
        hasResultActionContext(context.runId, context.conversationId),
    )
    .map((action) => ({
      id: action.id || action.type || action.label,
      label: action.label,
      type: action.type,
      presentation: "result" as const,
      payload: {
        ...(action.payload ?? {}),
        run_id: context.runId ?? "",
        strategy_id: context.strategyId ?? null,
        conversation_id: context.conversationId,
        strategy_name: context.strategyName,
        symbols: context.symbols ?? [],
        ...(context.template !== undefined ? { template: context.template } : {}),
        ...(context.assetClass ? { asset_class: context.assetClass } : {}),
      },
      value: action.value,
    }));
}

function stringOrNull(value: unknown) {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function recordOrNull(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringArrayOrNull(value: unknown): string[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const values = value.map(String).filter(Boolean);
  return values.length > 0 ? values : null;
}

function assetClassOrUndefined(value: unknown): AssetClass | undefined {
  return value === "crypto" || value === "equity" ? value : undefined;
}

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

function savedStrategyIdFromMetadata(metadata: Record<string, unknown>) {
  return stringOrNull(metadata.saved_strategy_id);
}

function savedStrategyIdFromFinalPayload(payload: Record<string, unknown>) {
  return stringOrNull(payload.saved_strategy_id);
}

function resultRunIdFromFinalPayload(
  payload: Record<string, unknown>,
  action?: ChatActionOption,
) {
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

function markComposerActionsInactive(messages: Message[]): Message[] {
  return messages.map((message) => {
    if (message.kind === "strategy_result" && message.result) {
      const resultActions = message.result.actions ?? message.actions;
      return {
        ...message,
        actions: undefined,
        result: {
          ...message.result,
          actions: resultActions,
        },
      };
    }
    if (message.kind === "strategy_confirmation" && message.confirmation) {
      const confirmationActions = message.confirmation.actions ?? message.actions;
      return {
        ...message,
        actions: undefined,
        confirmation: {
          ...message.confirmation,
          actions: confirmationActions,
        },
      };
    }
    return message.actions ? { ...message, actions: undefined } : message;
  });
}

function markResultCardSaved(
  messages: Message[],
  runId: string | null,
  savedStrategyId: string,
): Message[] {
  if (!runId) return messages;
  return messages.map((message) => {
    if (message.kind !== "strategy_result" || !message.result || message.result.runId !== runId) {
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

function markResultCardSaving(
  messages: Message[],
  runId: string | null,
  savingStrategy: boolean,
): Message[] {
  if (!runId) return messages;
  return messages.map((message) => {
    if (message.kind !== "strategy_result" || !message.result || message.result.runId !== runId) {
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

function hydrateMessagesFromApi(items: ApiMessage[]): HydratedMessages {
  const consumedResultActions = consumedResultActionsFromApi(items);
  const hiddenMessageIds = hiddenSaveActionMessageIdsFromApi(items);
  const messages: Message[] = items.filter((m) => !hiddenMessageIds.has(m.id)).map((m) => {
    const metadata = m.metadata ?? {};
    const chatAction = metadata.chat_action as ChatActionOption | undefined;
    const confirmation = metadata.confirmation_card as StrategyConfirmationPayload | undefined;
    const resultCard = metadata.result_card as ConversationResultCard | undefined;
    if (m.role === "user" && chatAction && typeof chatAction === "object") {
      return {
        id: m.id,
        role: "user",
        kind: "action",
        content: m.content,
        selectedAction: chatAction,
      };
    }
    if (
      m.role !== "user" &&
      !isBreakdownActionMetadata(metadata) &&
      resultCard &&
      Array.isArray(resultCard.rows)
    ) {
      const runId = String(metadata.result_run_id ?? metadata.latest_run_id ?? "");
      const conversationId =
        typeof metadata.result_conversation_id === "string"
          ? metadata.result_conversation_id
          : m.conversation_id;
      const resultStrategyId = stringOrNull(metadata.result_strategy_id);
      const savedStrategyId = savedStrategyIdFromMetadata(metadata);
      const card = resultCardFromConversationCard(resultCard, {
        id: runId,
        strategy_id: resultStrategyId,
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
    return {
      id: m.id,
      role: m.role === "user" ? "user" : "ai",
      kind: "text",
      content: m.content,
      contentPresentation:
        m.role !== "user" && isBreakdownActionMetadata(metadata)
          ? "result_breakdown"
          : undefined,
    };
  });

  const normalized = applyConsumedResultActions(
    normalizeConfirmationHistory(messages),
    consumedResultActions,
  );
  return { messages: normalized, inputActions: latestInputActions(normalized) };
}

function normalizeConfirmationHistory(messages: Message[]): Message[] {
  const lastResultIndex = messages.reduce(
    (latest, message, index) =>
      message.kind === "strategy_result" ? index : latest,
    -1,
  );
  const latestConfirmationIndex = messages.reduce(
    (latest, message, index) =>
      message.kind === "strategy_confirmation" && index > lastResultIndex
        ? index
        : latest,
    -1,
  );
  return messages.map((message, index) => {
    if (message.kind !== "strategy_confirmation" || !message.confirmation) {
      return message;
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
    return supersedePriorConfirmations(message);
  });
}

function supersedePriorConfirmations(message: Message): Message {
  if (message.kind !== "strategy_confirmation" || !message.confirmation) {
    return message;
  }
  return {
    ...message,
    confirmation: {
      ...message.confirmation,
      confirmation_state: "superseded",
      statusLabel: "Updated",
      actions: [],
    },
    actions: [],
  };
}

function supersedeOpenConfirmations(messages: Message[]): Message[] {
  const lastResultIndex = messages.reduce(
    (latest, message, index) =>
      message.kind === "strategy_result" ? index : latest,
    -1,
  );
  return messages.map((message, index) =>
    message.kind === "strategy_confirmation" && index > lastResultIndex
      ? supersedePriorConfirmations(message)
      : message,
  );
}

function chatStreamErrorText(detail: string | undefined, fallback: string) {
  return detail || fallback;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function ChatInterface() {
  const { t, i18n } = useTranslation();
  const collectionsEnabled = process.env.NEXT_PUBLIC_COLLECTIONS_ENABLED === "true";

  const [starterActions, setStarterActions] = useState<ChatActionOption[]>([]);
  const onboardingChoices = useMemo<OnboardingChoice[]>(
    () => [
      {
        goal: "learn_basics",
        title: t("onboarding.goals.learn_basics.title", "Learn investing basics"),
        description: t(
          "onboarding.goals.learn_basics.description",
          "Start with simple ideas and clear explanations.",
        ),
      },
      {
        goal: "build_passive_strategy",
        title: t("onboarding.goals.build_passive_strategy.title", "Build a passive strategy"),
        description: t(
          "onboarding.goals.build_passive_strategy.description",
          "Focus on long-term, low-maintenance ideas.",
        ),
      },
      {
        goal: "test_stock_idea",
        title: t("onboarding.goals.test_stock_idea.title", "Test a stock idea"),
        description: t(
          "onboarding.goals.test_stock_idea.description",
          "Validate a thesis on symbols you follow.",
        ),
      },
      {
        goal: "explore_crypto",
        title: t("onboarding.goals.explore_crypto.title", "Explore crypto"),
        description: t(
          "onboarding.goals.explore_crypto.description",
          "Try crypto-focused strategy starters.",
        ),
      },
    ],
    [t],
  );

  const [messages, setMessages] = useState<Message[]>([]);
  const [inputActions, setInputActions] = useState<ChatActionOption[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<View>("chat");
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [showChatOptions, setShowChatOptions] = useState(false);
  const [activeChatOptionsPanel, setActiveChatOptionsPanel] = useState<
    "none" | "history" | "collection"
  >("none");
  const [searchText, setSearchText] = useState("");
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [historyNextCursor, setHistoryNextCursor] = useState<string | null>(null);
  const [isLoadingMoreHistory, setIsLoadingMoreHistory] = useState(false);
  const [searchResults, setSearchResults] = useState<SearchItem[]>([]);
  const [searchNextCursor, setSearchNextCursor] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);
  const [isLoadingMoreSearch, setIsLoadingMoreSearch] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [showOnboardingGoalCards, setShowOnboardingGoalCards] = useState(false);
  const [collectionPickerTarget, setCollectionPickerTarget] = useState<{
    runId: string;
    strategyId: string | null;
    strategyName: string;
    symbols: string[];
    template: string;
    assetClass: AssetClass;
  } | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [isRecentsExpanded, setIsRecentsExpanded] = useState(true);
  const [activeMenuId, setActiveMenuId] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [feedbackState, setFeedbackState] = useState<{
    isOpen: boolean;
    type: "bug" | "feature" | "general" | "rating";
    rating?: "positive" | "negative";
    context?: Record<string, unknown>;
  }>({ isOpen: false, type: "general" });

  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const chatOptionsRef = useRef<HTMLDivElement>(null);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);

  // ── Toast helper ───────────────────────────────────────────────────────────

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const mergeHistoryItems = (existing: HistoryItem[], incoming: HistoryItem[]) => {
    const seen = new Set(existing.map((item) => `${item.type}:${item.id}`));
    const merged = [...existing];
    for (const item of incoming) {
      const key = `${item.type}:${item.id}`;
      if (!seen.has(key)) {
        seen.add(key);
        merged.push(item);
      }
    }
    return merged;
  };

  const hydrateResultActionsForRun = (actions: ChatActionOption[], run: BacktestRun): ChatActionOption[] =>
    hydrateResultActions(actions, {
      runId: run.id,
      strategyId: run.strategy_id ?? null,
      conversationId: run.conversation_id ?? undefined,
      strategyName: run.conversation_result_card.title,
      symbols: run.symbols,
      template: String(run.config_snapshot?.template ?? ""),
      assetClass: run.asset_class,
    });

  const loadHistoryPage = async (nextCursor?: string | null, append = false) => {
    const { items, next_cursor } = await listHistory({
      limit: 30,
      cursor: nextCursor ?? undefined,
    });
    const filtered = items.filter(
      (item) =>
        !(item.type === "chat" && item.subtitle === "No messages yet") &&
        (collectionsEnabled || item.type !== "collection"),
    );
    setHistoryItems((prev) => (append ? mergeHistoryItems(prev, filtered) : filtered));
    setHistoryNextCursor(next_cursor);
  };

  // ── History ────────────────────────────────────────────────────────────────

  /** Imperative refresh — safe to call from event handlers */
  const refreshHistory = () => {
    loadHistoryPage(null, false).catch(() => undefined);
  };

  const loadMoreHistory = () => {
    if (!historyNextCursor || isLoadingMoreHistory) return;
    setIsLoadingMoreHistory(true);
    loadHistoryPage(historyNextCursor, true)
      .catch(() => undefined)
      .finally(() => setIsLoadingMoreHistory(false));
  };

  useEffect(() => {
    loadHistoryPage(null, false).catch(() => undefined);
  }, []);

  useEffect(() => {
    if (!isSidebarOpen) {
      setIsRecentsExpanded(false);
    }
  }, [isSidebarOpen]);

  useEffect(() => {
    const query = searchText.trim();
    if (currentView !== "chat" || query.length === 0) {
      setSearchResults([]);
      setSearchNextCursor(null);
      setIsSearching(false);
      return;
    }

    let cancelled = false;
    const timer = setTimeout(() => {
      setIsSearching(true);
      searchGlobal({ q: query, limit: 20 })
        .then(({ items, next_cursor }) => {
          if (cancelled) return;
          setSearchResults(
            collectionsEnabled ? items : items.filter((item) => item.type !== "collection"),
          );
          setSearchNextCursor(next_cursor);
        })
        .catch(() => {
          if (cancelled) return;
          setSearchResults([]);
          setSearchNextCursor(null);
        })
        .finally(() => {
          if (cancelled) return;
          setIsSearching(false);
        });
    }, 250);

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [searchText, currentView, collectionsEnabled]);

  const loadMoreSearch = async () => {
    const query = searchText.trim();
    if (!searchNextCursor || !query || isLoadingMoreSearch) return;
    setIsLoadingMoreSearch(true);
    try {
      const { items, next_cursor } = await searchGlobal({
        q: query,
        limit: 20,
        cursor: searchNextCursor,
      });
      setSearchResults((prev) => {
        const seen = new Set(prev.map((item) => `${item.type}:${item.id}`));
        const merged = [...prev];
        const visibleItems = collectionsEnabled
          ? items
          : items.filter((item) => item.type !== "collection");
        for (const item of visibleItems) {
          const key = `${item.type}:${item.id}`;
          if (!seen.has(key)) {
            seen.add(key);
            merged.push(item);
          }
        }
        return merged;
      });
      setSearchNextCursor(next_cursor);
    } finally {
      setIsLoadingMoreSearch(false);
    }
  };

  // ── Init conversation ──────────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const meResponse = await getMe().catch(() => null);
        const resolvedLanguage = meResponse?.user?.language ?? i18n.language;
        if (resolvedLanguage && resolvedLanguage !== i18n.language) {
          await i18n.changeLanguage(resolvedLanguage);
        }
        const stage = meResponse?.user?.onboarding?.stage;
        const activeConversationId = readActiveConversationId();
        if (activeConversationId) {
          try {
            const { items } = await getConversationMessages(activeConversationId, 50);
            if (cancelled) return;
            const hydrated = hydrateMessagesFromApi(items);
            setConversationId(activeConversationId);
            setMessages(hydrated.messages);
            setInputActions(hydrated.inputActions);
            setShowOnboardingGoalCards(
              hydrated.messages.length === 0
              && (stage === "language_selection" || stage === "primary_goal_selection"),
            );

            const prompts = await getStarterPrompts().catch(() => []);
            if (cancelled) return;
            setStarterActions(prompts.map((p, i) => ({
              id: `starter-${i}`,
              label: p,
              value: p,
            })));
            return;
          } catch {
            clearActiveConversationId();
          }
        }

        const { conversation } = await createConversation(resolvedLanguage);
        if (cancelled) return;
        persistActiveConversationId(conversation.id);
        setConversationId(conversation.id);
        setMessages([]);
        setShowOnboardingGoalCards(
          stage === "language_selection" || stage === "primary_goal_selection",
        );

        const prompts = await getStarterPrompts().catch(() => []);
        setStarterActions(prompts.map((p, i) => ({
          id: `starter-${i}`,
          label: p,
          value: p,
        })));
      } catch {
        if (cancelled) return;
        setMessages([
          {
            id: "offline",
            role: "ai",
            kind: "text",
            content: t('chat.error_offline'),
          },
        ]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const updateScrollPositionState = () => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const isNearBottom = distanceFromBottom <= JUMP_TO_LATEST_THRESHOLD_PX;
    shouldAutoScrollRef.current = isNearBottom;
    setShowJumpToLatest(distanceFromBottom > JUMP_TO_LATEST_THRESHOLD_PX);
  };

  const scrollToLatest = (behavior: ScrollBehavior = "smooth") => {
    bottomRef.current?.scrollIntoView({ behavior });
    shouldAutoScrollRef.current = true;
    setShowJumpToLatest(false);
  };

  useEffect(() => {
    if (shouldAutoScrollRef.current) {
      scrollToLatest("smooth");
    } else {
      updateScrollPositionState();
    }
  }, [messages.length, streamStatus]);

  // ── Load existing conversation ─────────────────────────────────────────────

  const loadConversation = async (convId: string) => {
    setIsSidebarOpen(false);
    closeChatOptions();
    setCurrentView("chat");
    persistActiveConversationId(convId);
    setConversationId(convId);
    setMessages([]);
    setInputActions([]);
    setStreamStatus(t('common.loading'));
    try {
      const { items } = await getConversationMessages(convId, 50);
      const hydrated = hydrateMessagesFromApi(items);
      setMessages(hydrated.messages);
      setInputActions(hydrated.inputActions);
    } catch {
      setMessages([
        {
          id: "resume-error",
          role: "ai",
          kind: "text",
          content: t('chat.error_load'),
        },
      ]);
    } finally {
      setStreamStatus(null);
    }
  };

  const loadConversationForRun = async (item: Pick<HistoryItem | SearchItem, "id" | "conversation_id">) => {
    if (item.conversation_id) {
      void loadConversation(item.conversation_id);
      return;
    }
    try {
      const { run } = await getBacktestRun(item.id);
      if (run.conversation_id) {
        void loadConversation(run.conversation_id);
        return;
      }
    } catch {
      // Fall through to the chat surface if the run is unavailable.
    }
    setCurrentView("chat");
    setIsSidebarOpen(false);
  };

  const openHistoryItem = (item: HistoryItem | SearchItem) => {
    if (item.type === "chat") {
      void loadConversation(item.id);
      return;
    }
    if (item.type === "strategy") {
      setCurrentView("strategies");
      setIsSidebarOpen(false);
      return;
    }
    if (item.type === "collection") {
      setCurrentView("collections");
      setIsSidebarOpen(false);
      return;
    }
    if (item.type === "run") {
      void loadConversationForRun(item);
      return;
    }
    setCurrentView("chat");
    setIsSidebarOpen(false);
  };

  // ── Start new chat ─────────────────────────────────────────────────────────

  const startNewChat = async () => {
    try {
      const { conversation } = await createConversation(i18n.language);
      persistActiveConversationId(conversation.id);
      setConversationId(conversation.id);
      setIsSidebarOpen(false);
      setCurrentView("chat");
      setMessages([]);
      setInputActions([]);
      try {
        const me = await getMe();
        const stage = me.user.onboarding.stage;
        setShowOnboardingGoalCards(
          stage === "language_selection" || stage === "primary_goal_selection",
        );
      } catch {
        setShowOnboardingGoalCards(false);
      }
      void refreshHistory();
      return conversation.id;
    } catch (err) {
      console.error("Failed to start new chat:", err);
      return null;
    }
  };

  const handleTriggerPrompt = async (type: 'strategy' | 'collection', customPrompt?: string) => {
    // 1. Switch view
    setCurrentView("chat");
    setIsSidebarOpen(false);

    // 2. Start new chat
    const newConvId = await startNewChat();
    if (!newConvId) return;

    // 3. Define the localized prompt or use custom
    let prompt: string;
    if (customPrompt) {
      prompt = customPrompt;
    } else {
      const promptKey = type === 'strategy'
        ? 'chat.trigger_create_strategy'
        : 'chat.trigger_create_collection';

      const fallback = type === 'strategy'
        ? 'I want to create a new strategy.'
        : 'I want to create a new collection.';

      prompt = t(promptKey, fallback);
    }

    // 4. Send it
    void handleSend(prompt);
  };

  // ── Send message ───────────────────────────────────────────────────────────

  const handleSend = async (
    text: string,
    mentionsOrAction?: ChatMention[] | ChatActionOption,
    actionArg?: ChatActionOption,
  ) => {
    const trimmed = text.trim();
    if (!trimmed || !conversationId) return;
    const mentions = Array.isArray(mentionsOrAction) ? mentionsOrAction : [];
    const action = Array.isArray(mentionsOrAction) ? actionArg : mentionsOrAction;

    setIsSidebarOpen(false);
    shouldAutoScrollRef.current = true;

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      kind: action?.type ? "action" : "text",
      content: action?.label ?? trimmed,
      mentions,
      selectedAction: action,
    };
    const assistantId = crypto.randomUUID();

    setMessages((prev) => [
      ...consumeResultActionOnMessages(markComposerActionsInactive(prev), action),
      userMsg,
      {
        id: assistantId,
        role: "ai",
        kind: "text",
        content: "",
        contentPresentation:
          action?.type === "show_breakdown" ? "result_breakdown" : undefined,
      },
    ]);
    setInputActions([]);
    setStreamStatus(null);

    const streamInput: string | ChatActionRequest = action?.type
      ? {
          type: action.type,
          label: action.label,
          payload: action.payload,
          presentation: action.presentation,
        }
      : trimmed;

    const handleStreamEvent = (event: ChatStreamEvent) => {
      if (event.event === "stage_start") {
        setStreamStatus(t(`chat.status.${event.data.stage}`) || t('chat.status.preparing'));
      }
      if (event.event === "token") {
        setStreamStatus(null);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `${m.content ?? ""}${event.data.text}` }
              : m,
          ),
        );
      }
      if (event.event === "error") {
        setInputActions([]);
        setStreamStatus(null);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  content: chatStreamErrorText(
                    event.data.detail,
                    t('chat.error_backtest'),
                  ),
                }
              : m,
          ),
        );
      }
      if (event.event === "final") {
        setStreamStatus(null);
        const finalPayload = event.data as typeof event.data & Record<string, unknown>;
        const finalText = event.data.assistant_response ?? event.data.assistant_prompt ?? "";
        const finalStageOutcome = event.data.stage_outcome;
        const savedStrategyId = savedStrategyIdFromFinalPayload(finalPayload);
        if (action?.type === "save_strategy" && savedStrategyId) {
          setMessages((prev) =>
            markResultCardSaved(
              prev,
              resultRunIdFromFinalPayload(finalPayload, action),
              savedStrategyId,
            ),
          );
        }
        if (event.data.confirmation) {
          const confirmation = event.data.confirmation as StrategyConfirmationPayload;
          setInputActions([]);
          setMessages((prev) =>
            normalizeConfirmationHistory(
              prev.map((m) =>
                m.id === assistantId
                  ? {
                      ...m,
                      kind: "strategy_confirmation",
                      content: undefined,
                      confirmation,
                      actions: confirmation.actions ?? [],
                    }
                  : m,
              ),
            ),
          );
        } else if (event.data.run) {
          const run = event.data.run as BacktestRun;
          const baseCard = resultCardFromRun(run);
          const resultActions = hydrateResultActionsForRun(baseCard.actions ?? [], run);
          const card = {
            ...baseCard,
            savedStrategyId: savedStrategyId ?? run.strategy_id ?? null,
            actions: resultActions,
          };
          setInputActions([]);
          setMessages((prev) =>
            normalizeConfirmationHistory(
              prev.map((m) =>
                m.id === assistantId
                  ? {
                    ...m,
                    kind: "strategy_result",
                    content: m.content || finalText || undefined,
                    result: card,
                    actions: resultActions,
                    savedStrategyId: card.savedStrategyId,
                    }
                  : m,
              ),
            ),
          );
        } else if (finalText) {
          setMessages((prev) => {
            const nextMessages = prev.map((m) =>
              m.id === assistantId && !m.content
                ? {
                    ...m,
                    content: finalText,
                    contentPresentation:
                      action?.type === "show_breakdown"
                        ? "result_breakdown"
                        : m.contentPresentation,
                  }
                : m,
            );
            if (
              finalStageOutcome === "await_user_reply" ||
              finalStageOutcome === "needs_clarification"
            ) {
              return supersedeOpenConfirmations(nextMessages);
            }
            return nextMessages;
          });
        }
      }
      if (event.event === "title") {
        setHistoryItems((prev) =>
          prev.map((item) =>
            item.id === event.data.conversation_id
              ? { ...item, title: event.data.title }
              : item
          )
        );
      }
      if (event.event === "done") {
        setStreamStatus(null);
        refreshHistory();
      }
    };

    const streamToConversation = (targetConversationId: string) =>
      streamChatMessage(
        targetConversationId,
        streamInput,
        i18n.language,
        handleStreamEvent,
        action?.type ? [] : mentions,
      );

    try {
      await streamToConversation(conversationId);
    } catch (err: unknown) {
      if (err instanceof ChatStreamError && err.status === 404 && !action?.type) {
        try {
          clearActiveConversationId();
          const { conversation } = await createConversation(i18n.language);
          persistActiveConversationId(conversation.id);
          setConversationId(conversation.id);
          await streamToConversation(conversation.id);
          return;
        } catch (retryErr) {
          err = retryErr;
        }
      }
      setInputActions([]);
      setStreamStatus(null);
      const status = (err as { status?: number }).status;
      const isRateLimit = status === 429;
      const fallbackMessage =
        err instanceof ChatStreamError && err.message
          ? err.message
          : t('chat.error_backtest');
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: isRateLimit
                  ? t('chat.rate_limit_error')
                  : fallbackMessage,
              }
            : m,
        ),
      );
    }
  };

  const handleOnboardingGoalChoice = async (goal: PrimaryGoal) => {
    if (!conversationId) return;
    const isSkip = goal === "surprise_me";
    const hiddenMessage = isSkip ? "__ONBOARDING_SKIP__" : `__ONBOARDING_GOAL__:${goal}`;
    const userCopy = isSkip
      ? t("onboarding.skip", "Skip for now")
      : onboardingChoices.find((choice) => choice.goal === goal)?.title ?? goal;
    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      kind: "text",
      content: userCopy,
    };
    const assistantId = crypto.randomUUID();

    setMessages((prev) => {
      shouldAutoScrollRef.current = true;
      const base = markComposerActionsInactive(prev);
      if (isSkip) {
        return [...base, { id: assistantId, role: "ai", kind: "text", content: "" }];
      }
      return [...base, userMsg, { id: assistantId, role: "ai", kind: "text", content: "" }];
    });
    setStreamStatus(t("chat.status.understanding"));
    setIsSidebarOpen(false);

    try {
      await streamChatMessage(conversationId, hiddenMessage, i18n.language, (event) => {
        if (event.event === "token") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: `${m.content ?? ""}${event.data.text}` }
                : m,
            ),
          );
        }
        if (event.event === "error") {
          setStreamStatus(null);
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? {
                    ...m,
                    content: t('chat.error_backtest'),
                  }
                : m,
            ),
          );
        }
        if (event.event === "done") {
          setStreamStatus(null);
          setShowOnboardingGoalCards(false);
          refreshHistory();
        }
      });
      await patchMe({
        onboarding: {
          stage: "ready",
          language_confirmed: true,
          primary_goal: goal,
          completed: false,
        },
      });

      const prompts = await getStarterPrompts().catch(() => []);
      setStarterActions(prompts.map((p, i) => ({
        id: `starter-${i}`,
        label: p,
        value: p,
      })));
    } catch {
      setStreamStatus(null);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? { ...m, content: t("chat.error_backtest") }
            : m,
        ),
      );
    }
  };

  // ── Action routing ─────────────────────────────────────────────────────────

  const handleRename = async (id: string, newTitle: string, type: string) => {
    try {
      if (type === 'chat') await patchConversation(id, { title: newTitle });
      else if (type === 'strategies') await patchStrategy(id, { name: newTitle });
      else if (type === 'collections') await patchCollection(id, { name: newTitle });

      setHistoryItems((prev) =>
        prev.map((item) => (item.id === id ? { ...item, title: newTitle } : item)),
      );
      setEditingId(null);
    } catch (err) {
      console.error("Failed to rename:", err);
      showToast(t('chat.error_generic'));
    }
  };

  const handleSaveStrategyAction = async (action: ChatActionOption) => {
    if (!conversationId) return;
    const runId = resultActionRunId(action) ?? null;
    const streamInput: ChatActionRequest = {
      type: "save_strategy",
      label: action.label,
      payload: action.payload,
      presentation: action.presentation,
    };

    try {
      setMessages((prev) => markResultCardSaving(prev, runId, true));
      await streamChatMessage(conversationId, streamInput, i18n.language, (event) => {
        if (event.event === "final") {
          const finalPayload = event.data as typeof event.data & Record<string, unknown>;
          const savedStrategyId = savedStrategyIdFromFinalPayload(finalPayload);
          if (savedStrategyId) {
            setMessages((prev) =>
              markResultCardSaved(
                prev,
                resultRunIdFromFinalPayload(finalPayload, action),
                savedStrategyId,
              ),
            );
            showToast(t("chat.saved"));
          } else if (event.data.assistant_response) {
            showToast(event.data.assistant_response);
          }
        }
        if (event.event === "error") {
          showToast(chatStreamErrorText(event.data.detail, t('chat.error_generic')));
        }
        if (event.event === "done") {
          refreshHistory();
        }
      }, []);
    } catch (err: unknown) {
      const message =
        err instanceof ChatStreamError && err.message
          ? err.message
          : t('chat.error_generic');
          showToast(message);
    }
    finally {
      setMessages((prev) => markResultCardSaving(prev, runId, false));
    }
  };

  const handleAction = (action: ChatActionOption) => {
    const value = action.value ?? "";
    if (action.type === "save_strategy") {
      void handleSaveStrategyAction(action);
      return;
    }
    if (collectionsEnabled && value.startsWith("/action:add-to-collection:")) {
      if (action.payload) {
        setCollectionPickerTarget({
          runId: String(action.payload.run_id ?? ""),
          strategyId: action.payload.strategy_id == null ? null : String(action.payload.strategy_id),
          strategyName: String(action.payload.strategy_name ?? "My strategy"),
          symbols: Array.isArray(action.payload.symbols) ? action.payload.symbols.map(String) : [],
          template: String(action.payload.template ?? ""),
          assetClass: (action.payload.asset_class === "crypto" ? "crypto" : "equity"),
        });
        return;
      }
    }
    if (value === "/action:new-chat") {
      void startNewChat();
      return;
    }
    if (collectionsEnabled && value.startsWith("/action:add-to-collection:")) {
      // Format: /action:add-to-collection:<runId>:<strategyId>:<symbols>:<assetClass>
      const parts = value.split(":");
      const runId = parts[2];
      const strategyId = parts[3] || null;
      const symbols = (parts[4] ?? "").split(",").filter(Boolean);
      const assetClass = (parts[5] ?? "equity") as AssetClass;
      // Find the result card title from messages for strategy name
      const resultMsg = messages.find(
        (m) => m.kind === "strategy_result" && m.result,
      );
      const strategyName = resultMsg?.result?.strategyName ?? "My strategy";
      setCollectionPickerTarget({
        runId,
        strategyId,
        strategyName,
        symbols,
        template: "rsi_mean_reversion",
        assetClass,
      });
      return;
    }
    setInputActions(consumeInputAction(action, inputActions));
    void handleSend(action.label || value, action.type ? action : undefined);
  };

  // ── Chat options helpers ───────────────────────────────────────────────────

  const closeChatOptions = () => {
    setShowChatOptions(false);
    setActiveChatOptionsPanel("none");
  };

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (chatOptionsRef.current && !chatOptionsRef.current.contains(event.target as Node)) {
        closeChatOptions();
      }
    }
    if (showChatOptions) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showChatOptions]);

  const handleArchiveChat = async () => {
    if (!conversationId) return;
    try {
      await patchConversation(conversationId, { archived: true });
      showToast(t("common.archived"));
      closeChatOptions();
      void startNewChat();
    } catch {
      showToast(t("common.error_occurred"));
    }
  };

  const handleAddToCollection = () => {
    // Find the latest strategy result in the message list
    const lastStrategyMsg = [...messages].reverse().find(m => m.kind === "strategy_result" && m.result);
    if (lastStrategyMsg?.result) {
      const res = lastStrategyMsg.result;
      setCollectionPickerTarget({
        runId: res.runId ?? "",
        strategyId: res.strategyId ?? null,
        strategyName: res.strategyName,
        symbols: res.symbols ?? [],
        template: res.template ?? "",
        assetClass: res.assetClass ?? "equity",
      });
      closeChatOptions();
    } else {
      showToast(t('chat.error_load'));
    }
  };

  // ── Recent items grouped by type ───────────────────────────────────────────
  const groupedHistory = useMemo(() => {
    const groups: { label: string; items: HistoryItem[] }[] = [];
    const today: HistoryItem[] = [];
    const yesterday: HistoryItem[] = [];
    const last7Days: HistoryItem[] = [];
    const earlier: HistoryItem[] = [];

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
    const yesterdayStart = todayStart - 86400000;
    const last7DaysStart = todayStart - 86400000 * 6;

    historyItems.forEach((item) => {
      const d = new Date(item.created_at).getTime();
      if (d >= todayStart) {
        today.push(item);
      } else if (d >= yesterdayStart) {
        yesterday.push(item);
      } else if (d >= last7DaysStart) {
        last7Days.push(item);
      } else {
        earlier.push(item);
      }
    });

    if (today.length > 0) groups.push({ label: t("chat.history.today"), items: today });
    if (yesterday.length > 0) groups.push({ label: t("chat.history.yesterday"), items: yesterday });
    if (last7Days.length > 0) groups.push({ label: t("chat.history.last_7_days"), items: last7Days });
    if (earlier.length > 0) groups.push({ label: t("chat.history.earlier"), items: earlier });

    return groups;
  }, [historyItems, t]);
  const composerActions = hasActiveArtifactActionSet(messages)
    ? []
    : visibleComposerActions(inputActions);

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="relative flex h-[100dvh] w-full overflow-hidden bg-[#f9f9f9] text-black dark:bg-[#141517] dark:text-white md:flex-row">

      {/* ── Desktop sidebar ── */}
      <aside
        className={`flex flex-col border-r border-black/5 bg-white transition-all duration-300 ease-in-out overflow-x-hidden dark:border-white/5 dark:bg-[#141517] ${ isSidebarOpen ? "w-72" : "w-14" }`}
      >
        {/* Sidebar Header: Brand & Toggle */}
        <div className="flex h-20 items-center px-[6px] pb-4 pt-6 overflow-hidden">
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-full transition-all duration-300 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95"
            aria-label={isSidebarOpen ? "Collapse sidebar" : "Expand sidebar"}
          >
            {isSidebarOpen ? (
              <PanelLeft className="h-5 w-5 text-black/60 dark:text-white/60" />
            ) : (
              <ArgusLogo  className="h-8 w-8 text-black dark:text-white" />
            )}
          </button>
          <span className={`font-display pl-3 text-[22px] font-bold tracking-tight text-black transition-all duration-300 dark:text-white ${ isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
            argus
          </span>
        </div>

        <div className="flex flex-1 flex-col overflow-y-auto overflow-x-hidden px-[6px] pb-4 pt-2">
          {/* Main Navigation */}
          <button
            onClick={() => {
              void startNewChat();
              setIsSidebarOpen(false);
            }}
            className="group mb-2 flex h-11 w-full items-center gap-3 rounded-[14px] px-0 transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5"
          >
            <div className="flex h-11 w-11 items-center justify-center">
              <Plus className="h-5 w-5 text-black/60 transition-colors group-hover:text-black dark:text-white/60 dark:group-hover:text-white" />
            </div>
            <span className={`font-display pl-3 text-[15px] font-medium tracking-tight transition-all duration-300 ${ isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
              {t('chat.new_chat')}
            </span>
          </button>

          <button
            onClick={() => {
              setCurrentView("strategies");
              setIsSidebarOpen(false);
            }}
            className={`group mb-2 flex h-11 w-full items-center gap-3 rounded-[14px] px-0 transition-all duration-200 ${ currentView === "strategies" ? "bg-black/5 dark:bg-white/5" : "hover:bg-black/5 dark:hover:bg-white/5" }`}
          >
            <div className="flex h-11 w-11 items-center justify-center">
              <Compass className="h-[22px] w-[22px] text-black/60 transition-colors group-hover:text-black dark:text-white/60 dark:group-hover:text-white" />
            </div>
            <span className={`font-display pl-3 text-[15px] font-medium tracking-tight transition-all duration-300 ${ isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
              {t('common.strategies')}
            </span>
          </button>

          {collectionsEnabled && (
            <button
              onClick={() => {
                setCurrentView("collections");
                setIsSidebarOpen(false);
              }}
              className={`group mb-6 flex h-11 w-full items-center gap-3 rounded-[14px] px-0 transition-all duration-200 ${ currentView === "collections" ? "bg-black/5 dark:bg-white/5" : "hover:bg-black/5 dark:hover:bg-white/5" }`}
            >
              <div className="flex h-11 w-11 items-center justify-center">
                <Layers className="h-[22px] w-[22px] text-black/60 transition-colors group-hover:text-black dark:text-white/60 dark:group-hover:text-white" />
              </div>
              <span className={`font-display pl-3 text-[15px] font-medium tracking-tight transition-all duration-300 ${ isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
                {t('common.collections')}
              </span>
            </button>
          )}

          {/* History Accordion */}
          <div className="mb-2">
            <button
              onClick={() => setIsRecentsExpanded(!isRecentsExpanded)}
              className="flex h-11 w-full items-center justify-between rounded-[14px] px-0 transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5"
            >
              <div className="flex items-center gap-3">
                <div className="flex h-11 w-11 items-center justify-center">
                  <History className="h-[22px] w-[22px] text-black/60 dark:text-white/60" />
                </div>
                <span className={`font-display pl-3 tracking-tight transition-all duration-300 ${ isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
                  {t('common.recents')}
                </span>
              </div>
              <div className={`pr-4 transition-opacity duration-300 ${ isSidebarOpen ? "block opacity-100" : "hidden opacity-0 pointer-events-none" }`}>
                <ChevronRight className={`h-4 w-4 transition-transform duration-200 ${isRecentsExpanded ? "rotate-90" : ""}`} />
              </div>
            </button>

            {isRecentsExpanded && (
              <div className="space-y-0.5 pb-2">
                {currentView === "chat" && searchText.trim().length > 0 ? (
                  <>
                    {isSearching ? (
                      <div className="px-11 py-4 text-[13px] text-black/45 dark:text-white/45">
                        {t("common.loading")}
                      </div>
                    ) : searchResults.length === 0 ? (
                      <div className="px-11 py-6">
                        <p className={`text-[13px] leading-relaxed text-black/30 transition-all duration-300 dark:text-white/30 ${ isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
                          {t("common.no_items")}
                        </p>
                      </div>
                    ) : (
                      <>
                        {searchResults.map((item) => (
                          <button
                            key={`${item.type}:${item.id}`}
                            onClick={() => openHistoryItem(item)}
                            className="group relative flex w-full items-center gap-3 rounded-[14px] px-0 py-2.5 transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5"
                          >
                            <div className="flex h-6 w-11 flex-shrink-0 items-center justify-center" />
                            <div className={`min-w-0 flex-1 pl-3 pr-4 transition-all duration-300 ${ isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
                              <span className="font-display block truncate text-[15px] font-medium tracking-tight">
                                {item.title}
                              </span>
                              <span className="mt-0.5 block truncate text-[12px] text-black/40 dark:text-white/40">
                                {item.matched_text}
                              </span>
                            </div>
                          </button>
                        ))}
                        {searchNextCursor && (
                          <button
                            type="button"
                            onClick={() => void loadMoreSearch()}
                            disabled={isLoadingMoreSearch}
                            className="mx-11 mt-2 rounded-[12px] border border-black/10 px-3 py-1.5 text-[12px] font-medium text-black/70 hover:bg-black/5 disabled:opacity-50 dark:border-white/10 dark:text-white/70 dark:hover:bg-white/5"
                          >
                            {isLoadingMoreSearch ? t("common.loading") : t("common.retry")}
                          </button>
                        )}
                      </>
                    )}
                  </>
                ) : historyItems.length === 0 ? (
                  <div className="px-11 py-6">
                    <p className={`text-[13px] leading-relaxed text-black/30 transition-all duration-300 dark:text-white/30 ${ isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
                      {t('chat.no_recent_activity')}
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col gap-6 pb-4">
                    {groupedHistory.map((group) => (
                      <div key={group.label} className="flex flex-col">
                        <div className={`px-11 py-2 transition-all duration-300 ${ isSidebarOpen ? "opacity-100" : "opacity-0 invisible h-0 overflow-hidden" }`}>
                          <span className="text-[11px] font-semibold uppercase tracking-wider text-black/40 dark:text-white/40">
                            {group.label}
                          </span>
                        </div>
                        {group.items.map((item) => (
                          <button
                            key={`${item.type}:${item.id}`}
                            onClick={() => openHistoryItem(item)}
                            className={`group relative flex w-full items-center gap-3 rounded-[14px] px-0 py-2.5 transition-all duration-200 ${ item.type === "chat" && conversationId === item.id ? "bg-black/5 dark:bg-white/5" : "hover:bg-black/5 dark:hover:bg-white/5" }`}
                          >
                            <div className="flex h-6 w-11 flex-shrink-0 items-center justify-center" />
                            <div className={`min-w-0 flex-1 pl-3 pr-4 transition-all duration-300 ${ isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
                              <span className="font-display block truncate text-[15px] font-medium tracking-tight">
                                {item.title}
                              </span>
                              <span className="mt-0.5 block text-[12px] text-black/40 dark:text-white/40">
                                {t(`common.${item.type}`, item.type)}
                              </span>
                            </div>
                          </button>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
                {historyNextCursor && currentView === "chat" && searchText.trim().length === 0 && (
                  <button
                    type="button"
                    onClick={() => loadMoreHistory()}
                    disabled={isLoadingMoreHistory}
                    className="mx-11 mt-2 rounded-[12px] border border-black/10 px-3 py-1.5 text-[12px] font-medium text-black/70 hover:bg-black/5 disabled:opacity-50 dark:border-white/10 dark:text-white/70 dark:hover:bg-white/5"
                  >
                    {isLoadingMoreHistory ? t("common.loading") : t("common.retry")}
                  </button>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Search & Settings */}
        <div className="border-t border-black/5 p-[6px] dark:border-white/5">
          <div className="relative mb-4 h-11 overflow-hidden">
            <div className="absolute left-0 top-0 flex h-11 w-11 items-center justify-center">
              <Search className="h-4 w-4 text-black/30 dark:text-white/30" />
            </div>
            <input
              type="text"
              value={searchText}
              onChange={(e) => setSearchText(e.target.value)}
              placeholder={t('common.search')}
              className={`font-display h-11 w-full rounded-[14px] bg-black/[0.03] pl-[62px] pr-4 text-[15px] font-medium outline-none transition-all placeholder:text-black/30 hover:bg-black/[0.05] focus:bg-white focus:ring-1 focus:ring-black/5 dark:bg-white/[0.03] dark:placeholder:text-white/30 dark:hover:bg-white/[0.05] dark:focus:bg-[#1f2225] dark:focus:ring-white/5 ${ isSidebarOpen ? "block" : "hidden" }`}
            />
          </div>

          <button
            onClick={() => {
              setCurrentView("settings");
            }}
            className={`group flex h-11 w-full items-center gap-3 rounded-[14px] px-0 transition-all duration-200 ${ currentView === "settings" ? "bg-black/5 dark:bg-white/5" : "hover:bg-black/5 dark:hover:bg-white/5" }`}
          >
            <div className="flex h-11 w-11 items-center justify-center">
              <Settings className="h-5 w-5 text-black/60 transition-colors group-hover:text-black dark:text-white/60 dark:group-hover:text-white" />
            </div>
            <span className={`font-display pl-3 text-[15px] font-medium tracking-tight transition-all duration-300 ${ isSidebarOpen ? "opacity-100" : "absolute left-[72px] opacity-0 pointer-events-none" }`}>
              {t('common.settings')}
            </span>
          </button>
        </div>
      </aside>

      {/* ── Main panel ── */}
      <section
        className="relative z-10 flex h-full flex-1 flex-col overflow-hidden bg-[#f9f9f9] dark:bg-[#141517]"
      >
        {/* ── Unified View Header (SOTA: Absolute to content panel for perfect centering) ── */}
        {currentView !== "settings" && (
          <header className="absolute inset-x-0 top-0 z-[50] flex h-20 items-center justify-between px-4 pointer-events-none md:px-8">
          {/* Empty space for sidebar toggle alignment balance */}
          <div className="w-11 md:w-32" />

          {/* Title (Always Centered relative to Content) */}
          <h1 className="font-display pointer-events-auto text-[17px] font-semibold tracking-tight text-black/80 dark:text-white/80 md:text-[18px]">
            {currentView === "chat" && (messages.length > 0 ? t('common.conversation', 'Conversation') : t('chat.new_chat'))}
            {currentView === "strategies" && t('common.strategies')}
            {currentView === "collections" && t('common.collections')}
          </h1>

          {/* Action Button (Always Right-Anchored) */}
          <div className="flex w-11 justify-end pointer-events-auto md:w-32">
            {currentView === "chat" && (
              <div className="relative" ref={chatOptionsRef}>
                <button
                  type="button"
                  onClick={() => setShowChatOptions(!showChatOptions)}
                  className="flex h-11 w-11 items-center justify-center rounded-full transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95"
                  aria-label="Chat options"
                >
                  <History className="h-5 w-5" />
                </button>
                {showChatOptions && (
                  <div className="fixed inset-x-0 bottom-0 z-50 rounded-t-[28px] border-t border-black/5 bg-white pb-7 pt-2 dark:border-white/5 dark:bg-[#1f2225] md:absolute md:bottom-auto md:right-0 md:left-auto md:top-full md:mt-2 md:w-[260px] md:rounded-[20px] md:border md:pb-2">
                    <div className="mx-auto my-3 h-1.5 w-12 rounded-full bg-black/10 dark:bg-white/10 md:hidden" />
                    {activeChatOptionsPanel === "none" && (
                      <div className="py-1">
                        <button
                          type="button"
                          onClick={() => { closeChatOptions(); void startNewChat(); }}
                          className="flex w-full items-center gap-4 px-6 py-4 text-left text-[16px] font-medium transition-colors hover:bg-black/5 dark:hover:bg-white/5 md:px-5 md:py-3 md:text-[15px]"
                        >
                          <Plus className="h-[18px] w-[18px] text-black/60 dark:text-white/60 md:h-4 md:w-4" />
                          {t('chat.new_chat')}
                        </button>
                        {collectionsEnabled && (
                          <button
                            type="button"
                            onClick={handleAddToCollection}
                            className="flex w-full items-center gap-4 px-6 py-4 text-left text-[16px] font-medium transition-colors hover:bg-black/5 dark:hover:bg-white/5 md:px-5 md:py-3 md:text-[15px]"
                          >
                            <Layers className="h-[18px] w-[18px] text-black/60 dark:text-white/60 md:h-4 md:w-4" />
                            {t('common.add_to_collection')}
                          </button>
                        )}
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); setActiveChatOptionsPanel("history"); }}
                          className="group flex w-full items-center justify-between px-6 py-4 text-left text-[16px] font-medium transition-colors hover:bg-black/5 dark:hover:bg-white/5 md:px-5 md:py-3 md:text-[15px]"
                        >
                          <span className="flex items-center gap-4">
                            <History className="h-[18px] w-[18px] text-black/60 dark:text-white/60 md:h-4 md:w-4" />
                            {t('chat.view_history')}
                          </span>
                          <ChevronRight className="h-4 w-4 text-black/30 dark:text-white/30 transition-transform group-hover:translate-x-0.5" />
                        </button>
                        <div className="my-1 h-px bg-black/5 dark:bg-white/5" />
                        <button
                          type="button"
                          onClick={() => {
                            if (!conversationId) return;
                            deleteConversation(conversationId)
                              .then(() => {
                                showToast(t('common.delete'));
                                refreshHistory();
                                void startNewChat();
                                closeChatOptions();
                              })
                              .catch(() => showToast(t('common.error_occurred')));
                          }}
                          className="flex w-full items-center gap-4 px-6 py-4 text-left text-[16px] font-medium text-red-500 transition-colors hover:bg-red-50 dark:hover:bg-red-500/10 md:px-5 md:py-3 md:text-[15px]"
                        >
                          <Trash2 className="h-[18px] w-[18px] md:h-4 md:w-4" />
                          {t('chat.delete_chat')}
                        </button>
                      </div>
                    )}
                    {activeChatOptionsPanel === "history" && (
                      <div className="py-1">
                        <button
                          type="button"
                          onClick={() => setActiveChatOptionsPanel("none")}
                          className="flex w-full items-center justify-between px-6 py-3 text-left text-[13px] font-medium text-black/60 transition-colors hover:text-black dark:text-white/60 dark:hover:text-white md:px-5"
                        >
                          {t('chat.past_sessions')}
                          <ChevronRight className="h-4 w-4 -rotate-90" />
                        </button>
                        <div className="max-h-[300px] overflow-y-auto pb-1">
                          {historyItems.filter(i => i.type === "chat").map((item: HistoryItem) => (
                            <button
                              key={item.id}
                              type="button"
                              onClick={() => {
                                void loadConversation(item.id);
                                closeChatOptions();
                              }}
                              className="flex w-full flex-col px-6 py-4 text-left transition-colors hover:bg-black/5 dark:hover:bg-white/5 md:px-5 md:py-3"
                            >
                              <span className="truncate text-[15px] font-medium">{item.title}</span>
                              <span className="mt-1 truncate text-[13px] text-black/45 dark:text-white/45">{item.subtitle}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
            {(currentView === "strategies" || currentView === "collections") && (
              <button
                onClick={() => handleTriggerPrompt(currentView === "strategies" ? "strategy" : "collection")}
                className="flex h-11 w-11 items-center justify-center rounded-full transition-all duration-200 hover:bg-black/5 dark:hover:bg-white/5 active:scale-95"
                aria-label="New item"
              >
                <Plus className="h-5 w-5" />
              </button>
            )}
          </div>
          </header>
        )}
        {/* ── Chat view ── */}
        {currentView === "chat" && (
          <div className="relative mx-auto flex h-[100dvh] w-full max-w-5xl flex-col">

            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-start px-4 pt-[35vh]">
                <h1 className="font-display mb-8 text-[40px] font-medium tracking-tight text-black dark:text-white">
                  argus
                </h1>

                <div className="w-full max-w-2xl">
                  <ChatInput onSend={handleSend} />
                </div>

                {showOnboardingGoalCards && (
                  <div
                    className="mt-6 w-full max-w-2xl"
                    data-testid="onboarding-goal-cards"
                  >
                    <p className="mb-3 text-center text-[14px] text-black/60 dark:text-white/60">
                      {t(
                        "onboarding.prompt",
                        "What is your current primary goal? Don't worry, you can change it later.",
                      )}
                    </p>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {onboardingChoices.map((choice) => (
                        <button
                          key={choice.goal}
                          type="button"
                          data-testid={`onboarding-goal-${choice.goal}`}
                          onClick={() => handleOnboardingGoalChoice(choice.goal)}
                          className="rounded-[14px] border border-black/10 bg-white/70 px-3 py-3 text-left transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/70 dark:hover:bg-white/5"
                        >
                          <p className="text-[14px] font-medium text-black dark:text-white">
                            {choice.title}
                          </p>
                          <p className="mt-1 text-[12px] text-black/55 dark:text-white/55">
                            {choice.description}
                          </p>
                        </button>
                      ))}
                    </div>
                    <div className="mt-2 flex justify-center">
                      <button
                        type="button"
                        data-testid="onboarding-skip"
                        onClick={() => handleOnboardingGoalChoice("surprise_me")}
                        className="text-[13px] font-medium text-black/55 underline-offset-2 transition-colors hover:text-black hover:underline dark:text-white/55 dark:hover:text-white"
                      >
                        {t("onboarding.skip", "Skip for now")}
                      </button>
                    </div>
                  </div>
                )}

                {/* Show/Hide Suggestions Toggle */}
                <div className="mt-4">
                  <button
                    onClick={() => setShowSuggestions(!showSuggestions)}
                    className="text-[14px] font-medium text-black/60 transition-colors hover:text-black dark:text-white/60 dark:hover:text-white"
                  >
                    {showSuggestions ? t('chat.hide_suggestions') : t('chat.show_suggestions')}
                  </button>
                </div>

                <div className={`mt-6 w-full flex flex-col items-center transition-all duration-500 ease-in-out overflow-hidden ${ showSuggestions ? 'max-h-[600px] opacity-100' : 'max-h-0 opacity-0 pointer-events-none' }`}>
                  {/* Starter Actions / Chips */}
                  <div className="flex flex-wrap items-center justify-center gap-3">
                      <button
                        onClick={() => handleSend(t('chat.starter_actions.tsla.value', 'Show me TSLA analysis'))}
                        className="flex items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5"
                      >
                        <TrendingUp className="h-4 w-4 text-black/60 dark:text-white/60" />
                        {t('chat.starter_actions.tsla.label', 'TSLA Analysis')}
                      </button>
                      <button
                        onClick={() => handleSend(t('chat.starter_actions.btc.value', 'Show me BTC trends'))}
                        className="flex items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5"
                      >
                        <Bitcoin className="h-4 w-4 text-black/60 dark:text-white/60" />
                        {t('chat.starter_actions.btc.label', 'BTC Trends')}
                      </button>
                      <button
                        onClick={() => handleSend(t('chat.starter_actions.dca.value', 'Explain DCA strategy'))}
                        className="flex items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5"
                      >
                        <LineChart className="h-4 w-4 text-black/60 dark:text-white/60" />
                        {t('chat.starter_actions.dca.label', 'DCA Strategy')}
                      </button>
                    </div>

                    {/* Example Questions */}
                    <div className="mt-12 flex flex-col items-center gap-4 text-center">
                      <button onClick={() => handleSend(t('chat.example_queries.q1', 'What if I bought Apple whenever it dipped hard?'))} className="text-[14px] text-black/50 hover:text-black hover:underline dark:text-white/50 dark:hover:text-white transition-colors">
                        {t('chat.example_queries.q1', 'What if I bought Apple whenever it dipped hard?')}
                      </button>
                      <button onClick={() => handleSend(t('chat.example_queries.q2', 'Test a momentum breakout strategy on Bitcoin.'))} className="text-[14px] text-black/50 hover:text-black hover:underline dark:text-white/50 dark:hover:text-white transition-colors">
                        {t('chat.example_queries.q2', 'Test a momentum breakout strategy on Bitcoin.')}
                      </button>
                      <button onClick={() => handleSend(t('chat.example_queries.q3', 'How would a simple DCA strategy perform on Tesla?'))} className="text-[14px] text-black/50 hover:text-black hover:underline dark:text-white/50 dark:hover:text-white transition-colors">
                        {t('chat.example_queries.q3', 'How would a simple DCA strategy perform on Tesla?')}
                      </button>
                    </div>
                  </div>
                </div>
            ) : (
              <>
                <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-32 bg-[#f9f9f9]/80 backdrop-blur-[0.8px] [mask-image:linear-gradient(to_bottom,black_48%,transparent_100%)] dark:bg-[#141517]/80" />

                {/* Messages */}
                <div
                  ref={scrollContainerRef}
                  onScroll={updateScrollPositionState}
                  className="argus-scrollbar flex-1 overflow-y-auto px-4 pb-[126px] pt-[86px]"
                >
                  <div className="space-y-8">
                    {messages.map((msg, index) => {
                      const latestAiIndex = messages.findLastIndex((m) => m.role === "ai");
                      const isLatestAi = msg.role === "ai" && latestAiIndex === index;
                      const isWorkingMessage =
                        isLatestAi &&
                        msg.kind === "text" &&
                        (!!streamStatus || (msg.content ?? "") === "");
                      return (
                        <ChatMessage
                          key={msg.id}
                          message={msg}
                          onAction={handleAction}
                          onFeedback={(type, context, rating) => {
                            setFeedbackState({ isOpen: true, type, context, rating });
                            setIsSidebarOpen(false);
                          }}
                          isLatest={isLatestAi}
                          isStreaming={isWorkingMessage}
                        />
                      );
                    })}
                    {streamStatus && (
                      <div className="ml-12">
                        <span className="animate-ethereal-shimmer text-[13px] text-black/45 dark:text-white/45">
                          {streamStatus}
                        </span>
                      </div>
                    )}
                    <div ref={bottomRef} />
                  </div>
                </div>

                {/* Input fade + bar */}
                <div className="pointer-events-none absolute bottom-0 inset-x-0 z-10 h-40 bg-[#f9f9f9]/80 backdrop-blur-[0.8px] [mask-image:linear-gradient(to_top,black_50%,transparent_100%)] dark:bg-[#141517]/80" />
                <div className="pointer-events-none absolute bottom-6 inset-x-0 z-20 px-4">
                  <div className="pointer-events-auto mx-auto max-w-3xl rounded-full">
                    {showJumpToLatest && (
                      <div className="mb-3 flex justify-center">
                        <button
                          type="button"
                          aria-label="Jump to latest"
                          onClick={() => scrollToLatest("smooth")}
                          className="flex h-11 w-11 items-center justify-center rounded-full border border-black/10 bg-white/90 text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1d2023]/95 dark:text-white dark:hover:bg-white/6"
                        >
                          <ArrowDown className="h-4 w-4" />
                        </button>
                      </div>
                    )}
                    {composerActions.length > 0 && !streamStatus && (
                      <div className="mb-3 flex flex-wrap justify-center gap-2 animate-in fade-in slide-in-from-bottom-2 duration-300">
                        {composerActions.map((action) => (
                          <button
                            key={action.id ?? action.type ?? action.label}
                            type="button"
                            onClick={() => handleAction(action)}
                            className="min-h-11 rounded-full border border-black/10 bg-white/90 px-4 py-2 text-[14px] font-medium tracking-tight text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1d2023]/95 dark:text-white dark:hover:bg-white/6"
                          >
                            {action.label}
                          </button>
                        ))}
                      </div>
                    )}
                    <ChatInput onSend={handleSend} />
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {currentView === "strategies" && (
          <StrategiesView
            onMenuClick={() => setIsSidebarOpen((o) => !o)}
            onAddClick={() => handleTriggerPrompt('strategy')}
            searchText={searchText}
            onSearchChange={setSearchText}
            isSidebarOpen={isSidebarOpen}
            onTriggerPrompt={handleTriggerPrompt}
          />
        )}
        {collectionsEnabled && currentView === "collections" && (
          <CollectionsView
            onMenuClick={() => setIsSidebarOpen((o) => !o)}
            onAddClick={() => handleTriggerPrompt('collection')}
            searchText={searchText}
            onSearchChange={setSearchText}
            isSidebarOpen={isSidebarOpen}
            onTriggerPrompt={handleTriggerPrompt}
          />
        )}
        {currentView === "settings" && (
          <SettingsView
            onClose={() => setCurrentView("chat")}
            onLogout={() => {
              window.location.href = "/";
            }}
            onFeedback={(type, context) => {
              setFeedbackState({ isOpen: true, type, context });
              setIsSidebarOpen(false);
            }}
          />
        )}
      </section>

      {/* ── Collection picker sheet ── */}
      {collectionsEnabled && collectionPickerTarget && (
        <CollectionPicker
          strategyId={collectionPickerTarget.strategyId}
          strategyFallback={{
            name: collectionPickerTarget.strategyName,
            template: collectionPickerTarget.template,
            asset_class: collectionPickerTarget.assetClass,
            symbols: collectionPickerTarget.symbols,
          }}
          onClose={() => setCollectionPickerTarget(null)}
          onSuccess={(collectionName) => {
            setCollectionPickerTarget(null);
            showToast(t('chat.added_to_collection', { name: collectionName }));
          }}
        />
      )}

      {/* ── Feedback Dialog ── */}
      <FeedbackDialog
        isOpen={feedbackState.isOpen}
        onClose={() => setFeedbackState((s) => ({ ...s, isOpen: false }))}
        type={feedbackState.type}
        rating={feedbackState.rating}
        context={feedbackState.context}
      />

      {/* ── Toast ── */}
      {toast && (
        <div className="fixed bottom-24 left-1/2 z-[100] -translate-x-1/2 animate-in fade-in slide-in-from-bottom-2 duration-300 rounded-full bg-black dark:bg-white px-5 py-2.5 text-[14px] font-medium text-white dark:text-black">
          {toast}
        </div>
      )}
    </div>
  );
}
