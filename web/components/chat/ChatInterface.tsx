"use client";

import { useCallback, useMemo, useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ChevronRight,
  History,
  Plus,
  Trash2,
  TrendingUp,
  Bitcoin,
  LineChart,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import ChatCommandPalette from "@/components/sidebar/ChatCommandPalette";
import ChatSidebar, { type SidebarMode } from "@/components/sidebar/ChatSidebar";
import SidebarPreferenceModal from "@/components/settings/SidebarPreferenceModal";

import {
  createConversation,
  deleteConversation,
  getBacktestRun,
  getMe,
  getConversationMessages,
  listConversations,
  listHistory,
  logoutFromApi,
  patchMe,
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
import {
  chatExploratorySuggestionsEnabled,
  collectionsEnabled,
  omnisearchEnabled,
  privateAlphaOnboardingEnabled,
  strategiesEnabled,
} from "@/lib/private-alpha-flags";
import {
  conversationLoadRetryActionFromConversationId,
  failedActionRetryActionFromMetadata,
  hasFailedActionMetadata,
  isRetryAction,
  retryLastTurnActionFromMessage,
  retryLastTurnFailedAssistantIdFromAction,
  retryLastTurnMessageFromAction,
  retryLoadConversationIdFromAction,
} from "@/lib/chat-retry-actions";
import {
  activeConversationRouteStateFromUrl,
  shouldStartConversationForVisibleEmptyChat,
  type ActiveConversationRouteState,
} from "@/lib/chat-conversation-routing";
import { mergeFinalTextMessage } from "@/lib/chat-final-message";
import { hydrateTextMessageFromApi } from "@/lib/chat-message-hydration";
import { appendOrReplacePendingAssistantMessage } from "@/lib/chat-send-state";
import SettingsView from "../views/SettingsView";
import StrategiesView from "../views/StrategiesView";
import ChatInput from "./ChatInput";
import ChatMessage from "./ChatMessage";
import FeedbackDialog from "../feedback/FeedbackDialog";
import { type ChatActionOption, type ChatMention, type Message, type StrategyConfirmationPayload } from "./types";
import {
  applyConsumedResultActions,
  applyConfirmationActionEffects,
  confirmationActionEffectFromAction,
  confirmationActionEffectsFromApi,
  consumeResultActionOnMessages,
  consumedResultActionsFromApi,
  hiddenSaveActionMessageIdsFromApi,
  isBreakdownActionMetadata,
  normalizeConfirmationHistory,
  resultActionRunId,
  settleOpenConfirmationsAfterTextFinal,
} from "./artifact-history";

// ─── Constants ────────────────────────────────────────────────────────────────

type View = "chat" | "strategies" | "settings";
type SendOptions = {
  renderUserMessage?: boolean;
  replacementAssistantId?: string;
};
type OnboardingChoice = {
  goal: PrimaryGoal;
  title: string;
  description: string;
};

const JUMP_TO_LATEST_THRESHOLD_PX = 240;
const ACTIVE_CONVERSATION_STORAGE_KEY = "argus.activeConversationId";
const ACTIVE_CONVERSATION_QUERY_KEY = "conversation";
const POST_TURN_TITLE_REFRESH_DELAYS_MS = [0, 1500, 5000, 9000, 13000];

type HydratedMessages = {
  messages: Message[];
  inputActions: ChatActionOption[];
};

function readActiveConversationId() {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY);
  } catch {
    return null;
  }
}

function readActiveConversationRouteState(): ActiveConversationRouteState {
  if (typeof window === "undefined") {
    return {
      conversationId: null,
      isChatRoute: false,
      isNewChatRoute: false,
    };
  }
  try {
    return activeConversationRouteStateFromUrl(
      window.location.href,
      ACTIVE_CONVERSATION_QUERY_KEY,
    );
  } catch {
    return {
      conversationId: null,
      isChatRoute: false,
      isNewChatRoute: false,
    };
  }
}

function readActiveConversationIdFromUrl() {
  return readActiveConversationRouteState().conversationId;
}

function persistActiveConversationId(conversationId: string) {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, conversationId);
  } catch {
    // Storage can be unavailable in restricted browser contexts.
  }
}

function persistActiveConversationRoute(conversationId: string) {
  if (typeof window === "undefined") return;
  try {
    const url = new URL(window.location.href);
    if (url.pathname !== "/chat") return;
    if (url.searchParams.get(ACTIVE_CONVERSATION_QUERY_KEY) === conversationId) {
      return;
    }
    url.searchParams.set(ACTIVE_CONVERSATION_QUERY_KEY, conversationId);
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}`);
  } catch {
    // URL state is a convenience for reload recovery; chat still works without it.
  }
}

function rememberActiveConversationId(conversationId: string) {
  persistActiveConversationId(conversationId);
  persistActiveConversationRoute(conversationId);
}

function clearActiveConversationId() {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.removeItem(ACTIVE_CONVERSATION_STORAGE_KEY);
  } catch {
    // Storage can be unavailable in restricted browser contexts.
  }
}

function clearActiveConversationRoute() {
  if (typeof window === "undefined") return;
  try {
    const url = new URL(window.location.href);
    if (url.pathname !== "/chat") return;
    if (!url.searchParams.has(ACTIVE_CONVERSATION_QUERY_KEY)) return;
    url.searchParams.delete(ACTIVE_CONVERSATION_QUERY_KEY);
    const query = url.searchParams.toString();
    window.history.replaceState(
      window.history.state,
      "",
      query ? `${url.pathname}?${query}` : url.pathname,
    );
  } catch {
    // URL state is optional recovery metadata.
  }
}

function clearActiveConversationPointer() {
  clearActiveConversationId();
  clearActiveConversationRoute();
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
  return (latestAi?.actions ?? []).filter(
    (action) =>
      action.type !== "save_strategy" &&
      action.artifactType !== "failed_action",
  );
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

const CONFIRMATION_ACTION_TYPES = new Set<NonNullable<ChatActionOption["type"]>>([
  "run_backtest",
  "change_dates",
  "change_asset",
  "adjust_assumptions",
  "cancel_confirmation",
]);

function isCardScopedAction(action: ChatActionOption) {
  return Boolean(action.type && CARD_SCOPED_ACTION_TYPES.has(action.type));
}

function isConfirmationAction(action: ChatActionOption | undefined) {
  return Boolean(action?.type && CONFIRMATION_ACTION_TYPES.has(action.type));
}

function actionHasCardScopedOwnership(action: ChatActionOption) {
  return isCardScopedAction(action) || action.presentation === "confirmation" || action.presentation === "result";
}

function visibleInputActions(actions: ChatActionOption[]) {
  return actions.filter((action) => action.type !== "save_strategy");
}

function visibleComposerActions(actions: ChatActionOption[]) {
  return visibleInputActions(actions).filter((action) => !isCardScopedAction(action));
}

function isFailedActionRetry(action: ChatActionOption | undefined) {
  if (!action) return false;
  return action.type === "retry_failed_action" || action.artifactType === "failed_action";
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

function consumeInputAction(action: ChatActionOption, actions: ChatActionOption[]) {
  if (action.type === "show_breakdown") {
    return actions.filter((candidate) => candidate.type !== "show_breakdown");
  }
  return [];
}

function resultActionRequiresRunContext(action: ChatActionOption) {
  return (
    action.type === "show_breakdown" ||
    action.type === "save_strategy" ||
    action.type === "refine_strategy"
  );
}

function consumeConfirmationActionOnMessages(
  messages: Message[],
  action: ChatActionOption | undefined,
): Message[] {
  const effect = confirmationActionEffectFromAction(action);
  if (!effect) {
    return messages;
  }
  return applyConfirmationActionEffects(messages, [effect]);
}

function hasResultActionContext(runId: string | undefined, conversationId: string | undefined) {
  return Boolean(runId && conversationId);
}

function historyItemBelongsToConversation(
  item: HistoryItem,
  targetConversationId: string,
) {
  return item.id === targetConversationId || item.conversation_id === targetConversationId;
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
  const confirmationActionEffects = confirmationActionEffectsFromApi(items);
  const hiddenMessageIds = new Set([
    ...hiddenSaveActionMessageIdsFromApi(items),
    ...confirmationActionEffects.hiddenMessageIds,
  ]);
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

  const normalized = applyConsumedResultActions(
    applyConfirmationActionEffects(
      normalizeConfirmationHistory(messages),
      confirmationActionEffects.effects,
    ),
    consumedResultActions,
  );
  return { messages: normalized, inputActions: latestInputActions(normalized) };
}

function chatStreamErrorText(detail: string | undefined, fallback: string) {
  return detail || fallback;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function ChatInterface() {
  const { t, i18n } = useTranslation();

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
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [searchOverlayOpen, setSearchOverlayOpen] = useState(false);
  const [showChatOptions, setShowChatOptions] = useState(false);
  const [activeChatOptionsPanel, setActiveChatOptionsPanel] = useState<
    "none" | "history"
  >("none");
  const [searchText, setSearchText] = useState("");
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [historyNextCursor, setHistoryNextCursor] = useState<string | null>(null);
  const [isLoadingMoreHistory, setIsLoadingMoreHistory] = useState(false);
  const [isStreamingResponse, setIsStreamingResponse] = useState(false);
  const [isHydratingConversation, setIsHydratingConversation] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [showOnboardingGoalCards, setShowOnboardingGoalCards] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [isRecentsExpanded, setIsRecentsExpanded] = useState(true);
  const [feedbackState, setFeedbackState] = useState<{
    isOpen: boolean;
    type: "bug" | "feature" | "general" | "rating";
    rating?: "positive" | "negative";
    context?: Record<string, unknown>;
  }>({ isOpen: false, type: "general" });
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>("collapsed");
  const [isSidebarPreferenceModalOpen, setIsSidebarPreferenceModalOpen] = useState(false);

  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const chatOptionsRef = useRef<HTMLDivElement>(null);
  const postTurnHistoryRefreshTimersRef = useRef<number[]>([]);
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

  const loadHistoryPage = useCallback(async (nextCursor?: string | null, append = false) => {
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
  }, []);

  // ── History ────────────────────────────────────────────────────────────────

  /** Imperative refresh — safe to call from event handlers */
  const refreshHistory = useCallback(() => {
    loadHistoryPage(null, false).catch(() => undefined);
  }, [loadHistoryPage]);

  function clearPostTurnHistoryRefreshTimers() {
    for (const timerId of postTurnHistoryRefreshTimersRef.current) {
      window.clearTimeout(timerId);
    }
    postTurnHistoryRefreshTimersRef.current = [];
  }

  function schedulePostTurnHistoryRefresh(targetConversationId?: string | null) {
    clearPostTurnHistoryRefreshTimers();
    let settled = false;

    const refreshAndCheckTitle = async () => {
      if (settled) return;
      try {
        await loadHistoryPage(null, false);
        if (!targetConversationId) return;
        const { items } = await listConversations({ limit: 50 });
        const conversation = items.find((item) => item.id === targetConversationId);
        if (
          conversation?.title_source === "ai_generated" ||
          conversation?.title_source === "user_renamed"
        ) {
          settled = true;
          await loadHistoryPage(null, false);
        }
      } catch {
        // Title/sidebar refresh is fail-open; later scheduled attempts can still pick it up.
      }
    };

    for (const delay of POST_TURN_TITLE_REFRESH_DELAYS_MS) {
      const timerId = window.setTimeout(() => {
        void refreshAndCheckTitle().catch(() => undefined);
      }, delay);
      postTurnHistoryRefreshTimersRef.current.push(timerId);
    }
  }

  const loadMoreHistory = () => {
    if (!historyNextCursor || isLoadingMoreHistory) return;
    setIsLoadingMoreHistory(true);
    loadHistoryPage(historyNextCursor, true)
      .catch(() => undefined)
      .finally(() => setIsLoadingMoreHistory(false));
  };

  useEffect(() => {
    loadHistoryPage(null, false).catch(() => undefined);
  }, [loadHistoryPage]);

  useEffect(
    () => () => {
      for (const timerId of postTurnHistoryRefreshTimersRef.current) {
        window.clearTimeout(timerId);
      }
      postTurnHistoryRefreshTimersRef.current = [];
    },
    [],
  );

  useEffect(() => {
    if (!isSidebarOpen) {
      setIsRecentsExpanded(false);
    }
  }, [isSidebarOpen]);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem("argus:sidebar_mode") as SidebarMode | null;
      if (saved === "expanded" || saved === "collapsed" || saved === "hover") {
        setSidebarMode(saved);
        setIsSidebarOpen(saved === "expanded");
      }
    } catch {
      // Local preferences are optional.
    }
  }, []);

  useEffect(() => {
    if (!omnisearchEnabled) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "k") {
        return;
      }
      event.preventDefault();
      setSearchOverlayOpen(true);
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!strategiesEnabled && currentView === "strategies") {
      setCurrentView("chat");
    }
  }, [currentView]);

  const handleSetSidebarMode = (mode: SidebarMode) => {
    setSidebarMode(mode);
    try {
      window.localStorage.setItem("argus:sidebar_mode", mode);
    } catch {
      // Local preferences are optional.
    }
    if (mode === "expanded") setIsSidebarOpen(true);
    if (mode === "collapsed" || mode === "hover") setIsSidebarOpen(false);
  };

  const toggleSidebar = () => {
    setIsSidebarOpen((open) => !open);
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
        const activeConversationId = readActiveConversationIdFromUrl() ?? readActiveConversationId();
        if (activeConversationId) {
          try {
            const { items } = await getConversationMessages(activeConversationId, 50);
            if (cancelled) return;
            const hydrated = hydrateMessagesFromApi(items);
            rememberActiveConversationId(activeConversationId);
            setConversationId(activeConversationId);
            setMessages(hydrated.messages);
            setInputActions(hydrated.inputActions);
            setShowOnboardingGoalCards(
              privateAlphaOnboardingEnabled &&
              hydrated.messages.length === 0
              && (stage === "language_selection" || stage === "primary_goal_selection"),
            );

            return;
          } catch {
            clearActiveConversationPointer();
          }
        }

        const { conversation } = await createConversation(resolvedLanguage);
        if (cancelled) return;
        rememberActiveConversationId(conversation.id);
        setConversationId(conversation.id);
        setMessages([]);
        setShowOnboardingGoalCards(
          privateAlphaOnboardingEnabled &&
          (stage === "language_selection" || stage === "primary_goal_selection"),
        );

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
    // Bootstraps the active conversation once; re-running on i18n updates would create noisy chat reloads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
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
    rememberActiveConversationId(convId);
    setConversationId(convId);
    setStreamStatus(t('common.loading'));
    setIsHydratingConversation(true);
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
          actions: [
            conversationLoadRetryActionFromConversationId(convId),
          ].filter((action): action is ChatActionOption => Boolean(action)),
        },
      ]);
    } finally {
      setStreamStatus(null);
      setIsHydratingConversation(false);
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
    if (strategiesEnabled && item.type === "strategy") {
      setCurrentView("strategies");
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

  const startNewChat = useCallback(async () => {
    try {
      const { conversation } = await createConversation(i18n.language);
      rememberActiveConversationId(conversation.id);
      setConversationId(conversation.id);
      setIsSidebarOpen(false);
      setCurrentView("chat");
      setMessages([]);
      setInputActions([]);
      try {
        const me = await getMe();
        const stage = me.user.onboarding.stage;
        setShowOnboardingGoalCards(
          privateAlphaOnboardingEnabled &&
          (stage === "language_selection" || stage === "primary_goal_selection"),
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
  }, [i18n.language, refreshHistory]);

  const handleConversationRemoved = useCallback((removedConversationId: string) => {
    setHistoryItems((prev) =>
      prev.filter((item) => !historyItemBelongsToConversation(item, removedConversationId)),
    );
    refreshHistory();
    if (removedConversationId !== conversationId) return;
    void startNewChat();
  }, [conversationId, refreshHistory, startNewChat]);

  const handleTriggerPrompt = async (_type: 'strategy', customPrompt?: string) => {
    // 1. Switch view
    setCurrentView("chat");
    setIsSidebarOpen(false);

    // 2. Start new chat
    const newConvId = await startNewChat();
    if (!newConvId) return;

    // 3. Define the localized prompt or use custom
    const prompt = customPrompt ?? t(
      'chat.trigger_create_strategy',
      'I want to create a new strategy.',
    );

    // 4. Send it
    void handleSend(prompt);
  };

  // ── Send message ───────────────────────────────────────────────────────────

  const handleSend = async (
    text: string,
    mentionsOrAction?: ChatMention[] | ChatActionOption,
    actionArg?: ChatActionOption,
    options?: SendOptions,
  ) => {
    const trimmed = text.trim();
    if (!trimmed) return;
    if (isStreamingResponse) return;
    const mentions = Array.isArray(mentionsOrAction) ? mentionsOrAction : [];
    const action = Array.isArray(mentionsOrAction) ? actionArg : mentionsOrAction;
    const replacementAssistantId = options?.replacementAssistantId?.trim() || undefined;
    const routeState = readActiveConversationRouteState();
    let targetConversationId = routeState.conversationId ?? conversationId;
    const shouldCreateNewRouteConversation = shouldStartConversationForVisibleEmptyChat({
      routeState,
      visibleMessageCount: messages.length,
      hasStructuredAction: Boolean(action?.type),
    });
    let shouldResetMessagesForNewConversation = false;

    if (shouldCreateNewRouteConversation) {
      try {
        const { conversation } = await createConversation(i18n.language);
        targetConversationId = conversation.id;
        shouldResetMessagesForNewConversation = true;
        rememberActiveConversationId(conversation.id);
        setConversationId(conversation.id);
        void refreshHistory();
      } catch (err) {
        console.error("Failed to start conversation before sending:", err);
        showToast(t('chat.error_generic'));
        return;
      }
    }

    if (!targetConversationId) return;

    if (targetConversationId !== conversationId) {
      rememberActiveConversationId(targetConversationId);
      setConversationId(targetConversationId);
    }

    setIsSidebarOpen(false);
    shouldAutoScrollRef.current = true;
    const renderUserMessage = options?.renderUserMessage ?? !isRetryAction(action);

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      kind: action?.type ? "action" : "text",
      content: action?.label ?? trimmed,
      mentions,
      selectedAction: action,
    };
    const assistantId = replacementAssistantId ?? crypto.randomUUID();
    const retryLastTurnAction = action?.type
      ? null
      : retryLastTurnActionFromMessage(trimmed, {
          assistantMessageId: assistantId,
        });

    setMessages((prev) => {
      const baseMessages = consumeConfirmationActionOnMessages(
        consumeResultActionOnMessages(
          markComposerActionsInactive(
            shouldResetMessagesForNewConversation ? [] : prev,
          ),
          action,
        ),
        action,
      );
      return appendOrReplacePendingAssistantMessage(baseMessages, {
        assistantId,
        pendingAssistant: {
          id: assistantId,
          role: "ai",
          kind: "text",
          content: "",
          contentPresentation:
            action?.type === "show_breakdown" ? "result_breakdown" : undefined,
        },
        userMessage: userMsg,
        renderUserMessage,
      });
    });
    setInputActions([]);
    setStreamStatus(null);
    setIsStreamingResponse(true);

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
        const persistedErrorMessageId = event.data.message_id?.trim();
        const visibleRetryAction =
          retryLastTurnAction && persistedErrorMessageId
            ? retryLastTurnActionFromMessage(trimmed, {
                assistantMessageId: persistedErrorMessageId,
              })
            : retryLastTurnAction;
        setInputActions([]);
        setStreamStatus(null);
        setIsStreamingResponse(false);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? {
                  ...m,
                  id: persistedErrorMessageId || m.id,
                  content: chatStreamErrorText(
                    event.data.detail,
                    t('chat.error_backtest'),
                  ),
                  actions: visibleRetryAction ? [visibleRetryAction] : m.actions,
                }
              : m,
          ),
        );
      }
      if (event.event === "final") {
        setStreamStatus(null);
        setIsStreamingResponse(false);
        const finalPayload = event.data as typeof event.data & Record<string, unknown>;
        const finalText = event.data.assistant_response ?? event.data.assistant_prompt ?? "";
        const finalStageOutcome = event.data.stage_outcome;
        const finalRetryActions = [
          failedActionRetryActionFromMetadata(finalPayload),
        ].filter((retryAction): retryAction is ChatActionOption => Boolean(retryAction));
        const finalHasFailedAction = hasFailedActionMetadata(finalPayload);
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
              mergeFinalTextMessage(m, {
                assistantId,
                finalText,
                finalActions: finalRetryActions,
                contentPresentation:
                  action?.type === "show_breakdown"
                    ? "result_breakdown"
                    : undefined,
              }),
            );
            if (
              isConfirmationAction(action) ||
              finalStageOutcome === "await_user_reply" ||
              finalStageOutcome === "needs_clarification"
            ) {
              return settleOpenConfirmationsAfterTextFinal(nextMessages, {
                action,
                finalActions: finalRetryActions,
                hasFailedAction: finalHasFailedAction,
                stageOutcome: finalStageOutcome,
              });
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
        setIsStreamingResponse(false);
        schedulePostTurnHistoryRefresh(targetConversationId);
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
      await streamToConversation(targetConversationId);
    } catch (err: unknown) {
      if (err instanceof ChatStreamError && err.status === 404 && !action?.type) {
        try {
          clearActiveConversationPointer();
          const { conversation } = await createConversation(i18n.language);
          rememberActiveConversationId(conversation.id);
          setConversationId(conversation.id);
          await streamToConversation(conversation.id);
          return;
        } catch (retryErr) {
          err = retryErr;
        }
      }
      setInputActions([]);
      setStreamStatus(null);
      setIsStreamingResponse(false);
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
                actions: retryLastTurnAction ? [retryLastTurnAction] : m.actions,
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
    setIsStreamingResponse(true);
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
          setIsStreamingResponse(false);
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
          setIsStreamingResponse(false);
          setShowOnboardingGoalCards(false);
          schedulePostTurnHistoryRefresh(conversationId);
        }
      });
      await patchMe({
        onboarding: {
          stage: "ready",
          language_confirmed: true,
          primary_goal: goal,
          completed: true,
        },
      });

    } catch {
      setStreamStatus(null);
      setIsStreamingResponse(false);
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

  const handleSaveStrategyAction = async (action: ChatActionOption) => {
    if (!conversationId) return;
    if (!strategiesEnabled) {
      showToast(t(
        "chat.private_alpha_result_kept",
        "This result is already kept in conversation/history.",
      ));
      return;
    }
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
          schedulePostTurnHistoryRefresh(conversationId);
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

  const handleLogout = async () => {
    try {
      await logoutFromApi();
    } catch {
      // Even if the network is unavailable, leave the authenticated surface.
    } finally {
      window.location.href = "/";
    }
  };

  const handleCancelConfirmationAction = async (action: ChatActionOption) => {
    if (!conversationId || isStreamingResponse) return;
    const effect = confirmationActionEffectFromAction(action);
    if (!effect) return;
    const streamInput: ChatActionRequest = {
      type: "cancel_confirmation",
      label: action.label,
      payload: action.payload,
      presentation: action.presentation,
    };

    setInputActions([]);
    setStreamStatus(null);
    setIsStreamingResponse(true);
    try {
      await streamChatMessage(conversationId, streamInput, i18n.language, (event) => {
        if (event.event === "final") {
          setMessages((prev) =>
            applyConfirmationActionEffects(markComposerActionsInactive(prev), [effect]),
          );
        }
        if (event.event === "error") {
          showToast(chatStreamErrorText(event.data.detail, t('chat.error_generic')));
        }
        if (event.event === "done") {
          schedulePostTurnHistoryRefresh(conversationId);
        }
      }, []);
    } catch (err: unknown) {
      const message =
        err instanceof ChatStreamError && err.message
          ? err.message
          : t('chat.error_generic');
      showToast(message);
    } finally {
      setIsStreamingResponse(false);
      setStreamStatus(null);
    }
  };

  const handleAction = (action: ChatActionOption) => {
    const value = action.value ?? "";
    if (action.type === "save_strategy") {
      void handleSaveStrategyAction(action);
      return;
    }
    if (action.type === "cancel_confirmation") {
      void handleCancelConfirmationAction(action);
      return;
    }
    if (value === "/action:new-chat") {
      void startNewChat();
      return;
    }
    if (action.type === "retry_last_turn") {
      const retryText = retryLastTurnMessageFromAction(action);
      const failedAssistantId = retryLastTurnFailedAssistantIdFromAction(action);
      if (retryText) {
        void handleSend(retryText, [], undefined, {
          renderUserMessage: false,
          replacementAssistantId: failedAssistantId ?? undefined,
        });
      }
      return;
    }
    if (action.type === "retry_load_conversation") {
      const retryConversationId = retryLoadConversationIdFromAction(action);
      if (retryConversationId) {
        void loadConversation(retryConversationId);
      }
      return;
    }
    if (isFailedActionRetry(action)) {
      void handleSend(action.label || value, action);
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

  const composerActions = hasActiveArtifactActionSet(messages)
    ? []
    : visibleComposerActions(inputActions);
  const latestAssistantContent =
    [...messages].reverse().find((message) => message.role === "ai")?.content?.trim() ?? "";
  const showStreamStatus = Boolean(streamStatus && latestAssistantContent.length === 0);
  const showExploratorySuggestions =
    chatExploratorySuggestionsEnabled && showSuggestions;

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="relative flex h-[100dvh] w-full overflow-hidden bg-[#f9f9f9] text-black dark:bg-[#141517] dark:text-white md:flex-row">

      {/* ── Desktop sidebar ── */}
      <ChatSidebar
        isOpen={isSidebarOpen}
        onToggle={toggleSidebar}
        currentView={currentView}
        conversationId={conversationId}
        isRecentsExpanded={isRecentsExpanded}
        onToggleRecents={() => setIsRecentsExpanded((expanded) => !expanded)}
        historyItems={historyItems}
        historyNextCursor={historyNextCursor}
        isLoadingMoreHistory={isLoadingMoreHistory}
        onNewChat={() => {
          void startNewChat();
          setIsSidebarOpen(false);
        }}
        onNavigate={(view) => {
          setCurrentView(view);
          setIsSidebarOpen(false);
        }}
        onOpenItem={openHistoryItem}
        onLoadMoreHistory={loadMoreHistory}
        onOpenSearch={() => {
          if (omnisearchEnabled) {
            setSearchOverlayOpen(true);
          }
        }}
        onHistoryMutated={refreshHistory}
        onConversationRemoved={handleConversationRemoved}
        onLogout={() => {
          void handleLogout();
        }}
        onFeedback={(type) => {
          setFeedbackState({
            isOpen: true,
            type,
            context: { surface: "sidebar", conversation_id: conversationId },
          });
        }}
        onOpenSidebarPreference={() => setIsSidebarPreferenceModalOpen(true)}
        mode={sidebarMode}
        strategiesEnabled={strategiesEnabled}
        omnisearchEnabled={omnisearchEnabled}
      />

      {omnisearchEnabled && searchOverlayOpen && (
        <ChatCommandPalette
          onClose={() => setSearchOverlayOpen(false)}
          onOpenConversation={(convId) => {
            setSearchOverlayOpen(false);
            void loadConversation(convId);
          }}
          activeConversationId={conversationId}
          onMutated={refreshHistory}
          onConversationRemoved={handleConversationRemoved}
        />
      )}

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
            {strategiesEnabled && currentView === "strategies" && (
              <button
                onClick={() => handleTriggerPrompt("strategy")}
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
                  <ChatInput onSend={handleSend} disabled={isStreamingResponse} />
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

                {/* Starter Actions / Chips */}
                <div className="mt-6 flex flex-wrap items-center justify-center gap-3">
                  <button
                    onClick={() => handleSend(t('chat.starter_actions.tsla.value', 'How did Apple perform against SPY in 2024?'))}
                    className="flex items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5"
                  >
                    <TrendingUp className="h-4 w-4 text-black/60 dark:text-white/60" />
                    {t('chat.starter_actions.tsla.label', 'Compare Apple to SPY')}
                  </button>
                  <button
                    onClick={() => handleSend(t('chat.starter_actions.btc.value', 'What if I bought Bitcoin at the start of 2024 and held through the end of 2024?'))}
                    className="flex items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5"
                  >
                    <Bitcoin className="h-4 w-4 text-black/60 dark:text-white/60" />
                    {t('chat.starter_actions.btc.label', 'Hold Bitcoin in 2024')}
                  </button>
                  <button
                    onClick={() => handleSend(t('chat.starter_actions.dca.value', 'What if I bought $250 of Nvidia every week in 2024?'))}
                    className="flex items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5"
                  >
                    <LineChart className="h-4 w-4 text-black/60 dark:text-white/60" />
                    {t('chat.starter_actions.dca.label', 'Buy Nvidia weekly')}
                  </button>
                </div>

                {chatExploratorySuggestionsEnabled && (
                  <div className="mt-4">
                    <button
                      onClick={() => setShowSuggestions(!showSuggestions)}
                      className="text-[14px] font-medium text-black/60 transition-colors hover:text-black dark:text-white/60 dark:hover:text-white"
                    >
                      {showSuggestions ? t('chat.hide_suggestions') : t('chat.show_suggestions')}
                    </button>
                  </div>
                )}

                {showExploratorySuggestions && (
                  <div className="mt-8 flex flex-col items-center gap-4 text-center">
                    <button onClick={() => handleSend(t('chat.example_queries.q1', 'What if I bought Apple after big drops?'))} className="text-[14px] text-black/50 hover:text-black hover:underline dark:text-white/50 dark:hover:text-white transition-colors">
                      {t('chat.example_queries.q1', 'What if I bought Apple after big drops?')}
                    </button>
                    <button onClick={() => handleSend(t('chat.example_queries.q2', 'What if I bought Bitcoin when it starts rising?'))} className="text-[14px] text-black/50 hover:text-black hover:underline dark:text-white/50 dark:hover:text-white transition-colors">
                      {t('chat.example_queries.q2', 'What if I bought Bitcoin when it starts rising?')}
                    </button>
                    <button onClick={() => handleSend(t('chat.example_queries.q3', 'What if I bought Tesla every month?'))} className="text-[14px] text-black/50 hover:text-black hover:underline dark:text-white/50 dark:hover:text-white transition-colors">
                      {t('chat.example_queries.q3', 'What if I bought Tesla every month?')}
                    </button>
                  </div>
                )}
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
                        (isStreamingResponse || !!streamStatus || (msg.content ?? "") === "");
                      return (
                        <ChatMessage
                          key={msg.id}
                          message={msg}
                          onAction={handleAction}
                          onFeedback={(type, context, rating) => {
                            setFeedbackState({
                              isOpen: true,
                              type,
                              context: { ...context, conversation_id: conversationId },
                              rating,
                            });
                            setIsSidebarOpen(false);
                          }}
                          isLatest={isLatestAi}
                          isStreaming={isWorkingMessage}
                          conversationId={conversationId}
                        />
                      );
                    })}
                    {showStreamStatus && (
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
                    {composerActions.length > 0 && !streamStatus && !isStreamingResponse && !isHydratingConversation && (
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
                    <ChatInput onSend={handleSend} disabled={isStreamingResponse || isHydratingConversation} />
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {strategiesEnabled && currentView === "strategies" && (
          <StrategiesView
            onMenuClick={() => setIsSidebarOpen((o) => !o)}
            onAddClick={() => handleTriggerPrompt('strategy')}
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
              void handleLogout();
            }}
            onFeedback={(type, context) => {
              setFeedbackState({
                isOpen: true,
                type,
                context: { ...context, conversation_id: conversationId },
              });
              setIsSidebarOpen(false);
            }}
          />
        )}
      </section>

      {/* ── Feedback Dialog ── */}
      <FeedbackDialog
        isOpen={feedbackState.isOpen}
        onClose={() => setFeedbackState((s) => ({ ...s, isOpen: false }))}
        type={feedbackState.type}
        rating={feedbackState.rating}
        context={feedbackState.context}
      />

      {isSidebarPreferenceModalOpen && (
        <SidebarPreferenceModal
          mode={sidebarMode}
          onSelect={handleSetSidebarMode}
          onClose={() => setIsSidebarPreferenceModalOpen(false)}
        />
      )}

      {/* ── Toast ── */}
      {toast && (
        <div className="fixed bottom-24 left-1/2 z-[100] -translate-x-1/2 animate-in fade-in slide-in-from-bottom-2 duration-300 rounded-full bg-black dark:bg-white px-5 py-2.5 text-[14px] font-medium text-white dark:text-black">
          {toast}
        </div>
      )}
    </div>
  );
}
