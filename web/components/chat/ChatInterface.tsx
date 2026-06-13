"use client";

import { useCallback, useMemo, useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  Edit2,
  MoreVertical,
  Pin,
  Plus,
  Trash2,
  TrendingUp,
  Bitcoin,
  LineChart,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import ChatCommandPalette from "@/components/sidebar/ChatCommandPalette";
import ChatSidebar, { type SidebarMode } from "@/components/sidebar/ChatSidebar";
import SidebarPreferenceModal from "@/components/settings/SidebarPreferenceModal";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";

import {
  createConversation,
  deleteConversation,
  getBacktestJob,
  getBacktestRun,
  getMe,
  getConversationMessages,
  listConversations,
  listHistory,
  logoutFromApi,
  patchConversation,
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
  type BacktestJobResponse,
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
  failedActionRetryActionFromMetadata,
  hasFailedActionMetadata,
  isRetryAction,
  retryLastTurnActionFromMetadata,
  retryLastTurnActionFromMessage,
  retryLastTurnFailedAssistantIdFromAction,
  retryLastTurnMessageFromAction,
  retryLoadConversationIdFromAction,
} from "@/lib/chat-retry-actions";
import {
  activeConversationRouteStateFromUrl,
  shouldStartConversationForVisibleEmptyChat,
  targetConversationIdForSend,
  type ActiveConversationRouteState,
} from "@/lib/chat-conversation-routing";
import {
  conversationLoadFailureMessage,
  shouldShowConversationDisclaimer,
} from "@/lib/chat-conversation-load-state";
import { mergeFinalTextMessage } from "@/lib/chat-final-message";
import { hydrateTextMessageFromApi } from "@/lib/chat-message-hydration";
import { normalizeRetryActionHistory } from "@/lib/chat-retry-action-history";
import {
  hydrateResultActions,
  hydrateResultActionsForRun,
} from "@/lib/chat-result-actions";
import { appendOrReplacePendingAssistantMessage } from "@/lib/chat-send-state";
import {
  applyBacktestJobUpdate,
  backtestJobFromFinalPayload,
  backtestJobMessageFromApi,
  pendingBacktestJobIds,
} from "@/lib/chat-backtest-jobs";
import {
  actionHasCardScopedOwnership,
  isConfirmationAction,
  visibleComposerActions,
} from "@/lib/chat-action-ownership";
import {
  attentionAfterConversationOpen,
  attentionAfterTurnSettled,
} from "@/lib/chat-attention-state";
import { sidebarOpenAfterTransientNavigation } from "@/lib/sidebar-mode-state";
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
  settleOpenConfirmationsAfterStreamError,
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
const ACTIVE_CONVERSATION_QUERY_KEY = "conversation";
const POST_TURN_TITLE_REFRESH_DELAYS_MS = [0, 1500, 5000, 9000, 13000];

type HydratedMessages = {
  messages: Message[];
  inputActions: ChatActionOption[];
};

function chatActionRequestFromAction(action: ChatActionOption): ChatActionRequest {
  return {
    type: action.type as NonNullable<ChatActionOption["type"]>,
    label: action.label,
    labelKey: action.labelKey,
    payload: action.payload,
    presentation: action.presentation,
  };
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
  persistActiveConversationRoute(conversationId);
}

function clearActiveConversationRoute(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const url = new URL(window.location.href);
    if (url.pathname !== "/chat") return null;
    if (!url.searchParams.has(ACTIVE_CONVERSATION_QUERY_KEY)) return null;
    url.searchParams.delete(ACTIVE_CONVERSATION_QUERY_KEY);
    const query = url.searchParams.toString();
    const nextRoute = query ? `${url.pathname}?${query}` : url.pathname;
    window.history.replaceState(
      window.history.state,
      "",
      nextRoute,
    );
    return nextRoute;
  } catch {
    // URL state is optional recovery metadata.
    return null;
  }
}

function clearActiveConversationPointer() {
  return clearActiveConversationRoute();
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

function historyItemBelongsToConversation(
  item: HistoryItem,
  targetConversationId: string,
) {
  return item.id === targetConversationId || item.conversation_id === targetConversationId;
}

function isMissingConversationLoadError(error: unknown) {
  if (typeof error !== "object" || error === null) {
    return false;
  }
  const status = "status" in error ? Number(error.status) : null;
  const code = "code" in error && typeof error.code === "string" ? error.code : null;
  return status === 403 || status === 404 || code === "not_found";
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

function isHydratableResultCard(value: unknown): value is ConversationResultCard {
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
    const resultCard = metadata.result_card;
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

function chatStreamErrorText(detail: string | undefined, fallback: string) {
  return detail || fallback;
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function ChatInterface() {
  const { t, i18n } = useTranslation();
  const router = useRouter();

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
  const [attentionConversationIds, setAttentionConversationIds] = useState<Set<string>>(
    () => new Set(),
  );
  const [currentView, setCurrentView] = useState<View>("chat");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [searchOverlayOpen, setSearchOverlayOpen] = useState(false);
  const [showChatOptions, setShowChatOptions] = useState(false);
  const [pendingHeaderDeleteId, setPendingHeaderDeleteId] = useState<string | null>(null);
  const [isDeletingHeaderChat, setIsDeletingHeaderChat] = useState(false);
  const [headerRenameValue, setHeaderRenameValue] = useState("");
  const [isRenamingHeaderChat, setIsRenamingHeaderChat] = useState(false);
  const [isSavingHeaderRename, setIsSavingHeaderRename] = useState(false);
  const [isPinningHeaderChat, setIsPinningHeaderChat] = useState(false);
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
  const activeConversationIdRef = useRef<string | null>(null);
  const currentViewRef = useRef<View>("chat");
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const pendingBacktestJobKey = useMemo(
    () => pendingBacktestJobIds(messages).join("|"),
    [messages],
  );

  const applyDurableBacktestJobResponse = useCallback(
    (response: BacktestJobResponse) => {
      setMessages((prev) =>
        normalizeRetryActionHistory(
          normalizeConfirmationHistory(
            applyBacktestJobUpdate(prev, response),
          ),
        ),
      );
    },
    [],
  );

  // ── Toast helper ───────────────────────────────────────────────────────────

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  }, []);

  const clearConversationAttention = useCallback((nextConversationId?: string | null) => {
    setAttentionConversationIds((prev) =>
      attentionAfterConversationOpen(prev, nextConversationId),
    );
  }, []);

  const markConversationAttentionIfOutOfFocus = useCallback(
    (settledConversationId?: string | null) => {
      const focusedConversationId =
        currentViewRef.current === "chat" ? activeConversationIdRef.current : null;
      setAttentionConversationIds((prev) =>
        attentionAfterTurnSettled(prev, settledConversationId, focusedConversationId),
      );
    },
    [],
  );

  useEffect(() => {
    activeConversationIdRef.current = conversationId;
    currentViewRef.current = currentView;
    if (currentView === "chat") {
      clearConversationAttention(conversationId);
    }
  }, [clearConversationAttention, conversationId, currentView]);

  const resetToEmptyChatSurface = useCallback(() => {
    const clearedRoute = clearActiveConversationPointer();
    if (clearedRoute) {
      router.replace(clearedRoute, { scroll: false });
    }
    setConversationId(null);
    setMessages([]);
    setInputActions([]);
    setStreamStatus(null);
    setIsHydratingConversation(false);
    setIsStreamingResponse(false);
    setShowChatOptions(false);
    setIsRenamingHeaderChat(false);
    setHeaderRenameValue("");
    setCurrentView("chat");
  }, [router]);

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

  const closeTransientSidebar = useCallback(() => {
    setIsSidebarOpen((currentOpen) =>
      sidebarOpenAfterTransientNavigation({
        currentOpen,
        mode: sidebarMode,
      }),
    );
  }, [sidebarMode]);

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
        const activeConversationId = readActiveConversationIdFromUrl();
        if (activeConversationId) {
          try {
            const { items } = await getConversationMessages(activeConversationId, 50);
            if (cancelled) return;
            const hydrated = hydrateMessagesFromApi(items);
            if (hydrated.messages.length === 0) {
              // clear empty persisted conversations from the active route.
              resetToEmptyChatSurface();
              setShowOnboardingGoalCards(
                privateAlphaOnboardingEnabled &&
                (stage === "language_selection" || stage === "primary_goal_selection"),
              );
              return;
            }
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
          } catch (error) {
            if (cancelled) return;
            if (isMissingConversationLoadError(error)) {
              setHistoryItems((prev) =>
                prev.filter((item) => !historyItemBelongsToConversation(item, activeConversationId)),
              );
              resetToEmptyChatSurface();
              setShowOnboardingGoalCards(
                privateAlphaOnboardingEnabled &&
                (stage === "language_selection" || stage === "primary_goal_selection"),
              );
              return;
            }
            rememberActiveConversationId(activeConversationId);
            setConversationId(activeConversationId);
            setMessages([
              conversationLoadFailureMessage(activeConversationId, t('chat.error_load')),
            ]);
            setInputActions([]);
            setShowOnboardingGoalCards(false);
            return;
          }
        }

        if (cancelled) return;
        resetToEmptyChatSurface();
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

  useEffect(() => {
    if (!pendingBacktestJobKey) {
      return;
    }
    let cancelled = false;
    const timers: number[] = [];
    const jobIds = pendingBacktestJobKey.split("|").filter(Boolean);

    const pollJob = async (jobId: string, attempt = 0) => {
      try {
        const response = await getBacktestJob(jobId);
        if (cancelled) {
          return;
        }
        applyDurableBacktestJobResponse(response);
        const shouldContinue =
          response.job.status === "queued" ||
          response.job.status === "running" ||
          (response.job.status === "succeeded" && !response.run);
        if (shouldContinue && attempt < 45) {
          timers.push(window.setTimeout(() => {
            void pollJob(jobId, attempt + 1);
          }, 2000));
        }
      } catch {
        if (!cancelled && attempt < 5) {
          timers.push(window.setTimeout(() => {
            void pollJob(jobId, attempt + 1);
          }, 3000));
        }
      }
    };

    jobIds.forEach((jobId) => {
      void pollJob(jobId);
    });

    return () => {
      cancelled = true;
      timers.forEach(window.clearTimeout);
    };
  }, [applyDurableBacktestJobResponse, pendingBacktestJobKey]);

  // ── Load existing conversation ─────────────────────────────────────────────

  const loadConversation = async (convId: string) => {
    closeTransientSidebar();
    closeChatOptions();
    setCurrentView("chat");
    rememberActiveConversationId(convId);
    setConversationId(convId);
    setStreamStatus(t('common.loading'));
    setIsHydratingConversation(true);
    try {
      const { items } = await getConversationMessages(convId, 50);
      const hydrated = hydrateMessagesFromApi(items);
      if (hydrated.messages.length === 0) {
        // Keep empty persisted conversations from the active route.
        resetToEmptyChatSurface();
        return;
      }
      setMessages(hydrated.messages);
      setInputActions(hydrated.inputActions);
    } catch (error) {
      if (isMissingConversationLoadError(error)) {
        setHistoryItems((prev) =>
          prev.filter((item) => !historyItemBelongsToConversation(item, convId)),
        );
        resetToEmptyChatSurface();
        showToast(t('chat.error_load'));
        return;
      }
      setMessages([conversationLoadFailureMessage(convId, t('chat.error_load'))]);
      setInputActions([]);
      showToast(t('chat.error_load'));
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
    closeTransientSidebar();
  };

  const openHistoryItem = (item: HistoryItem | SearchItem) => {
    if (item.type === "chat") {
      void loadConversation(item.id);
      return;
    }
    if (strategiesEnabled && item.type === "strategy") {
      setCurrentView("strategies");
      closeTransientSidebar();
      return;
    }
    if (item.type === "run") {
      void loadConversationForRun(item);
      return;
    }
    setCurrentView("chat");
    closeTransientSidebar();
  };

  // ── Start new chat ─────────────────────────────────────────────────────────

  const startNewChat = useCallback(async () => {
    resetToEmptyChatSurface();
    closeTransientSidebar();
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
    return null;
  }, [closeTransientSidebar, refreshHistory, resetToEmptyChatSurface]);

  const handleConversationRemoved = useCallback((removedConversationId: string) => {
    setHistoryItems((prev) =>
      prev.filter((item) => !historyItemBelongsToConversation(item, removedConversationId)),
    );
    refreshHistory();
    if (removedConversationId !== conversationId) return;
    resetToEmptyChatSurface();
  }, [conversationId, refreshHistory, resetToEmptyChatSurface]);

  const handleAllConversationsDeleted = useCallback(() => {
    setHistoryItems([]);
    refreshHistory();
    if (conversationId === null) return;
    resetToEmptyChatSurface();
  }, [conversationId, refreshHistory, resetToEmptyChatSurface]);

  const handleTriggerPrompt = async (_type: 'strategy', customPrompt?: string) => {
    // 1. Switch view
    setCurrentView("chat");
    closeTransientSidebar();

    // 2. Start new chat
    await startNewChat();

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
    let targetConversationId = targetConversationIdForSend({
      routeConversationId: routeState.conversationId,
      stateConversationId: conversationId,
      action,
    });
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

    if (!targetConversationId && !action?.type) {
      try {
        const { conversation } = await createConversation(i18n.language);
        targetConversationId = conversation.id;
        shouldResetMessagesForNewConversation = messages.length === 0;
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

    closeTransientSidebar();
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
      ? chatActionRequestFromAction(action)
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
        const errorPayload = event.data as typeof event.data & Record<string, unknown>;
        const persistedErrorMessageId = event.data.message_id?.trim();
        const metadataRetryAction = retryLastTurnActionFromMetadata(errorPayload, {
          assistantMessageId: persistedErrorMessageId,
        });
        const visibleRetryAction =
          metadataRetryAction ??
          (retryLastTurnAction && persistedErrorMessageId
            ? retryLastTurnActionFromMessage(trimmed, {
                assistantMessageId: persistedErrorMessageId,
              })
            : retryLastTurnAction);
        setInputActions([]);
        setStreamStatus(null);
        setIsStreamingResponse(false);
        setMessages((prev) =>
          normalizeRetryActionHistory(
            settleOpenConfirmationsAfterStreamError(
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
              action,
            ),
          ),
        );
        markConversationAttentionIfOutOfFocus(targetConversationId);
      }
      if (event.event === "final") {
        setStreamStatus(null);
        setIsStreamingResponse(false);
        const finalPayload = event.data as typeof event.data & Record<string, unknown>;
        const finalText = event.data.assistant_response ?? event.data.assistant_prompt ?? "";
        const finalStageOutcome = event.data.stage_outcome;
        const finalMessageId =
          typeof finalPayload.message_id === "string"
            ? finalPayload.message_id
            : undefined;
        const finalRetryActions = [
          failedActionRetryActionFromMetadata(finalPayload),
          retryLastTurnActionFromMetadata(finalPayload, {
            assistantMessageId: finalMessageId,
          }),
        ].filter((retryAction): retryAction is ChatActionOption => Boolean(retryAction));
        const finalHasFailedAction = hasFailedActionMetadata(finalPayload);
        const savedStrategyId = savedStrategyIdFromFinalPayload(finalPayload);
        const finalBacktestJob = backtestJobFromFinalPayload(finalPayload);
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
            normalizeRetryActionHistory(
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
            normalizeRetryActionHistory(
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
            ),
          );
        } else if (finalBacktestJob) {
          setInputActions([]);
          setMessages((prev) =>
            normalizeRetryActionHistory(
              normalizeConfirmationHistory(
                applyBacktestJobUpdate(
                  prev.map((m) =>
                    m.id === assistantId
                      ? {
                          ...m,
                          kind: "backtest_job",
                          content: finalText || m.content || undefined,
                          backtestJob: finalBacktestJob,
                          artifactId: finalBacktestJob.id,
                          artifactType: "backtest_job",
                          artifactStatus: finalBacktestJob.status,
                          actions: undefined,
                        }
                      : m,
                  ),
                  { job: finalBacktestJob, run: null },
                ),
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
              return normalizeRetryActionHistory(
                settleOpenConfirmationsAfterTextFinal(nextMessages, {
                  action,
                  finalActions: finalRetryActions,
                  hasFailedAction: finalHasFailedAction,
                  stageOutcome: finalStageOutcome,
                }),
              );
            }
            return normalizeRetryActionHistory(nextMessages);
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
        markConversationAttentionIfOutOfFocus(targetConversationId);
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
      markConversationAttentionIfOutOfFocus(targetConversationId);
    }
  };

  const handleOnboardingGoalChoice = async (goal: PrimaryGoal) => {
    let targetConversationId = conversationId;
    if (!targetConversationId) {
      try {
        const { conversation } = await createConversation(i18n.language);
        targetConversationId = conversation.id;
        rememberActiveConversationId(conversation.id);
        setConversationId(conversation.id);
      } catch {
        showToast(t('chat.error_generic'));
        return;
      }
    }
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
    closeTransientSidebar();

    try {
      await streamChatMessage(targetConversationId, hiddenMessage, i18n.language, (event) => {
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
          markConversationAttentionIfOutOfFocus(targetConversationId);
        }
        if (event.event === "done") {
          setStreamStatus(null);
          setIsStreamingResponse(false);
          setShowOnboardingGoalCards(false);
          schedulePostTurnHistoryRefresh(targetConversationId);
          markConversationAttentionIfOutOfFocus(targetConversationId);
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
      markConversationAttentionIfOutOfFocus(targetConversationId);
    }
  };

  // ── Action routing ─────────────────────────────────────────────────────────

  const handleSaveStrategyAction = async (action: ChatActionOption) => {
    const routeState = readActiveConversationRouteState();
    const targetConversationId = targetConversationIdForSend({
      routeConversationId: routeState.conversationId,
      stateConversationId: conversationId,
      action,
    });
    if (!targetConversationId) return;
    if (targetConversationId !== conversationId) {
      rememberActiveConversationId(targetConversationId);
      setConversationId(targetConversationId);
    }
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
      labelKey: action.labelKey,
      payload: action.payload,
      presentation: action.presentation,
    };

    try {
      setMessages((prev) => markResultCardSaving(prev, runId, true));
      await streamChatMessage(targetConversationId, streamInput, i18n.language, (event) => {
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
          markConversationAttentionIfOutOfFocus(targetConversationId);
        }
        if (event.event === "done") {
          schedulePostTurnHistoryRefresh(targetConversationId);
          markConversationAttentionIfOutOfFocus(targetConversationId);
        }
      }, []);
    } catch (err: unknown) {
      const message =
        err instanceof ChatStreamError && err.message
          ? err.message
          : t('chat.error_generic');
          showToast(message);
      markConversationAttentionIfOutOfFocus(targetConversationId);
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
    const routeState = readActiveConversationRouteState();
    const targetConversationId = targetConversationIdForSend({
      routeConversationId: routeState.conversationId,
      stateConversationId: conversationId,
      action,
    });
    if (!targetConversationId || isStreamingResponse) return;
    if (targetConversationId !== conversationId) {
      rememberActiveConversationId(targetConversationId);
      setConversationId(targetConversationId);
    }
    const effect = confirmationActionEffectFromAction(action);
    if (!effect) return;
    const streamInput: ChatActionRequest = {
      type: "cancel_confirmation",
      label: action.label,
      labelKey: action.labelKey,
      payload: action.payload,
      presentation: action.presentation,
    };

    setInputActions([]);
    setStreamStatus(null);
    setIsStreamingResponse(true);
    try {
      await streamChatMessage(targetConversationId, streamInput, i18n.language, (event) => {
        if (event.event === "final") {
          setMessages((prev) =>
            applyConfirmationActionEffects(markComposerActionsInactive(prev), [effect]),
          );
        }
        if (event.event === "error") {
          showToast(chatStreamErrorText(event.data.detail, t('chat.error_generic')));
          markConversationAttentionIfOutOfFocus(targetConversationId);
        }
        if (event.event === "done") {
          schedulePostTurnHistoryRefresh(targetConversationId);
          markConversationAttentionIfOutOfFocus(targetConversationId);
        }
      }, []);
    } catch (err: unknown) {
      const message =
        err instanceof ChatStreamError && err.message
          ? err.message
          : t('chat.error_generic');
      showToast(message);
      markConversationAttentionIfOutOfFocus(targetConversationId);
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

  const closeChatOptions = useCallback(() => {
    setShowChatOptions(false);
    setIsRenamingHeaderChat(false);
  }, []);

  const activeHistoryChat = useMemo(
    () =>
      conversationId
        ? historyItems.find(
            (item) =>
              item.type === "chat" &&
              historyItemBelongsToConversation(item, conversationId),
          ) ?? null
        : null,
    [conversationId, historyItems],
  );

  const handleStartHeaderRename = () => {
    if (!conversationId) return;
    setHeaderRenameValue(
      activeHistoryChat?.title && activeHistoryChat.title !== t('chat.new_chat')
        ? activeHistoryChat.title
        : "",
    );
    setIsRenamingHeaderChat(true);
  };

  const handleSaveHeaderRename = async () => {
    if (!conversationId || isSavingHeaderRename) return;
    const nextTitle = headerRenameValue.trim();
    if (!nextTitle) {
      setIsRenamingHeaderChat(false);
      return;
    }
    setIsSavingHeaderRename(true);
    try {
      await patchConversation(conversationId, { title: nextTitle });
      refreshHistory();
      showToast(t('common.save'));
      closeChatOptions();
    } catch {
      showToast(t('chat.rename_failed'));
    } finally {
      setIsSavingHeaderRename(false);
    }
  };

  const handleToggleHeaderPin = async () => {
    if (!conversationId || isPinningHeaderChat) return;
    setIsPinningHeaderChat(true);
    try {
      await patchConversation(conversationId, {
        pinned: !Boolean(activeHistoryChat?.pinned),
      });
      refreshHistory();
      closeChatOptions();
    } catch {
      showToast(t('common.error_occurred'));
    } finally {
      setIsPinningHeaderChat(false);
    }
  };

  const handleRequestHeaderDelete = () => {
    if (!conversationId) return;
    setPendingHeaderDeleteId(conversationId);
    closeChatOptions();
  };

  const handleConfirmHeaderDelete = async () => {
    if (!pendingHeaderDeleteId || isDeletingHeaderChat) return;
    setIsDeletingHeaderChat(true);
    try {
      await deleteConversation(pendingHeaderDeleteId);
      showToast(t('common.delete'));
      handleConversationRemoved(pendingHeaderDeleteId);
    } catch {
      showToast(t('common.error_occurred'));
    } finally {
      setIsDeletingHeaderChat(false);
      setPendingHeaderDeleteId(null);
    }
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
  }, [closeChatOptions, showChatOptions]);

  const composerActions = hasActiveArtifactActionSet(messages)
    ? []
    : visibleComposerActions(inputActions);
  const latestAssistantContent =
    [...messages].reverse().find((message) => message.role === "ai")?.content?.trim() ?? "";
  const showStreamStatus = Boolean(streamStatus && latestAssistantContent.length === 0);
  const showExploratorySuggestions =
    chatExploratorySuggestionsEnabled && showSuggestions;
  const showConversationDisclaimer = shouldShowConversationDisclaimer(
    messages,
    isStreamingResponse,
  );
  const chatInputPlaceholder =
    messages.length === 0
      ? t("chat.input_placeholder")
      : t("chat.followup_placeholder", "Ask a follow-up...");

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
        attentionConversationIds={attentionConversationIds}
        historyNextCursor={historyNextCursor}
        isLoadingMoreHistory={isLoadingMoreHistory}
        onNewChat={() => {
          void startNewChat();
          closeTransientSidebar();
        }}
        onNavigate={(view) => {
          setCurrentView(view);
          closeTransientSidebar();
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
        onAllConversationsDeleted={handleAllConversationsDeleted}
        onToast={showToast}
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

      <ConfirmDialog
        isOpen={Boolean(pendingHeaderDeleteId)}
        title={t("sidebar.delete_confirm.title", "Delete this conversation?")}
        description={t(
          "sidebar.delete_confirm.description",
          "This moves “{{title}}” to Recently Deleted. You can restore it before permanent removal.",
          { title: t("common.conversation", "Conversation") },
        )}
        confirmLabel={t("sidebar.delete_confirm.confirm", "Delete conversation")}
        cancelLabel={t("common.cancel", "Cancel")}
        isBusy={isDeletingHeaderChat}
        onCancel={() => {
          if (!isDeletingHeaderChat) setPendingHeaderDeleteId(null);
        }}
        onConfirm={() => void handleConfirmHeaderDelete()}
      />

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
            {currentView === "chat" && messages.length > 0 && t('common.conversation', 'Conversation')}
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
                  aria-label={t("chat.chat_options", "Chat options")}
                >
                  <MoreVertical className="h-5 w-5" />
                </button>
                {showChatOptions && (
                  <div className="fixed inset-x-0 bottom-0 z-50 rounded-t-[28px] border-t border-black/5 bg-white pb-7 pt-2 dark:border-white/5 dark:bg-[#1f2225] md:absolute md:bottom-auto md:right-0 md:left-auto md:top-full md:mt-2 md:w-[260px] md:rounded-[20px] md:border md:pb-2">
                    <div className="mx-auto my-3 h-1.5 w-12 rounded-full bg-black/10 dark:bg-white/10 md:hidden" />
                    {!isRenamingHeaderChat ? (
                      <div className="py-1">
                        <button
                          type="button"
                          disabled={!conversationId}
                          onClick={handleStartHeaderRename}
                          className="flex w-full items-center gap-4 px-6 py-4 text-left text-[16px] font-medium transition-colors hover:bg-black/5 dark:hover:bg-white/5 md:px-5 md:py-3 md:text-[15px]"
                        >
                          <Edit2 className="h-[18px] w-[18px] text-black/60 dark:text-white/60 md:h-4 md:w-4" />
                          {t('chat.rename_chat', 'Rename chat')}
                        </button>
                        <button
                          type="button"
                          disabled={!conversationId || isPinningHeaderChat}
                          onClick={() => { void handleToggleHeaderPin(); }}
                          className="flex w-full items-center gap-4 px-6 py-4 text-left text-[16px] font-medium transition-colors hover:bg-black/5 dark:hover:bg-white/5 md:px-5 md:py-3 md:text-[15px]"
                        >
                          <Pin className="h-[18px] w-[18px] text-black/60 dark:text-white/60 md:h-4 md:w-4" />
                          {activeHistoryChat?.pinned
                            ? t('chat.unpin_chat', 'Unpin chat')
                            : t('chat.pin_chat', 'Pin chat')}
                        </button>
                        <div className="my-1 h-px bg-black/5 dark:bg-white/5" />
                        <button
                          type="button"
                          disabled={!conversationId || isDeletingHeaderChat}
                          onClick={handleRequestHeaderDelete}
                          className="flex w-full items-center gap-4 px-6 py-4 text-left text-[16px] font-medium text-red-500 transition-colors hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-45 dark:hover:bg-red-500/10 md:px-5 md:py-3 md:text-[15px]"
                        >
                          <Trash2 className="h-[18px] w-[18px] md:h-4 md:w-4" />
                          {t('chat.delete_chat')}
                        </button>
                      </div>
                    ) : (
                      <form
                        className="space-y-2 px-5 py-3"
                        onSubmit={(event) => {
                          event.preventDefault();
                          void handleSaveHeaderRename();
                        }}
                      >
                        <label className="block text-[12px] font-medium text-black/45 dark:text-white/45">
                          {t('chat.rename_chat', 'Rename chat')}
                        </label>
                        <input
                          autoFocus
                          value={headerRenameValue}
                          onChange={(event) => setHeaderRenameValue(event.target.value.slice(0, 80))}
                          className="w-full rounded-[12px] border border-black/10 bg-black/[0.02] px-3 py-2 text-[14px] font-medium text-black outline-none focus:border-black/25 dark:border-white/10 dark:bg-white/[0.04] dark:text-white dark:focus:border-white/25"
                          maxLength={80}
                        />
                        <div className="flex gap-2">
                          <button
                            type="submit"
                            disabled={isSavingHeaderRename}
                            className="min-h-9 flex-1 rounded-full bg-black px-3 py-1.5 text-[13px] font-medium text-white transition-opacity hover:opacity-85 disabled:opacity-50 dark:bg-white dark:text-black"
                          >
                            {t('common.save')}
                          </button>
                          <button
                            type="button"
                            disabled={isSavingHeaderRename}
                            onClick={() => setIsRenamingHeaderChat(false)}
                            className="min-h-9 flex-1 rounded-full border border-black/10 px-3 py-1.5 text-[13px] font-medium text-black/70 transition-colors hover:bg-black/5 disabled:opacity-50 dark:border-white/10 dark:text-white/70 dark:hover:bg-white/5"
                          >
                            {t('common.cancel')}
                          </button>
                        </div>
                      </form>
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
                  <ChatInput
                    onSend={handleSend}
                    disabled={isStreamingResponse}
                    placeholder={chatInputPlaceholder}
                  />
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
                    onClick={() => handleSend(t('chat.starter_actions.tsla.value', 'Buy and hold AAPL over the last 12 months with SPY as the benchmark.'))}
                    className="flex items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5"
                  >
                    <TrendingUp className="h-4 w-4 text-black/60 dark:text-white/60" />
                    {t('chat.starter_actions.tsla.label', 'Test Apple vs SPY')}
                  </button>
                  <button
                    onClick={() => handleSend(t('chat.starter_actions.btc.value', 'What if I bought Bitcoin this year so far?'))}
                    className="flex items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5"
                  >
                    <Bitcoin className="h-4 w-4 text-black/60 dark:text-white/60" />
                    {t('chat.starter_actions.btc.label', 'Test Bitcoin (BTC) hold')}
                  </button>
                  <button
                    onClick={() => handleSend(t('chat.starter_actions.dca.value', 'What if I bought $250 of Nvidia every week over the last 12 months?'))}
                    className="flex items-center gap-2 rounded-full border border-black/10 bg-white/50 px-4 py-2 text-[14px] font-medium text-black transition-colors hover:bg-black/5 dark:border-white/10 dark:bg-[#1f2225]/50 dark:text-white dark:hover:bg-white/5"
                  >
                    <LineChart className="h-4 w-4 text-black/60 dark:text-white/60" />
                    {t('chat.starter_actions.dca.label', 'Test weekly Nvidia buys')}
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
                  className="argus-scrollbar flex-1 overflow-y-auto px-4 pb-[190px] pt-[86px]"
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
                          onToast={showToast}
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
                    <div ref={bottomRef} className="h-28" aria-hidden="true" />
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
                    <ChatInput
                      onSend={handleSend}
                      disabled={isStreamingResponse || isHydratingConversation}
                      placeholder={chatInputPlaceholder}
                    />
                    {showConversationDisclaimer && (
                      <p
                        data-testid="chat-disclaimer"
                        className="mt-3 text-center text-[13px] font-normal leading-[1.45] text-black/40 dark:text-white/40"
                      >
                        {t("chat.disclaimer", "Argus can make mistakes. For education only. Not financial advice.")}
                      </p>
                    )}
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
            onHistoryMutated={refreshHistory}
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

        {/* ── Toast ── */}
        {toast && (
          <div className="pointer-events-none absolute inset-x-0 bottom-24 z-[100] flex justify-center px-4">
            <div
              role="status"
              aria-live="polite"
              className="max-w-[min(720px,calc(100vw-2rem))] animate-in rounded-full border border-black/10 bg-white px-5 py-2.5 text-center text-[14px] font-medium text-black/80 shadow-[0_18px_60px_rgba(15,23,42,0.18)] duration-300 fade-in slide-in-from-bottom-2 dark:border-white/10 dark:bg-[#1f2225] dark:text-white/80 dark:shadow-[0_18px_60px_rgba(0,0,0,0.35)]"
            >
              {toast}
            </div>
          </div>
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

    </div>
  );
}
