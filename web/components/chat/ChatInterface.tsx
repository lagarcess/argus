"use client";

import {
  useCallback,
  useMemo,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import {
  ArrowDown,
  Plus,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import ChatCommandPalette from "@/components/sidebar/ChatCommandPalette";
import ChatSidebar, {
  type SidebarMode,
} from "@/components/sidebar/ChatSidebar";
import SidebarPreferenceModal from "@/components/settings/SidebarPreferenceModal";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import StarterActions from "@/components/chat/StarterActions";
import ChatLegalNotice from "@/components/chat/ChatLegalNotice";
import ChatToast from "@/components/chat/ChatToast";
import EmptyChatHeading from "@/components/chat/EmptyChatHeading";
import { useChatSurfaceLifecycle } from "@/components/chat/useChatSurfaceLifecycle";
import { useRecentConversations } from "@/components/chat/useRecentConversations";
import GuestExperienceSurfaces from "@/components/guest/GuestExperienceSurfaces";
import GuestHeader from "@/components/guest/GuestHeader";
import {
  useGuestExperience,
  useGuestSendBridge,
  type GuestResumeSend,
} from "@/components/guest/useGuestExperience";
import {
  createConversation,
  deleteConversation,
  getBacktestRun,
  listConversations,
  logoutFromApi,
  patchConversation,
  getMe,
  resultCardFromRun,
  streamChatMessage,
  ChatStreamError,
  type ChatStreamEvent,
  type ChatActionRequest,
  type HistoryItem,
  type BacktestRun,
  type SearchItem,
} from "@/lib/argus-api";
import {
  chatExploratorySuggestionsEnabled,
  omnisearchEnabled,
  strategiesEnabled,
} from "@/lib/private-alpha-flags";
import {
  durableRetryLastTurnFromStreamError,
  failedActionRetryActionFromMetadata,
  hasFailedActionMetadata,
  isRetryAction,
  normalizeDurableRetryActionHistory,
  retryLastTurnActionFromMetadata,
  retryLastTurnActionFromMessage,
  retryLastTurnChatActionFromAction,
  retryLastTurnFailedAssistantIdFromAction,
  retryLastTurnMessageFromAction,
  retryLastTurnRequestMessageIdFromAction,
  retryLoadConversationIdFromAction,
} from "@/lib/chat-retry-actions";
import {
  activeConversationRouteStateFromUrl,
  shouldApplyConversationOwnedUpdate,
  shouldApplyConversationScopedUpdate,
  shouldRetireActiveStreamForNavigation,
  shouldStartConversationForVisibleEmptyChat,
  targetConversationIdForSend,
  type ActiveConversationRouteState,
} from "@/lib/chat-conversation-routing";
import {
  conversationLoadFailureMessage,
  shouldShowConversationDisclaimer,
} from "@/lib/chat-conversation-load-state";
import { mergeFinalTextMessage } from "@/lib/chat-final-message";
import {
  discoveryCandidateMention,
  discoverySidecarFromMetadata,
} from "@/lib/chat-discovery-sidecar";
import {
  recoveryActionsFromMetadata,
  recoveryDisplayFromMetadata,
  retryableAssistantRecoveryCode,
} from "@/lib/chat-recovery-display";
import { nextExperimentRowsFromMetadata } from "@/lib/chat-next-experiments";
import { resultFactHeadingKeyFromMetadata } from "@/lib/result-followup-heading";
import {
  loadAllConversationMessagePages,
  resolveOrdinaryTransportAmbiguityView,
  snapshotOrdinaryTransportMessageIds,
} from "@/lib/chat-message-hydration";
import {
  hydrateResultActionsForRun,
  markResultCardSaved,
  markResultCardSaving,
} from "@/lib/chat-result-actions";
import {
  appendOrReplacePendingAssistantMessage,
  replaceOrAppendFinalAssistantMessage,
} from "@/lib/chat-send-state";
import {
  applyBacktestJobUpdate,
  backtestJobFromFinalPayload,
} from "@/lib/chat-backtest-jobs";
import {
  applyRecoverableRunReconciliation,
  ambiguousRunConfirmationId,
  applyReconciledBacktestJobResponse,
  getBacktestJobByAction,
  reconcileAmbiguousRunResponse,
  throwIfAmbiguousRunSseError,
  throwIfAmbiguousRunStreamTermination,
  useBacktestJobPolling,
} from "@/lib/chat-run-reconciliation";
import { isConfirmationAction } from "@/lib/chat-action-ownership";
import {
  attentionAfterConversationOpen,
  attentionAfterTurnSettled,
} from "@/lib/chat-attention-state";
import { sidebarOpenAfterTransientNavigation } from "@/lib/sidebar-mode-state";
import {
  TranscriptSessionCache,
  type TranscriptMutation,
  type TranscriptNavigationState,
} from "@/lib/chat-transcript-session-cache";
import { renamePrefillTitle } from "@/lib/chat-title-display";
import { useActiveConversationTitle } from "@/lib/chat-header-title-state";
import SettingsView from "../views/SettingsView";
import StrategiesView from "../views/StrategiesView";
import ChatHeaderMenu from "./ChatHeaderMenu";
import ChatHeaderTitle from "./ChatHeaderTitle";
import ChatInput from "./ChatInput";
import ChatMessage from "./ChatMessage";
import ConversationRetrievalState, {
  ConversationRetrievalAnnouncement,
} from "./ConversationRetrievalState";
import FeedbackDialog from "../feedback/FeedbackDialog";
import {
  type ChatActionOption,
  type ChatMention,
  type Message,
  type StrategyConfirmationPayload,
} from "./types";
import {
  chatActionRequestFromAction,
  chatStreamErrorText,
  consumeConfirmationActionOnMessages,
  hasActiveArtifactActionSet,
  hydrateMessagesFromApi,
  isFailedActionRetry,
  markComposerActionsInactive,
  resultRunIdFromFinalPayload,
  savedStrategyIdFromFinalPayload,
  settleOpenConfirmationsFromFinalPayload,
} from "./chat-message-projection";
export {
  hydrateMessagesFromApi,
  latestInputActions,
  settleOpenConfirmationsFromFinalPayload,
} from "./chat-message-projection";
import {
  applyConfirmationActionEffects,
  confirmationActionEffectFromAction,
  consumeResultActionOnMessages,
  isStaleConfirmationActionRejectionCode,
  normalizeConfirmationHistory,
  settleConfirmationAfterActionTransportError,
  resultActionRunId,
  settleOpenConfirmationsAfterStreamError,
} from "./artifact-history";

type View = "chat" | "strategies" | "settings";
type SendOptions = {
  renderUserMessage?: boolean;
  replacementAssistantId?: string;
  bypassGuestGate?: boolean;
};
const JUMP_TO_LATEST_THRESHOLD_PX = 240;
const COLD_TRANSCRIPT_RETRIEVAL_DELAY_MS = 150;
const ACTIVE_CONVERSATION_QUERY_KEY = "conversation";
const POST_TURN_TITLE_REFRESH_DELAYS_MS = [0, 1500, 5000, 9000, 13000];
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
    if (
      url.searchParams.get(ACTIVE_CONVERSATION_QUERY_KEY) === conversationId
    ) {
      return;
    }
    url.searchParams.set(ACTIVE_CONVERSATION_QUERY_KEY, conversationId);
    window.history.replaceState(
      window.history.state,
      "",
      `${url.pathname}${url.search}`,
    );
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
    window.history.replaceState(window.history.state, "", nextRoute);
    return nextRoute;
  } catch {
    // URL state is optional recovery metadata.
    return null;
  }
}

function clearActiveConversationPointer() {
  return clearActiveConversationRoute();
}

function historyItemBelongsToConversation(
  item: HistoryItem,
  targetConversationId: string,
) {
  return (
    item.id === targetConversationId ||
    item.conversation_id === targetConversationId
  );
}

function isMissingConversationLoadError(error: unknown) {
  if (typeof error !== "object" || error === null) {
    return false;
  }
  const status = "status" in error ? Number(error.status) : null;
  const code =
    "code" in error && typeof error.code === "string" ? error.code : null;
  return status === 403 || status === 404 || code === "not_found";
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function ChatInterface() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const [account, setAccount] = useState<Awaited<
    ReturnType<typeof getMe>
  > | null>(null);
  const refreshAccount = useCallback(async () => {
    const nextAccount = await getMe();
    setAccount(nextAccount);
    const resolvedLanguage = nextAccount.user.language ?? i18n.language;
    if (resolvedLanguage && resolvedLanguage !== i18n.language) {
      await i18n.changeLanguage(resolvedLanguage);
    }
    return nextAccount;
  }, [i18n]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [attentionConversationIds, setAttentionConversationIds] = useState<
    Set<string>
  >(() => new Set());
  const [currentView, setCurrentView] = useState<View>("chat");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [searchOverlayOpen, setSearchOverlayOpen] = useState(false);
  const [showChatOptions, setShowChatOptions] = useState(false);
  const [pendingHeaderDeleteId, setPendingHeaderDeleteId] = useState<
    string | null
  >(null);
  const [isDeletingHeaderChat, setIsDeletingHeaderChat] = useState(false);
  const [headerRenameValue, setHeaderRenameValue] = useState("");
  const [isRenamingHeaderChat, setIsRenamingHeaderChat] = useState(false);
  const [isSavingHeaderRename, setIsSavingHeaderRename] = useState(false);
  const [isPinningHeaderChat, setIsPinningHeaderChat] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const {
    historyItems,
    setHistoryItems,
    historyNextCursor,
    isLoadingMoreHistory,
    hasRequestedOlderHistory,
    historyLoadMoreError,
    loadHistoryPage,
    clearHistory,
    loadMoreHistory,
    refreshHistory,
  } = useRecentConversations({
    guestExpiresAt: account?.guest?.expires_at,
  });
  const [isStreamingResponse, setIsStreamingResponse] = useState(false);
  const [isHydratingConversation, setIsHydratingConversation] = useState(false);
  const [showConversationRetrievalState, setShowConversationRetrievalState] =
    useState(false);
  const [failedConversationId, setFailedConversationId] = useState<
    string | null
  >(null);
  // First paint waits for the authenticated profile language so a fresh
  // browser cannot send starter prompts in the wrong language.
  const [isBootstrappingProfile, setIsBootstrappingProfile] = useState(true);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [isRecentsExpanded, setIsRecentsExpanded] = useState(true);
  const [feedbackState, setFeedbackState] = useState<{
    isOpen: boolean;
    type: "bug" | "feature" | "general" | "rating";
    rating?: "positive" | "negative";
    context?: Record<string, unknown>;
  }>({ isOpen: false, type: "general" });
  const [sidebarMode, setSidebarMode] = useState<SidebarMode>("collapsed");
  const [isSidebarPreferenceModalOpen, setIsSidebarPreferenceModalOpen] =
    useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const postTurnHistoryRefreshTimersRef = useRef<number[]>([]);
  const activeConversationIdRef = useRef<string | null>(null);
  const activeStreamConversationIdRef = useRef<string | null>(null);
  const hasAcceptedUserInputRef = useRef(false);
  const guestSendRef = useRef<GuestResumeSend | null>(null);
  const ordinaryTransportReconciliationAbortRef =
    useRef<AbortController | null>(null);
  const currentViewRef = useRef<View>("chat");
  const [transcriptSessionCache] = useState(
    () => new TranscriptSessionCache<Message[]>(),
  );
  const coldRetrievalTimerRef = useRef<number | null>(null);
  const coldRetrievalConversationIdRef = useRef<string | null>(null);
  const authenticatedUserIdRef = useRef<string | null>(null);
  const readyTranscriptConversationIdRef = useRef<string | null>(null);
  const pendingScrollRestoreRef = useRef<{
    conversationId: string;
    scrollTop: number | null;
  } | null>(null);
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
  const canApplyConversationScopedUpdate = useCallback(
    (targetConversationId?: string | null) =>
      shouldApplyConversationScopedUpdate({
        targetConversationId,
        activeConversationId: activeConversationIdRef.current,
        currentView: currentViewRef.current,
        routeState: readActiveConversationRouteState(),
      }),
    [],
  );
  const canApplyConversationOwnedUpdate = useCallback(
    (targetConversationId?: string | null) =>
      shouldApplyConversationOwnedUpdate({
        targetConversationId,
        activeConversationId: activeConversationIdRef.current,
      }),
    [],
  );
  const invalidateTranscriptForMutation = useCallback(
    (targetConversationId: string, mutation: TranscriptMutation) => {
      const userId = account?.user.id;
      if (!userId) return;
      transcriptSessionCache.invalidateForMutation({
        userId,
        conversationId: targetConversationId,
        mutation,
      });
      if (
        readyTranscriptConversationIdRef.current === targetConversationId &&
        mutation !== "conversation_rename"
      ) {
        readyTranscriptConversationIdRef.current = null;
      }
    },
    [account?.user.id, transcriptSessionCache],
  );
  const handleDurableJobCompletion = useCallback(
    (targetConversationId: string) => {
      invalidateTranscriptForMutation(
        targetConversationId,
        "durable_job_completion",
      );
    },
    [invalidateTranscriptForMutation],
  );
  useBacktestJobPolling(
    messages,
    canApplyConversationOwnedUpdate,
    setMessages,
    handleDurableJobCompletion,
  );

  // ── Toast helper ───────────────────────────────────────────────────────────

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  }, []);

  const clearConversationAttention = useCallback(
    (nextConversationId?: string | null) => {
      setAttentionConversationIds((prev) =>
        attentionAfterConversationOpen(prev, nextConversationId),
      );
    },
    [],
  );

  const markConversationAttentionIfOutOfFocus = useCallback(
    (settledConversationId?: string | null) => {
      const focusedConversationId =
        currentViewRef.current === "chat"
          ? activeConversationIdRef.current
          : null;
      setAttentionConversationIds((prev) =>
        attentionAfterTurnSettled(
          prev,
          settledConversationId,
          focusedConversationId,
        ),
      );
    },
    [],
  );

  function clearPostTurnHistoryRefreshTimers() {
    for (const timerId of postTurnHistoryRefreshTimersRef.current) {
      window.clearTimeout(timerId);
    }
    postTurnHistoryRefreshTimersRef.current = [];
  }

  const cancelOrdinaryTransportReconciliation = useCallback(() => {
    ordinaryTransportReconciliationAbortRef.current?.abort();
    ordinaryTransportReconciliationAbortRef.current = null;
  }, []);

  const retireActiveStreamForNavigation = useCallback(
    (nextConversationId?: string | null) => {
      if (
        !shouldRetireActiveStreamForNavigation({
          activeStreamConversationId: activeStreamConversationIdRef.current,
          nextConversationId,
        })
      ) {
        return;
      }
      cancelOrdinaryTransportReconciliation();
      activeStreamConversationIdRef.current = null;
      setStreamStatus(null);
      setIsStreamingResponse(false);
      clearPostTurnHistoryRefreshTimers();
    },
    [cancelOrdinaryTransportReconciliation],
  );

  const clearColdTranscriptRetrieval = useCallback(() => {
    if (coldRetrievalTimerRef.current !== null) {
      window.clearTimeout(coldRetrievalTimerRef.current);
      coldRetrievalTimerRef.current = null;
    }
    coldRetrievalConversationIdRef.current = null;
    setShowConversationRetrievalState(false);
  }, []);

  const cancelTranscriptNavigation = useCallback(() => {
    transcriptSessionCache.cancelActiveNavigation();
    clearColdTranscriptRetrieval();
    pendingScrollRestoreRef.current = null;
    readyTranscriptConversationIdRef.current = null;
    setFailedConversationId(null);
    setIsHydratingConversation(false);
  }, [clearColdTranscriptRetrieval, transcriptSessionCache]);

  useEffect(() => {
    activeConversationIdRef.current = conversationId;
    currentViewRef.current = currentView;
    if (currentView === "chat") {
      clearConversationAttention(conversationId);
    }
  }, [clearConversationAttention, conversationId, currentView]);

  const resetToEmptyChatSurface = useCallback(
    (nextConversationId: string | null = null) => {
      cancelTranscriptNavigation();
      retireActiveStreamForNavigation(nextConversationId);
      if (nextConversationId) {
        rememberActiveConversationId(nextConversationId);
      } else {
        const clearedRoute = clearActiveConversationPointer();
        if (clearedRoute) router.replace(clearedRoute, { scroll: false });
      }
      activeConversationIdRef.current = nextConversationId;
      hasAcceptedUserInputRef.current = false;
      currentViewRef.current = "chat";
      setConversationId(nextConversationId);
      setMessages([]);
      setStreamStatus(null);
      setIsHydratingConversation(false);
      setIsStreamingResponse(false);
      setShowChatOptions(false);
      setIsRenamingHeaderChat(false);
      setHeaderRenameValue("");
      setCurrentView("chat");
    },
    [cancelTranscriptNavigation, retireActiveStreamForNavigation, router],
  );

  useLayoutEffect(() => {
    const nextUserId = account?.user.id ?? null;
    const previousUserId = authenticatedUserIdRef.current;
    if (
      previousUserId !== null &&
      nextUserId !== null &&
      previousUserId !== nextUserId
    ) {
      transcriptSessionCache.clearAuthenticatedState();
      resetToEmptyChatSurface();
    }
    authenticatedUserIdRef.current = nextUserId;
  }, [
    account?.user.id,
    resetToEmptyChatSurface,
    transcriptSessionCache,
  ]);

  // ── History ────────────────────────────────────────────────────────────────

  function schedulePostTurnHistoryRefresh(
    targetConversationId?: string | null,
  ) {
    clearPostTurnHistoryRefreshTimers();
    let settled = false;

    const refreshAndCheckTitle = async () => {
      if (settled) return;
      try {
        await loadHistoryPage(null, false);
        if (!targetConversationId) return;
        const { items } = await listConversations({ limit: 50 });
        const conversation = items.find(
          (item) => item.id === targetConversationId,
        );
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

  function markSettledStreamAttention(
    activeStreamTargetConversationId?: string | null,
  ) {
    schedulePostTurnHistoryRefresh(activeStreamTargetConversationId);
    markConversationAttentionIfOutOfFocus(activeStreamTargetConversationId);
  }

  function clearActiveStreamState() {
    cancelOrdinaryTransportReconciliation();
    setStreamStatus(null);
    setIsStreamingResponse(false);
    activeStreamConversationIdRef.current = null;
  }
  useEffect(
    () => () => {
      for (const timerId of postTurnHistoryRefreshTimersRef.current) {
        window.clearTimeout(timerId);
      }
      postTurnHistoryRefreshTimersRef.current = [];
      cancelOrdinaryTransportReconciliation();
      transcriptSessionCache.clearAuthenticatedState();
      if (coldRetrievalTimerRef.current !== null) {
        window.clearTimeout(coldRetrievalTimerRef.current);
      }
    },
    [cancelOrdinaryTransportReconciliation, transcriptSessionCache],
  );

  useEffect(() => {
    if (!isSidebarOpen) {
      setIsRecentsExpanded(false);
    }
  }, [isSidebarOpen]);

  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(
        "argus:sidebar_mode",
      ) as SidebarMode | null;
      if (saved === "expanded" || saved === "collapsed" || saved === "hover") {
        setSidebarMode(saved);
        setIsSidebarOpen(saved === "expanded");
      }
    } catch {
      // Local preferences are optional.
    }
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

  function rememberCurrentConversationScroll(): void {
    const currentConversationId = readyTranscriptConversationIdRef.current;
    const userId = account?.user.id;
    const container = scrollContainerRef.current;
    if (!currentConversationId || !userId || !container) return;
    transcriptSessionCache.rememberScroll({
      userId,
      conversationId: currentConversationId,
      scrollTop: container.scrollTop,
    });
  }

  function stageTranscriptSnapshot(
    targetConversationId: string,
    userId: string,
    snapshot: Message[],
    scrollTopOverride?: number | null,
  ): void {
    clearColdTranscriptRetrieval();
    setFailedConversationId(null);
    setIsHydratingConversation(false);
    if (snapshot.length === 0) {
      resetToEmptyChatSurface();
      return;
    }
    readyTranscriptConversationIdRef.current = targetConversationId;
    const scrollTop =
      scrollTopOverride === undefined
        ? transcriptSessionCache.readScroll({
            userId,
            conversationId: targetConversationId,
          })
        : scrollTopOverride;
    pendingScrollRestoreRef.current = {
      conversationId: targetConversationId,
      scrollTop,
    };
    shouldAutoScrollRef.current = scrollTop === null;
    setMessages(snapshot);
  }

  function beginColdTranscriptRetrieval(targetConversationId: string): void {
    clearColdTranscriptRetrieval();
    readyTranscriptConversationIdRef.current = null;
    pendingScrollRestoreRef.current = null;
    setFailedConversationId(null);
    setMessages([]);
    setIsHydratingConversation(true);
    coldRetrievalConversationIdRef.current = targetConversationId;
    coldRetrievalTimerRef.current = window.setTimeout(() => {
      if (
        coldRetrievalConversationIdRef.current === targetConversationId &&
        activeConversationIdRef.current === targetConversationId &&
        currentViewRef.current === "chat"
      ) {
        setShowConversationRetrievalState(true);
      }
    }, COLD_TRANSCRIPT_RETRIEVAL_DELAY_MS);
  }

  async function navigateConversationTranscript(
    targetConversationId: string,
    userId: string = account?.user.id ?? "",
    options: Readonly<{ bootstrap?: boolean }> = {},
  ): Promise<void> {
    if (!userId) return;
    rememberCurrentConversationScroll();
    retireActiveStreamForNavigation(targetConversationId);
    rememberActiveConversationId(targetConversationId);
    activeConversationIdRef.current = targetConversationId;
    currentViewRef.current = "chat";
    setConversationId(targetConversationId);
    setCurrentView("chat");
    setStreamStatus(null);
    setShowChatOptions(false);

    let renderedStaleSnapshot = false;
    const handle = transcriptSessionCache.navigate({
      userId,
      conversationId: targetConversationId,
      load: async (signal) => {
        const items = await loadAllConversationMessagePages(
          targetConversationId,
          undefined,
          { signal },
        );
        return hydrateMessagesFromApi(items).messages;
      },
      onState: (state: TranscriptNavigationState<Message[]>) => {
        if (state.phase === "loading") {
          beginColdTranscriptRetrieval(targetConversationId);
          return;
        }
        if (state.phase === "refreshing") {
          renderedStaleSnapshot = true;
          stageTranscriptSnapshot(
            targetConversationId,
            userId,
            state.snapshot,
          );
          return;
        }
        if (state.phase === "ready") {
          const currentScrollTop =
            renderedStaleSnapshot &&
            readyTranscriptConversationIdRef.current === targetConversationId
              ? (scrollContainerRef.current?.scrollTop ?? null)
              : undefined;
          stageTranscriptSnapshot(
            targetConversationId,
            userId,
            state.snapshot,
            currentScrollTop,
          );
          return;
        }

        clearColdTranscriptRetrieval();
        setIsHydratingConversation(false);
        if (state.snapshot !== null) {
          readyTranscriptConversationIdRef.current = targetConversationId;
          setMessages(state.snapshot);
          return;
        }
        readyTranscriptConversationIdRef.current = null;
        pendingScrollRestoreRef.current = null;
        setMessages([]);
        if (
          options.bootstrap &&
          isMissingConversationLoadError(state.error)
        ) {
          setHistoryItems((current) =>
            current.filter(
              (item) =>
                !historyItemBelongsToConversation(
                  item,
                  targetConversationId,
                ),
            ),
          );
          resetToEmptyChatSurface();
          return;
        }
        setFailedConversationId(targetConversationId);
      },
    });
    await handle.completion;
  }

  // ── Init conversation ──────────────────────────────────────────────────────

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        let meResponse: Awaited<ReturnType<typeof getMe>> | null = null;
        let profileUnreachable = false;
        try {
          meResponse = await getMe();
          if (!cancelled) setAccount(meResponse);
        } catch (error) {
          const status =
            typeof error === "object" && error !== null && "status" in error
              ? (error as { status?: number }).status
              : undefined;
          profileUnreachable = status !== 401 && status !== 403;
        }
        const resolvedLanguage = meResponse?.user?.language ?? i18n.language;
        if (resolvedLanguage && resolvedLanguage !== i18n.language) {
          await i18n.changeLanguage(resolvedLanguage);
        }
        if (cancelled) return;
        setIsBootstrappingProfile(false);
        if (profileUnreachable) {
          setMessages([
            {
              id: "offline",
              role: "ai",
              kind: "text",
              content: t('chat.error_offline'),
            },
          ]);
          return;
        }
        let activeConversationId = readActiveConversationIdFromUrl();
        if (!activeConversationId && meResponse?.account_kind === "guest") {
          const { items } = await listConversations({ limit: 2 });
          if (cancelled || hasAcceptedUserInputRef.current) return;
          activeConversationId = items[0]?.id ?? null;
        }
        if (activeConversationId) {
          const userId = meResponse?.user.id;
          if (!userId) {
            resetToEmptyChatSurface();
            return;
          }
          await navigateConversationTranscript(activeConversationId, userId, {
            bootstrap: true,
          });
          return;
        }

        if (cancelled || hasAcceptedUserInputRef.current) return;
        resetToEmptyChatSurface();
      } catch {
        if (cancelled) return;
        setIsBootstrappingProfile(false);
        setMessages([
          {
            id: "offline",
            role: "ai",
            kind: "text",
            content: t("chat.error_offline"),
          },
        ]);
        setIsHydratingConversation(false);
      }
    })();
    return () => {
      cancelled = true;
      transcriptSessionCache.cancelActiveNavigation();
    };
    // Bootstraps the active conversation once; re-running on i18n updates would create noisy chat reloads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const updateScrollPositionState = useCallback(() => {
    const container = scrollContainerRef.current;
    if (!container) return;
    const activeTranscriptId = readyTranscriptConversationIdRef.current;
    const userId = account?.user.id;
    if (
      activeTranscriptId &&
      userId &&
      activeTranscriptId === activeConversationIdRef.current
    ) {
      transcriptSessionCache.rememberScroll({
        userId,
        conversationId: activeTranscriptId,
        scrollTop: container.scrollTop,
      });
    }
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const isNearBottom = distanceFromBottom <= JUMP_TO_LATEST_THRESHOLD_PX;
    shouldAutoScrollRef.current = isNearBottom;
    setShowJumpToLatest(distanceFromBottom > JUMP_TO_LATEST_THRESHOLD_PX);
  }, [account?.user.id, transcriptSessionCache]);

  const scrollToLatest = (behavior: ScrollBehavior = "smooth") => {
    bottomRef.current?.scrollIntoView({ behavior });
    shouldAutoScrollRef.current = true;
    setShowJumpToLatest(false);
  };

  useLayoutEffect(() => {
    const pending = pendingScrollRestoreRef.current;
    const container = scrollContainerRef.current;
    if (
      !pending ||
      !container ||
      pending.conversationId !== conversationId ||
      pending.conversationId !== activeConversationIdRef.current
    ) {
      return;
    }
    container.scrollTop = pending.scrollTop ?? container.scrollHeight;
    pendingScrollRestoreRef.current = null;
    const distanceFromBottom =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    const isNearBottom = distanceFromBottom <= JUMP_TO_LATEST_THRESHOLD_PX;
    shouldAutoScrollRef.current =
      pending.scrollTop === null ? true : isNearBottom;
    setShowJumpToLatest(distanceFromBottom > JUMP_TO_LATEST_THRESHOLD_PX);
  }, [conversationId, messages]);

  useEffect(() => {
    if (shouldAutoScrollRef.current) {
      scrollToLatest("smooth");
    } else {
      updateScrollPositionState();
    }
  }, [messages.length, streamStatus, updateScrollPositionState]);

  // ── Load existing conversation ─────────────────────────────────────────────

  const loadConversation = async (convId: string) => {
    closeChatOptions();
    await navigateConversationTranscript(convId);
  };

  const loadConversationForRun = async (
    item: Pick<HistoryItem | SearchItem, "id" | "conversation_id">,
  ) => {
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
      rememberCurrentConversationScroll();
      cancelTranscriptNavigation();
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

  const {
    startNewChat,
    adoptGuestConversation,
    handleConversationRemoved,
    handleAllConversationsDeleted,
  } = useChatSurfaceLifecycle({
    conversationId,
    setHistoryItems,
    resetToEmptyChatSurface,
    closeTransientSidebar,
    refreshHistory,
    onConversationRemoved: (removedConversationId) => {
      invalidateTranscriptForMutation(
        removedConversationId,
        "conversation_delete",
      );
    },
    onAllConversationsDeleted: () => {
      transcriptSessionCache.clearAuthenticatedState();
      readyTranscriptConversationIdRef.current = null;
      pendingScrollRestoreRef.current = null;
    },
  });

  const guestExperience = useGuestExperience({
    account,
    conversationId,
    messages,
    sendRef: guestSendRef,
    refreshAccount,
    refreshHistory,
    closeTransientSidebar,
    startNewChat,
    onOpenFeedback: () =>
      setFeedbackState({
        isOpen: true,
        type: "general",
        context: { surface: "guest_header", conversation_id: conversationId },
      }),
    onOpenOmnisearch: () => setSearchOverlayOpen(true),
    onAdoptConversation: adoptGuestConversation,
    onGateError: () => showToast(t("chat.error_generic")),
    onStartOverError: () =>
      showToast(
        t(
          "guest.new_conversation.error",
          "The temporary chat was left unchanged.",
        ),
      ),
    omnisearchShortcutEnabled: omnisearchEnabled,
  });
  const {
    isGuest,
    canManageConversation,
    canSaveDecision,
    canUseOmnisearch,
    canUseGroundedDiscovery,
    requestGuestDecision,
    requestGuestFeedback,
    requestGuestSearchUpgrade,
    requestGuestSignIn,
    requestNewChat,
    requestOmnisearch,
    resumeDecisionArtifactId,
    resumeDecisionMessageId,
    clearResumeDecision,
  } = guestExperience;

  const actionDisplayLabel = useCallback(
    (action: ChatActionOption) =>
      action.labelKey
      ? t(action.labelKey, {
          defaultValue: action.label,
          ...((action.payload ?? {}) as Record<string, unknown>),
        })
      : action.label,
    [t],
  );

  const handleTriggerPrompt = async (
    _type: "strategy",
    customPrompt?: string,
  ) => {
    // 1. Switch view
    setCurrentView("chat");
    closeTransientSidebar();

    // 2. Start new chat
    await startNewChat();

    // 3. Define the localized prompt or use custom
    const prompt =
      customPrompt ??
      t("chat.trigger_create_strategy", "I want to create a new strategy.");

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
    if (!trimmed) return false;
    if (isStreamingResponse) return false;
    const mentions = Array.isArray(mentionsOrAction) ? mentionsOrAction : [];
    const action = Array.isArray(mentionsOrAction)
      ? actionArg
      : mentionsOrAction;
    if (
      !options?.bypassGuestGate &&
      !(await guestExperience.admitSend({ text: trimmed, mentions, action }))
    ) {
      return false;
    }
    hasAcceptedUserInputRef.current = true;
    setIsHydratingConversation(false);
    const replacementAssistantId =
      options?.replacementAssistantId?.trim() || undefined;
    const routeState = readActiveConversationRouteState();
    let targetConversationId = targetConversationIdForSend({
      routeConversationId: routeState.conversationId,
      stateConversationId: conversationId,
      action,
    });
    const shouldCreateNewRouteConversation =
      shouldStartConversationForVisibleEmptyChat({
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
        showToast(t("chat.error_generic"));
        return false;
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
        showToast(t("chat.error_generic"));
        return false;
      }
    }

    if (!targetConversationId) return false;
    const transcriptMutation: TranscriptMutation =
      action?.type === "retry_last_turn"
        ? "retry"
        : isFailedActionRetry(action)
          ? "recovery"
          : "message_send";
    invalidateTranscriptForMutation(targetConversationId, transcriptMutation);

    if (targetConversationId !== conversationId) {
      rememberActiveConversationId(targetConversationId);
      setConversationId(targetConversationId);
    }
    activeConversationIdRef.current = targetConversationId;
    currentViewRef.current = "chat";

    closeTransientSidebar();
    shouldAutoScrollRef.current = true;
    const renderUserMessage =
      options?.renderUserMessage ?? !isRetryAction(action);

    const userMsg: Message = {
      id: crypto.randomUUID(),
      role: "user",
      kind: action?.type ? "action" : "text",
      content: action?.type ? actionDisplayLabel(action) : trimmed,
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
    setStreamStatus(null);
    activeStreamConversationIdRef.current = targetConversationId;
    setIsStreamingResponse(true);

    const streamInput: string | ChatActionRequest = action?.type
      ? chatActionRequestFromAction(action)
      : trimmed;
    let activeStreamTargetConversationId = targetConversationId;
    const ordinaryTransportMessageIds =
      action?.type === "run_backtest"
        ? null
        : await snapshotOrdinaryTransportMessageIds(async () =>
            loadAllConversationMessagePages(targetConversationId),
          );

    const canApplyVisibleStreamUpdate = () =>
      activeStreamConversationIdRef.current ===
        activeStreamTargetConversationId &&
      canApplyConversationScopedUpdate(activeStreamTargetConversationId);
    const canApplyOwnedStreamUpdate = () =>
      activeStreamConversationIdRef.current ===
        activeStreamTargetConversationId &&
      canApplyConversationOwnedUpdate(activeStreamTargetConversationId);
    const handleStreamEvent = (event: ChatStreamEvent) => {
      throwIfAmbiguousRunSseError(event, action?.type === "run_backtest");
      const canApplyVisibleUpdate = canApplyVisibleStreamUpdate();
      const canApplyOwnedUpdate = canApplyOwnedStreamUpdate();
      if (event.event === "stage_start") {
        if (!canApplyVisibleUpdate) return;
        const stageKey = `chat.status.${event.data.stage}`;
        const detail = event.data.detail;
        setStreamStatus(
          (detail ? t(`${stageKey}_detail`, { detail }) || t(stageKey) : t(stageKey)) ||
            t("chat.status.preparing"),
        );
      }
      if (event.event === "token") {
        if (!canApplyVisibleUpdate) return;
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
        if (!canApplyOwnedUpdate) {
          markSettledStreamAttention(activeStreamTargetConversationId);
          return;
        }
        const errorPayload = event.data as typeof event.data &
          Record<string, unknown>;
        const persistedErrorMessageId = event.data.message_id?.trim();
        const errorRecoveryDisplay = recoveryDisplayFromMetadata(errorPayload);
        const durableRetry = durableRetryLastTurnFromStreamError(errorPayload);
        const durableRetryAction = durableRetry?.action ?? null;
        const metadataRetryAction = durableRetryAction
          ? null
          : retryLastTurnActionFromMetadata(errorPayload, {
              assistantMessageId: persistedErrorMessageId,
              messageRole: "assistant",
            });
        const visibleRetryAction =
          metadataRetryAction ??
          (retryLastTurnAction && persistedErrorMessageId
            ? retryLastTurnActionFromMessage(trimmed, {
                assistantMessageId: persistedErrorMessageId,
              })
            : retryLastTurnAction);
        clearActiveStreamState();
        setMessages((prev) =>
          normalizeDurableRetryActionHistory(
            settleOpenConfirmationsAfterStreamError(
              prev.map((m) =>
                durableRetry && m.id === userMsg.id
                  ? {
                      ...m,
                      id: durableRetry.requestMessageId,
                      content: durableRetry.persistedMessage,
                      recoveryDisplay: errorRecoveryDisplay,
                      actions: [durableRetry.action],
                    }
                  : m.id === assistantId
                    ? {
                        ...m,
                        id: persistedErrorMessageId || m.id,
                        content: chatStreamErrorText(
                          event.data.detail,
                          t("chat.error_backtest"),
                        ),
                        recoveryDisplay: errorRecoveryDisplay,
                        actions:
                          visibleRetryAction && !durableRetryAction
                            ? [visibleRetryAction]
                            : m.actions,
                      }
                    : m,
              ),
              action,
            ),
          ),
        );
        markSettledStreamAttention(activeStreamTargetConversationId);
      }
      if (event.event === "final") {
        if (!canApplyOwnedUpdate) {
          markSettledStreamAttention(activeStreamTargetConversationId);
          return;
        }
        setStreamStatus(null);
        setIsStreamingResponse(false);
        const finalPayload = event.data as typeof event.data &
          Record<string, unknown>;
        const finalText =
          event.data.assistant_response ?? event.data.assistant_prompt ?? "";
        const finalStageOutcome = event.data.stage_outcome;
        const finalMessageId =
          typeof finalPayload.message_id === "string"
            ? finalPayload.message_id
            : undefined;
        const finalRecoveryDisplay = recoveryDisplayFromMetadata(finalPayload);
        const finalAssistantRecoveryCode = retryableAssistantRecoveryCode(
          finalPayload.recovery,
        );
        const finalDiscovery = discoverySidecarFromMetadata(finalPayload);
        const finalResponseActions = finalMessageId
          ? recoveryActionsFromMetadata(finalPayload, finalMessageId)
          : [];
        const finalRetryActions = [
          failedActionRetryActionFromMetadata(finalPayload),
          retryLastTurnActionFromMetadata(finalPayload, {
            assistantMessageId: finalMessageId,
          }),
        ].filter((retryAction): retryAction is ChatActionOption =>
          Boolean(retryAction),
        );
        const finalTextActions = [
          ...finalResponseActions,
          ...finalRetryActions,
        ];
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
          const confirmation = event.data
            .confirmation as StrategyConfirmationPayload;
          const finalAssistantId = finalMessageId ?? assistantId;
          setMessages((prev) =>
            normalizeDurableRetryActionHistory(
              normalizeConfirmationHistory(
                replaceOrAppendFinalAssistantMessage(prev, assistantId, {
                  id: finalAssistantId,
                  role: "ai",
                  kind: "strategy_confirmation",
                  content: undefined,
                  confirmation,
                  actions: confirmation.actions ?? [],
                }),
              ),
            ),
          );
        } else if (event.data.run) {
          const run = event.data.run as BacktestRun;
          const finalAssistantId = finalMessageId ?? assistantId;
          const baseCard = resultCardFromRun(run);
          const resultActions = hydrateResultActionsForRun(
            baseCard.actions ?? [],
            run,
          );
          const card = {
            ...baseCard,
            savedStrategyId: savedStrategyId ?? run.strategy_id ?? null,
            actions: resultActions,
          };
          const finalNextExperiments =
            nextExperimentRowsFromMetadata(finalPayload) ?? undefined;
          setMessages((prev) =>
            normalizeDurableRetryActionHistory(
              normalizeConfirmationHistory(
                replaceOrAppendFinalAssistantMessage(prev, assistantId, {
                  id: finalAssistantId,
                  role: "ai",
                  kind: "strategy_result",
                  content: finalText || undefined,
                  result: card,
                  actions: resultActions,
                  nextExperiments: finalNextExperiments,
                  savedStrategyId: card.savedStrategyId,
                }),
              ),
            ),
          );
        } else if (finalBacktestJob) {
          const finalAssistantId = finalMessageId ?? assistantId;
          setMessages((prev) =>
            normalizeDurableRetryActionHistory(
              normalizeConfirmationHistory(
                applyBacktestJobUpdate(
                  replaceOrAppendFinalAssistantMessage(prev, assistantId, {
                    id: finalAssistantId,
                    role: "ai",
                    kind: "backtest_job",
                    content: finalText || undefined,
                    backtestJob: finalBacktestJob,
                    artifactId: finalBacktestJob.id,
                    artifactType: "backtest_job",
                    artifactStatus: finalBacktestJob.status,
                    actions: undefined,
                  }),
                  { job: finalBacktestJob, run: null },
                ),
              ),
            ),
          );
        } else if (finalText) {
          const finalFactHeadingKey =
            resultFactHeadingKeyFromMetadata(finalPayload);
          setMessages((prev) => {
            const finalAssistantId = finalMessageId ?? assistantId;
            const nextMessages = replaceOrAppendFinalAssistantMessage(
              prev.map((m) =>
                mergeFinalTextMessage(m, {
                  assistantId,
                  finalText,
                  finalActions: finalTextActions,
                  recoveryDisplay: finalRecoveryDisplay,
                  assistantRecoveryCode: finalAssistantRecoveryCode,
                  discovery: finalDiscovery,
                  contentPresentation:
                    action?.type === "show_breakdown"
                      ? "result_breakdown"
                      : undefined,
                  resultFactHeadingKey: finalFactHeadingKey,
                }),
              ),
              assistantId,
              {
                id: finalAssistantId,
                role: "ai",
                kind: "text",
                content: finalText,
                actions:
                  finalTextActions.length > 0 ? finalTextActions : undefined,
                recoveryDisplay: finalRecoveryDisplay,
                assistantRecoveryCode: finalAssistantRecoveryCode,
                discovery: finalDiscovery,
                contentPresentation:
                  action?.type === "show_breakdown"
                    ? "result_breakdown"
                    : undefined,
                resultFactHeadingKey: finalFactHeadingKey,
              },
            );
            if (
              isConfirmationAction(action) ||
              finalStageOutcome === "await_user_reply" ||
              finalStageOutcome === "needs_clarification"
            ) {
              return normalizeDurableRetryActionHistory(
                settleOpenConfirmationsFromFinalPayload(
                  nextMessages,
                  finalPayload,
                  {
                    action,
                    finalActions: finalTextActions,
                    hasFailedAction: finalHasFailedAction,
                  },
                ),
              );
            }
            return normalizeDurableRetryActionHistory(nextMessages);
          });
        }
      }
      if (event.event === "title") {
        if (!canApplyOwnedUpdate) {
          return;
        }
        setHistoryItems((prev) =>
          prev.map((item) =>
            item.id === event.data.conversation_id
              ? { ...item, title: event.data.title }
              : item,
          ),
        );
      }
      if (event.event === "done") {
        if (!canApplyOwnedUpdate) {
          markSettledStreamAttention(activeStreamTargetConversationId);
          return;
        }
        clearActiveStreamState();
        markSettledStreamAttention(activeStreamTargetConversationId);
      }
    };
    const streamToConversation = async (nextTargetConversationId: string) => {
      activeStreamTargetConversationId = nextTargetConversationId;
      activeStreamConversationIdRef.current = nextTargetConversationId;
      let runStreamFinalSeen = false;
      await streamChatMessage(
        nextTargetConversationId,
        streamInput,
        i18n.language,
        (event) => {
          runStreamFinalSeen ||= event.event === "final";
          handleStreamEvent(event);
        },
        // Action turns drop composer mentions, but a discovery selection has no
        // composer input to drop -- its mention *is* the resolver identity the
        // candidate already earned, and dropping it is what forces the
        // interpreter to re-derive the asset from the chip text.
        action?.type && action.type !== "select_discovery_candidate"
          ? []
          : mentions,
      );
      throwIfAmbiguousRunStreamTermination(
        action?.type === "run_backtest",
        runStreamFinalSeen,
      );
    };

    void (async () => {
      try {
        await streamToConversation(targetConversationId);
      } catch (err: unknown) {
        if (
          err instanceof ChatStreamError &&
          err.status === 404 &&
          !action?.type
        ) {
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
        const isOrdinaryTransportAmbiguity =
          action?.type !== "run_backtest" &&
          (!(err instanceof ChatStreamError) || err.status === 0);
        if (isOrdinaryTransportAmbiguity) {
          if (canApplyOwnedStreamUpdate())
            setStreamStatus(t("chat.status.checking"));
          const reconciliationController = new AbortController();
          ordinaryTransportReconciliationAbortRef.current =
            reconciliationController;
          try {
            const view = await resolveOrdinaryTransportAmbiguityView(
              async () =>
                loadAllConversationMessagePages(
                  activeStreamTargetConversationId,
                ),
              hydrateMessagesFromApi,
              {
                assistantId,
                message: conversationLoadFailureMessage(
                  activeStreamTargetConversationId,
                  t("chat.error_load"),
                ),
              },
              ordinaryTransportMessageIds,
              err instanceof ChatStreamError ? err.requestId : null,
              { signal: reconciliationController.signal },
            );
            if (
              !reconciliationController.signal.aborted &&
              canApplyOwnedStreamUpdate()
            ) {
              setMessages(view.messages);
              if (!view.showChecking) {
                clearActiveStreamState();
              }
            }
          } finally {
            if (
              ordinaryTransportReconciliationAbortRef.current ===
              reconciliationController
            ) {
              ordinaryTransportReconciliationAbortRef.current = null;
            }
          }
          markConversationAttentionIfOutOfFocus(
            activeStreamTargetConversationId,
          );
          return;
        }
        const confirmationId = ambiguousRunConfirmationId(action, err);
        if (confirmationId) {
          if (
            canApplyConversationOwnedUpdate(activeStreamTargetConversationId)
          ) {
            setStreamStatus(t("chat.status.checking"));
            setMessages((prev) =>
              settleConfirmationAfterActionTransportError(prev, action, {
                durableStateUnknown: true,
              }),
            );
          }
          const reconciliation = await reconcileAmbiguousRunResponse({
            lookup: () => getBacktestJobByAction(confirmationId),
            replay: () =>
              streamToConversation(activeStreamTargetConversationId),
          });
          if (reconciliation.kind === "replayed") return;
          if (reconciliation.kind === "durable") {
            if (
              canApplyConversationOwnedUpdate(
                reconciliation.response.job.conversation_id,
              )
            ) {
              setMessages((prev) =>
                normalizeDurableRetryActionHistory(
                  normalizeConfirmationHistory(
                    applyReconciledBacktestJobResponse(
                      prev,
                      reconciliation.response,
                      assistantId,
                    ),
                  ),
                ),
              );
              clearActiveStreamState();
            }
            markConversationAttentionIfOutOfFocus(
              activeStreamTargetConversationId,
            );
            return;
          }
          if (reconciliation.kind === "recoverable") {
            if (
              canApplyConversationOwnedUpdate(activeStreamTargetConversationId)
            ) {
              setMessages((prev) =>
                applyRecoverableRunReconciliation(
                  prev,
                  assistantId,
                  activeStreamTargetConversationId,
                  reconciliation.error,
                ),
              );
              clearActiveStreamState();
            }
            markConversationAttentionIfOutOfFocus(
              activeStreamTargetConversationId,
            );
            return;
          }
        }
        const canApplyOwnedUpdate = canApplyConversationOwnedUpdate(
          activeStreamTargetConversationId,
        );
        if (canApplyOwnedUpdate) {
          clearActiveStreamState();
        }
        const status = (err as { status?: number }).status;
        const isRateLimit = status === 429;
        const rejectionCode = err instanceof ChatStreamError ? err.code : null;
        const staleConfirmationRejected =
          isStaleConfirmationActionRejectionCode(rejectionCode);
        const fallbackMessage =
          err instanceof ChatStreamError && err.message
            ? err.message
            : t("chat.error_backtest");
        if (canApplyOwnedUpdate) {
          setMessages((prev) =>
            normalizeDurableRetryActionHistory(
              settleConfirmationAfterActionTransportError(
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: staleConfirmationRejected
                          ? ""
                          : isRateLimit
                            ? t("chat.rate_limit_error")
                            : fallbackMessage,
                        recoveryDisplay: staleConfirmationRejected
                          ? {
                              kind: "recovery_code" as const,
                              code: rejectionCode,
                            }
                          : m.recoveryDisplay,
                        actions: m.actions,
                      }
                    : m,
                ),
                action,
                { rejectionCode },
              ),
            ),
          );
        }
        markConversationAttentionIfOutOfFocus(activeStreamTargetConversationId);
      }
    })();
    return true;
  };

  useGuestSendBridge(guestSendRef, handleSend);
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
      showToast(
        t(
          "chat.private_alpha_result_kept",
          "This result is already kept in conversation/history.",
        ),
      );
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
      await streamChatMessage(
        targetConversationId,
        streamInput,
        i18n.language,
        (event) => {
          if (event.event === "final") {
            const finalPayload = event.data as typeof event.data &
              Record<string, unknown>;
            const savedStrategyId =
              savedStrategyIdFromFinalPayload(finalPayload);
            if (savedStrategyId) {
              setMessages((prev) =>
                markResultCardSaved(
                  prev,
                  resultRunIdFromFinalPayload(finalPayload, action),
                  savedStrategyId,
                ),
              );
              invalidateTranscriptForMutation(targetConversationId, "durable_result_action");
              showToast(t("chat.saved"));
            } else if (event.data.assistant_response) {
              showToast(event.data.assistant_response);
            }
          }
          if (event.event === "error") {
            showToast(
              chatStreamErrorText(event.data.detail, t("chat.error_generic")),
            );
            markConversationAttentionIfOutOfFocus(targetConversationId);
          }
          if (event.event === "done") {
            schedulePostTurnHistoryRefresh(targetConversationId);
            markConversationAttentionIfOutOfFocus(targetConversationId);
          }
        },
        [],
      );
    } catch (err: unknown) {
      const message =
        err instanceof ChatStreamError && err.message
          ? err.message
          : t("chat.error_generic");
      showToast(message);
      markConversationAttentionIfOutOfFocus(targetConversationId);
    } finally {
      setMessages((prev) => markResultCardSaving(prev, runId, false));
    }
  };

  const handleLogout = async () => {
    try {
      const result = await logoutFromApi();
      if (result.revocation === "failed") {
        showToast(
          t(
            "settings.logout_error",
            "We couldn’t sign out this browser. Try again.",
          ),
        );
        return;
      }
      transcriptSessionCache.clearAuthenticatedState();
      resetToEmptyChatSurface();
      clearHistory();
      setSearchText("");
      window.location.href = "/";
    } catch {
      showToast(
        t(
          "settings.logout_error",
          "We couldn’t sign out this browser. Try again.",
        ),
      );
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
    invalidateTranscriptForMutation(targetConversationId, "message_send");
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

    setStreamStatus(null);
    setIsStreamingResponse(true);
    try {
      await streamChatMessage(
        targetConversationId,
        streamInput,
        i18n.language,
        (event) => {
          if (event.event === "final") {
            setMessages((prev) =>
              applyConfirmationActionEffects(
                markComposerActionsInactive(prev),
                [effect],
              ),
            );
          }
          if (event.event === "error") {
            showToast(
              chatStreamErrorText(event.data.detail, t("chat.error_generic")),
            );
            markConversationAttentionIfOutOfFocus(targetConversationId);
          }
          if (event.event === "done") {
            schedulePostTurnHistoryRefresh(targetConversationId);
            markConversationAttentionIfOutOfFocus(targetConversationId);
          }
        },
        [],
      );
    } catch (err: unknown) {
      const message =
        err instanceof ChatStreamError && err.message
          ? err.message
          : t("chat.error_generic");
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
      requestNewChat();
      return;
    }
    if (action.type === "retry_last_turn") {
      const retryText = retryLastTurnMessageFromAction(action);
      const retryChatAction = retryLastTurnChatActionFromAction(action);
      const failedAssistantId =
        retryLastTurnFailedAssistantIdFromAction(action);
      const requestMessageId = retryLastTurnRequestMessageIdFromAction(action);
      // A replayed discovery selection has to carry its identity too, or the
      // retry sends bare chip text and reintroduces the asset re-derivation
      // this lane fixes. The persisted chat_action still holds the payload.
      const retryMention = retryChatAction
        ? discoveryCandidateMention(retryChatAction)
        : null;
      if (retryText) {
        void handleSend(
          retryText,
          retryMention ? [retryMention] : (retryChatAction ?? []),
          retryMention ? (retryChatAction ?? undefined) : undefined,
          requestMessageId
            ? { renderUserMessage: true }
            : {
                renderUserMessage: false,
                replacementAssistantId: failedAssistantId ?? undefined,
              },
        );
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
    const discoveryMention = discoveryCandidateMention(action);
    if (discoveryMention) {
      void handleSend(action.label || value, [discoveryMention], action);
      return;
    }
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
        ? (historyItems.find(
            (item) =>
              item.type === "chat" &&
              historyItemBelongsToConversation(item, conversationId),
          ) ?? null)
        : null,
    [conversationId, historyItems],
  );

  const {
    activeTitleRecord,
    headerConversationTitle,
    headerConversationTitleSource,
  } = useActiveConversationTitle({
    conversationId,
    activeHistoryChat,
    messageCount: messages.length,
    isStreamingResponse,
    isChatViewActive: currentView === "chat",
    placeholder: t("chat.new_chat", "New chat"),
  });

  const handleStartHeaderRename = () => {
    if (!conversationId) return;
    setHeaderRenameValue(renamePrefillTitle(activeTitleRecord));
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
      invalidateTranscriptForMutation(
        conversationId,
        "conversation_rename",
      );
      refreshHistory();
      showToast(t("common.save"));
      closeChatOptions();
    } catch {
      showToast(t("chat.rename_failed"));
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
      showToast(t("common.error_occurred"));
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
      showToast(t("common.delete"));
      handleConversationRemoved(pendingHeaderDeleteId);
    } catch {
      showToast(t("common.error_occurred"));
    } finally {
      setIsDeletingHeaderChat(false);
      setPendingHeaderDeleteId(null);
    }
  };

  // One in-flight lock for every way to start a turn. The composer already
  // disables itself while a turn runs; persistent discovery rows have to obey
  // the same lock or they become a way to spam turns around it.
  const turnInFlight =
    Boolean(streamStatus) || isStreamingResponse || isHydratingConversation;
  // Next-move rows render under their owning message instead of a floating
  // strip above the composer, but they keep every gate the strip applied:
  // nothing offers a next move mid-turn, or while an active card already owns
  // the conversation's actions.
  const nextMovesEnabled =
    !turnInFlight && !hasActiveArtifactActionSet(messages);
  const latestAssistantContent =
    [...messages]
      .reverse()
      .find((message) => message.role === "ai")
      ?.content?.trim() ?? "";
  const showStreamStatus = Boolean(
    streamStatus && latestAssistantContent.length === 0,
  );
  const showExploratorySuggestions =
    chatExploratorySuggestionsEnabled && showSuggestions;
  const showConversationDisclaimer = shouldShowConversationDisclaimer(
    messages,
    isStreamingResponse,
  );
  const chatInputPlaceholder =
    messages.length === 0
      ? t(isGuest ? "guest.shell.input_placeholder" : "chat.input_placeholder")
      : t("chat.followup_placeholder", "Ask a follow-up...");
  const showEmptyChatSurface =
    conversationId === null && messages.length === 0;
  const conversationComposerUnavailable =
    isStreamingResponse ||
    isHydratingConversation ||
    failedConversationId === conversationId;

  // ── Render ─────────────────────────────────────────────────────────────────

  if (isBootstrappingProfile) {
    return (
      <div className="flex h-[100dvh] w-full items-center justify-center bg-background">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

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
        hasRequestedOlderHistory={hasRequestedOlderHistory}
        historyLoadMoreError={historyLoadMoreError}
        onNewChat={() => {
          requestNewChat();
          closeTransientSidebar();
        }}
        onNavigate={(view) => {
          if (view !== "chat") {
            rememberCurrentConversationScroll();
            cancelTranscriptNavigation();
          }
          setCurrentView(view);
          closeTransientSidebar();
        }}
        onOpenItem={openHistoryItem}
        onLoadMoreHistory={loadMoreHistory}
        onOpenSearch={() => {
          if (omnisearchEnabled) {
            requestOmnisearch();
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
        canManageConversation={canManageConversation}
        showProfileMenu={!isGuest}
        isGuest={isGuest}
        guestExpiresAt={account?.guest?.expires_at}
      />

      {omnisearchEnabled &&
        (!isGuest || canUseOmnisearch) &&
        searchOverlayOpen && (
          <ChatCommandPalette
            onClose={() => setSearchOverlayOpen(false)}
            onOpenConversation={(convId) => {
              setSearchOverlayOpen(false);
              void loadConversation(convId);
            }}
            activeConversationId={conversationId}
            isGuest={isGuest}
            groundedDiscoveryAvailable={canUseGroundedDiscovery}
            canManageConversation={canManageConversation}
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
          { title: headerConversationTitle },
        )}
        confirmLabel={t(
          "sidebar.delete_confirm.confirm",
          "Delete conversation",
        )}
        cancelLabel={t("common.cancel", "Cancel")}
        isBusy={isDeletingHeaderChat}
        onCancel={() => {
          if (!isDeletingHeaderChat) setPendingHeaderDeleteId(null);
        }}
        onConfirm={() => void handleConfirmHeaderDelete()}
      />

      {/* ── Main panel ── */}
      <section className="relative z-10 flex h-full flex-1 flex-col overflow-hidden bg-[#f9f9f9] dark:bg-[#141517]">
        {/* ── Unified View Header (SOTA: Absolute to content panel for perfect centering) ── */}
        {currentView !== "settings" && (
          <header className="absolute inset-x-0 top-0 z-[50] flex h-20 items-center justify-between gap-4 px-4 pointer-events-none md:px-8">
            {/* Title (left-aligned; truncates before the action cluster) */}
            <h1 className="font-display pointer-events-auto min-w-0 flex-1 truncate text-left text-[17px] font-semibold tracking-tight text-black/80 dark:text-white/80 md:text-[18px]">
              {currentView === "chat" &&
                (conversationId !== null || messages.length > 0) && (
                <ChatHeaderTitle
                  conversationId={conversationId}
                  title={headerConversationTitle}
                  titleSource={headerConversationTitleSource}
                />
              )}
              {currentView === "strategies" && t("common.strategies")}
            </h1>

            {/* Action cluster (guest settings or durable owner menu) */}
            <div className="flex shrink-0 justify-end pointer-events-auto">
              {currentView === "chat" && isGuest ? (
                <GuestHeader
                  expiresAt={account?.guest?.expires_at ?? null}
                  onFeedback={requestGuestFeedback}
                  onSignIn={requestGuestSignIn}
                />
              ) : currentView === "chat" &&
                conversationId &&
                canManageConversation ? (
                <ChatHeaderMenu
                  isOpen={showChatOptions}
                  onToggleOpen={() => setShowChatOptions(!showChatOptions)}
                  onRequestClose={closeChatOptions}
                  isRenaming={isRenamingHeaderChat}
                  renameValue={headerRenameValue}
                  onRenameValueChange={setHeaderRenameValue}
                  onStartRename={handleStartHeaderRename}
                  onSaveRename={() => void handleSaveHeaderRename()}
                  onCancelRename={() => setIsRenamingHeaderChat(false)}
                  isSavingRename={isSavingHeaderRename}
                  pinned={Boolean(activeHistoryChat?.pinned)}
                  isPinning={isPinningHeaderChat}
                  onTogglePin={() => void handleToggleHeaderPin()}
                  isDeleting={isDeletingHeaderChat}
                  onRequestDelete={handleRequestHeaderDelete}
                />
              ) : null}
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
            {showEmptyChatSurface ? (
              <div className="flex h-full flex-col items-center justify-start overflow-y-auto px-4 pb-8 pt-[24vh] sm:pt-[28vh]">
                <EmptyChatHeading isGuest={isGuest} />

                <div className="w-full max-w-2xl">
                  <ChatInput
                    key="new-conversation"
                    onSend={handleSend}
                    disabled={isStreamingResponse || isHydratingConversation}
                    placeholder={chatInputPlaceholder}
                    onToast={showToast}
                  />
                  <ChatLegalNotice
                    expiresAt={account?.guest?.expires_at}
                    isGuest={isGuest}
                    variant="before_message"
                  />
                </div>

                <StarterActions
                  disabled={isStreamingResponse || isHydratingConversation}
                  guestAnalyticsEnabled={guestExperience.isGuest}
                  onSelect={handleSend}
                />

                {chatExploratorySuggestionsEnabled && (
                  <div className="mt-4">
                    <button
                      onClick={() => setShowSuggestions(!showSuggestions)}
                      className="text-[14px] font-medium text-black/60 transition-colors hover:text-black dark:text-white/60 dark:hover:text-white"
                    >
                      {showSuggestions
                        ? t("chat.hide_suggestions")
                        : t("chat.show_suggestions")}
                    </button>
                  </div>
                )}

                {showExploratorySuggestions && (
                  <div className="mt-8 flex flex-col items-center gap-4 text-center">
                    <button
                      onClick={() =>
                        handleSend(
                          t(
                            "chat.example_queries.q1",
                            "What if I bought Apple after big drops?",
                          ),
                        )
                      }
                      className="text-[14px] text-black/50 hover:text-black hover:underline dark:text-white/50 dark:hover:text-white transition-colors"
                    >
                      {t(
                        "chat.example_queries.q1",
                        "What if I bought Apple after big drops?",
                      )}
                    </button>
                    <button
                      onClick={() =>
                        handleSend(
                          t(
                            "chat.example_queries.q2",
                            "What if I bought Bitcoin when it starts rising?",
                          ),
                        )
                      }
                      className="text-[14px] text-black/50 hover:text-black hover:underline dark:text-white/50 dark:hover:text-white transition-colors"
                    >
                      {t(
                        "chat.example_queries.q2",
                        "What if I bought Bitcoin when it starts rising?",
                      )}
                    </button>
                    <button
                      onClick={() =>
                        handleSend(
                          t(
                            "chat.example_queries.q3",
                            "What if I bought Tesla every month?",
                          ),
                        )
                      }
                      className="text-[14px] text-black/50 hover:text-black hover:underline dark:text-white/50 dark:hover:text-white transition-colors"
                    >
                      {t(
                        "chat.example_queries.q3",
                        "What if I bought Tesla every month?",
                      )}
                    </button>
                  </div>
                )}
              </div>
            ) : (
              <>
                <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-32 bg-[#f9f9f9]/80 backdrop-blur-[0.8px] [mask-image:linear-gradient(to_bottom,black_48%,transparent_100%)] dark:bg-[#141517]/80" />

                {showConversationRetrievalState &&
                  isHydratingConversation && (
                    <ConversationRetrievalAnnouncement />
                  )}

                {/* Messages */}
                <div
                  data-testid="conversation-transcript-region"
                  data-conversation-id={conversationId ?? undefined}
                  ref={scrollContainerRef}
                  onScroll={updateScrollPositionState}
                  role="region"
                  aria-label={t("common.conversation", "Conversation")}
                  aria-busy={isHydratingConversation}
                  className="argus-scrollbar flex-1 overflow-y-auto px-4 pb-[190px] pt-[86px]"
                >
                  <div className="space-y-8">
                    {showConversationRetrievalState &&
                      isHydratingConversation && (
                        <ConversationRetrievalState state="loading" />
                      )}
                    {failedConversationId === conversationId && (
                      <ConversationRetrievalState
                        state="error"
                        onRetry={() => {
                          if (failedConversationId) {
                            void loadConversation(failedConversationId);
                          }
                        }}
                      />
                    )}
                    {messages.map((msg, index) => {
                      const latestAiIndex = messages.findLastIndex(
                        (m) => m.role === "ai",
                      );
                      const isLatestAi =
                        msg.role === "ai" && latestAiIndex === index;
                      const isWorkingMessage =
                        isLatestAi &&
                        msg.kind === "text" &&
                        (isStreamingResponse ||
                          !!streamStatus ||
                          (msg.content ?? "") === "");
                      return (
                        <ChatMessage
                          key={msg.id}
                          message={msg}
                          onAction={handleAction}
                          onFeedback={(type, context, rating) => {
                            setFeedbackState({
                              isOpen: true,
                              type,
                              context: {
                                ...context,
                                conversation_id: conversationId,
                              },
                              rating,
                            });
                            setIsSidebarOpen(false);
                          }}
                          onToast={showToast}
                          isLatest={isLatestAi}
                          isStreaming={isWorkingMessage}
                          conversationId={conversationId}
                          nextMovesEnabled={nextMovesEnabled}
                          turnInFlight={turnInFlight}
                          isGuest={isGuest}
                          canSaveDecision={canSaveDecision}
                          onDecisionUnavailable={requestGuestDecision}
                          onDecisionSaved={() => { if (conversationId) invalidateTranscriptForMutation(conversationId, "durable_result_action"); }}
                          onRequestSearchUpgrade={requestGuestSearchUpgrade}
                          resumeDecisionArtifactId={
                            msg.id === resumeDecisionMessageId
                              ? resumeDecisionArtifactId
                              : null
                          }
                          onDecisionResumeHandled={clearResumeDecision}
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
                    <ChatInput
                      key={conversationId ?? "unowned-transcript"}
                      onSend={handleSend}
                      disabled={conversationComposerUnavailable}
                      placeholder={chatInputPlaceholder}
                      onToast={showToast}
                    />
                    <ChatLegalNotice
                      expiresAt={account?.guest?.expires_at}
                      isGuest={isGuest}
                      showRegisteredDisclaimer={showConversationDisclaimer}
                      variant="after_message"
                    />
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {strategiesEnabled && currentView === "strategies" && (
          <StrategiesView
            onMenuClick={() => setIsSidebarOpen((o) => !o)}
            onAddClick={() => handleTriggerPrompt("strategy")}
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

        <ChatToast message={toast} />
      </section>

      {/* ── Feedback Dialog ── */}
      <FeedbackDialog
        isOpen={feedbackState.isOpen}
        onClose={() => setFeedbackState((s) => ({ ...s, isOpen: false }))}
        type={feedbackState.type}
        rating={feedbackState.rating}
        context={feedbackState.context}
      />
      <GuestExperienceSurfaces experience={guestExperience} />
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
