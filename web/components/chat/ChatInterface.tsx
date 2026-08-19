"use client";

import { useCallback, useMemo, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useProfileUpdates } from "@/components/chat/useProfileUpdates";
import { useTranslation } from "react-i18next";
import { readStored, writeStored } from "@/lib/browser-storage";
import ChatCommandPalette from "@/components/sidebar/ChatCommandPalette";
import { KeyboardShortcutSurfaces } from "@/components/keyboard/KeyboardShortcutSurfaces";
import { useChatKeyboardShortcuts } from "@/components/keyboard/useChatKeyboardShortcuts";
import ChatSidebar, { type SidebarMode } from "@/components/sidebar/ChatSidebar";
import SidebarPreferenceModal from "@/components/settings/SidebarPreferenceModal";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import ConversationActivityAnnouncement from "@/components/chat/ConversationActivityAnnouncement";
import ConversationActivityRail from "@/components/chat/ConversationActivityRail";
import { ConversationActivityPresentationProvider } from "@/components/chat/ConversationActivityIndicator";
import { ConversationActivityJumpButton } from "@/components/chat/ConversationActivityJumpButton";
import ChatLegalNotice from "@/components/chat/ChatLegalNotice";
import ChatToast from "@/components/chat/ChatToast";
import { useChatToast } from "@/components/chat/useChatToast";
import EmptyChatSurface from "@/components/chat/EmptyChatSurface";
import {
  useInitialChatSession,
  type ProfileState,
} from "@/components/chat/useInitialChatSession";
import { executeChatTranscriptUpdateScroll, useChatScrollControls } from "@/components/chat/useChatScrollControls";
import { useChatSurfaceLifecycle } from "@/components/chat/useChatSurfaceLifecycle";
import { useArchiveActiveConversation } from "@/components/chat/useArchiveActiveConversation";
import { toggleConversationUnread } from "@/components/chat/toggleConversationUnread";
import { useRecentConversations } from "@/components/chat/useRecentConversations";
import { conversationActivityMutationNoticeDescriptor, useConversationActivity } from "@/components/chat/useConversationActivity";
import { clearConversationActivityTranscript, conversationActivityMutationRequiresCanonicalHydration, createConversationActivityTerminalReadinessSession, createConversationActivityTranscriptReadiness, promoteCanonicalConversationActivityTranscript, synchronizeConversationViewRefs, useConversationActivityViewport } from "@/components/chat/useConversationActivityViewport";
import GuestExperienceSurfaces from "@/components/guest/GuestExperienceSurfaces";
import GuestHeader from "@/components/guest/GuestHeader";
import ExpiredGuestSession from "@/components/guest/ExpiredGuestSession";
import {
  useGuestExperience,
  useGuestSendBridge,
  type GuestResumeSend,
} from "@/components/guest/useGuestExperience";
import {
  createConversation,
  deleteConversation,
  postFeedback,
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
  type BacktestRun, type BacktestJobResponse,
  type SearchConversationItem,
} from "@/lib/argus-api";
import type { KeyboardDeleteRequest } from "@/lib/keyboard-shortcuts";
import { omnisearchEnabled, researchRailEnabled } from "@/lib/private-alpha-flags";
import {
  useTranscriptTurnAnchor,
  type PendingMessageAnchor,
  type PendingScrollRestore,
} from "@/components/chat/useTranscriptTurnAnchor";
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
import { RETEST_ACTION_TYPE, applyRetestReceipt, retestReceiptFromFinalPayload, settleRetestReceiptProjection } from "@/lib/chat-retest";
import { omnisearchActionHandlers } from "./omnisearch-actions";
import { projectedTranscriptAnchorId } from "@/lib/chat-retry-action-history";
import {
  clearActiveConversationPointer,
  isCurrentAnchoredConversationRequest,
  readActiveConversationRouteState,
  rememberActiveConversationId,
  shouldApplyConversationOwnedUpdate,
  shouldStartConversationForVisibleEmptyChat,
  targetConversationIdForSend,
} from "@/lib/chat-conversation-routing";
import {
  conversationLoadFailureMessage,
  shouldShowEmptyChatSurface,
  shouldShowConversationDisclaimer,
} from "@/lib/chat-conversation-load-state";
import {
  COLD_TRANSCRIPT_RETRIEVAL_DELAY_MS,
  historyItemBelongsToConversation,
  isMissingConversationLoadError,
  POST_TURN_TITLE_REFRESH_DELAYS_MS,
} from "@/lib/chat-conversation-view-helpers";
import { activeConfirmationIdFrom } from "@/lib/chat-confirmation-peers";
import { mergeFinalTextMessage } from "@/lib/chat-final-message";
import {
  discoveryCandidateMention,
  discoverySidecarFromMetadata,
  researchSourcesForFinalPayload,
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
  strategyPathContextFromMetadata,
} from "@/lib/chat-message-hydration";
import {
  hydrateResultActionsForRun,
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
import { createConversationActivityCausalClock } from "@/lib/conversation-activity-state";
import {
  createChatRequestSessionController,
  type ChatRequestSession,
  visibleRequestStatus,
} from "@/lib/chat-request-session";
import { sidebarOpenAfterTransientNavigation } from "@/lib/sidebar-mode-state";
import {
  TranscriptSessionCache,
  type TranscriptMutation,
  type TranscriptNavigationState,
} from "@/lib/chat-transcript-session-cache";
import { renamePrefillTitle } from "@/lib/chat-title-display";
import { useActiveConversationTitle } from "@/lib/chat-header-title-state";
import SettingsView from "../views/SettingsView";
import ChatHeaderMenu from "./ChatHeaderMenu";
import ChatHeaderTitle from "./ChatHeaderTitle";
import ChatInput from "./ChatInput";
import ChatMessage from "./ChatMessage";
import ConversationRetrievalState, {
  ConversationRetrievalAnnouncement,
} from "./ConversationRetrievalState";
import FeedbackDialog from "../feedback/FeedbackDialog";
import { feedbackContextForSubmission } from "@/lib/feedback-context";
import {
  type ChatActionOption,
  type Message,
  type StrategyConfirmationPayload,
} from "./types";
import { confirmationSupersedingHandlers } from "./confirmation-superseding";
import {
  chatActionRequestFromAction, chatHttpErrorDisplay,
  chatStreamErrorText,
  consumeConfirmationActionOnMessages,
  hasActiveArtifactActionSet,
  hydrateMessagesFromApi,
  isFailedActionRetry,
  markComposerActionsInactive,
  messageStreamPresentation,
  messagesWithSavedDecisionState,
  settleOpenConfirmationsFromFinalPayload,
} from "./chat-message-projection";
import { openFeedbackDialogState } from "./feedback-dialog-state";
import { messageElementRegistrar } from "./transcript-element-refs";
import { isGuestSimulationConversionRejection } from "@/lib/guest-conversion-recovery";
import SidebarShell from "@/components/sidebar/SidebarShell";
import ChatShellMenuTrigger from "@/components/chat/ChatShellMenuTrigger";
import GuestSettingsMenu from "@/components/guest/GuestSettingsMenu";
import { useMobileShell } from "@/components/chat/useMobileShell";
import { memoryRecallsFromFinalPayload, useMemoryChrome } from "./memory-chrome";
import {
  isStarterSelectionMetadata,
  type GuestPendingSubmission,
  type SendOptions,
  type SendSelection,
} from "./chat-send-selection";
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
  settleOpenConfirmationsAfterStreamError,
} from "./artifact-history";
import { randomId } from "@/lib/random-id";
import { SEND_BUSY_FALLBACK, SEND_GENERIC_FALLBACK, sendRefusal } from "@/lib/send-refusal";
type View = "chat" | "settings";

const JUMP_TO_LATEST_THRESHOLD_PX = 240;
// ─── Component ────────────────────────────────────────────────────────────────
export default function ChatInterface() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const [account, setAccount] = useState<Awaited<
    ReturnType<typeof getMe>
  > | null>(null);
  const [profileState, setProfileState] = useState<ProfileState>("probing");
  const [expiredPublicAccountAccessEnabled, setExpiredPublicAccountAccessEnabled] =
    useState(false);
  const refreshAccount = useCallback(async () => {
    const nextAccount = await getMe();
    if (nextAccount === null) return null;
    setAccount(nextAccount);
    const resolvedLanguage = nextAccount.user.language ?? i18n.language;
    if (resolvedLanguage && resolvedLanguage !== i18n.language) {
      await i18n.changeLanguage(resolvedLanguage);
    }
    setProfileState("established");
    return nextAccount;
  }, [i18n]);
  const { onProfileUpdated, greetingName } = useProfileUpdates(account, setAccount);
  const [messages, setMessages] = useState<Message[]>([]);
  // Long-lived handlers (the undo toast) need the current transcript, not
  // the render that created them.
  const latestMessagesRef = useRef<Message[]>([]);
  useEffect(() => {
    latestMessagesRef.current = messages;
  }, [messages]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [currentView, setCurrentView] = useState<View>("chat");
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const mobileShell = useMobileShell();
  const [searchOverlayOpen, setSearchOverlayOpen] = useState(false);
  const [showChatOptions, setShowChatOptions] = useState(false);
  const [pendingHeaderDelete, setPendingHeaderDelete] = useState<KeyboardDeleteRequest | null>(null);
  const [isDeletingHeaderChat, setIsDeletingHeaderChat] = useState(false);
  const [headerRenameValue, setHeaderRenameValue] = useState("");
  const [isRenamingHeaderChat, setIsRenamingHeaderChat] = useState(false);
  const [isSavingHeaderRename, setIsSavingHeaderRename] = useState(false);
  const [isPinningHeaderChat, setIsPinningHeaderChat] = useState(false);
  const [streamStatus, setStreamStatus] = useState<string | null>(null);
  const [activityCausalClock] = useState(createConversationActivityCausalClock);
  const [activityTranscriptReadiness] = useState(createConversationActivityTranscriptReadiness);
  const {
    historyItems,
    historyActivityRevision,
    setHistoryItems,
    historyNextCursor,
    isLoadingMoreHistory,
    hasRequestedOlderHistory,
    historyLoadMoreError,
    loadHistoryPage,
    clearHistory,
    loadMoreHistory,
    refreshHistory,
    refreshHistoryForActivity,
  } = useRecentConversations({
    guestExpiresAt: account?.guest?.expires_at,
    activityCausalClock,
  });
  const [guestSubmissionPending, setGuestSubmissionPending] = useState(false);
  const [guestSubmissionError, setGuestSubmissionError] = useState(false);
  const [isHydratingConversation, setIsHydratingConversation] = useState(false);
  const [showConversationRetrievalState, setShowConversationRetrievalState] =
    useState(false);
  const [failedConversationId, setFailedConversationId] = useState<string | null>(null);
  const { toast, showToast, hideToast } = useChatToast();
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
  const latestActivitySentinelRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const shouldAutoScrollRef = useRef(true);
  const postTurnHistoryRefreshTimersRef = useRef<number[]>([]);
  const activeConversationIdRef = useRef<string | null>(null);
  const hasAcceptedUserInputRef = useRef(false);
  const guestSendRef = useRef<GuestResumeSend | null>(null);
  const sendAdmissionInFlightRef = useRef(false);
  const guestSubmissionRetryRef = useRef<GuestPendingSubmission | null>(null);
  const currentViewRef = useRef<View>("chat");
  const [transcriptSessionCache] = useState(
    () => new TranscriptSessionCache<Message[]>(),
  );
  const coldRetrievalTimerRef = useRef<number | null>(null);
  const coldRetrievalConversationIdRef = useRef<string | null>(null);
  const authenticatedUserIdRef = useRef<string | null>(null);
  const readyTranscriptConversationIdRef = useRef<string | null>(null);
  const pendingScrollRestoreRef = useRef<PendingScrollRestore>(null);
  const pendingMessageAnchorRef = useRef<PendingMessageAnchor>(null);
  const messageElementRefs = useRef(new Map<string, HTMLDivElement>());
  const [showJumpToLatest, setShowJumpToLatest] = useState(false);
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
        conversationActivityMutationRequiresCanonicalHydration(mutation)
      ) {
        clearConversationActivityTranscript(activityTranscriptReadiness, readyTranscriptConversationIdRef);
      }
    },
    [account?.user.id, activityTranscriptReadiness, transcriptSessionCache],
  );
  const invalidateInactiveActivityTranscript = useCallback(
    (targetConversationId: string) =>
      invalidateTranscriptForMutation(targetConversationId, "durable_job_completion"),
    [invalidateTranscriptForMutation],
  );
  const conversationActivity = useConversationActivity({
    historyItems,
    historyActivityRevision,
    activeConversationId: currentView === "chat" ? conversationId : null,
    accountScopeKey: account?.user.id ?? null,
    refreshHistory: refreshHistoryForActivity,
    invalidateInactiveTranscript: invalidateInactiveActivityTranscript,
    onMutationNotice: (notice) => {
      const descriptor = conversationActivityMutationNoticeDescriptor(notice);
      showToast(t(descriptor.key, descriptor.defaultValue), descriptor.variant);
    },
    causalClock: activityCausalClock,
  });
  const [requestSessions] = useState(() =>
    createChatRequestSessionController({
      activity: conversationActivity,
      accountScopeKey: account?.user.id ?? null,
      routeContext: {
        activeConversationId: conversationId,
        currentView,
        routeState: readActiveConversationRouteState(),
      },
    }),
  );
  const isStreamingResponse = conversationActivity.isConversationLocked(conversationId);
  const visibleStreamStatus = visibleRequestStatus(streamStatus, isStreamingResponse);
  const reloadActiveTranscriptRef = useRef<(conversationId: string) => void>(
    () => {},
  );
  useEffect(() => {
    reloadActiveTranscriptRef.current = (targetConversationId) => {
      // A locked (mid-stream) conversation reconciles through its own
      // terminal path instead of a competing reload.
      if (conversationActivity.isConversationLocked(targetConversationId)) return;
      void navigateConversationTranscript(targetConversationId);
    };
  });
  const handleDurableJobCompletion = useCallback((response: BacktestJobResponse) => {
      const targetConversationId = response.job.conversation_id;
      invalidateTranscriptForMutation(targetConversationId, "durable_job_completion");
      const promoted = promoteCanonicalConversationActivityTranscript({ conversationId: targetConversationId, activeConversationIdRef, currentViewRef, readyTranscriptConversationIdRef, transcriptReadiness: activityTranscriptReadiness });
      // A research job's answer arrives as a new assistant message, not a
      // card update; the active view must refetch it or "the full answer is
      // below" renders above nothing.
      if (promoted && response.job.operation_scope === "chat.research") {
        reloadActiveTranscriptRef.current(targetConversationId);
      }
    }, [activityTranscriptReadiness, invalidateTranscriptForMutation]);
  useBacktestJobPolling(messages, canApplyConversationOwnedUpdate, setMessages, handleDurableJobCompletion);

  const retireActiveTranscriptPresentationForNavigation = useCallback(() => {
    setStreamStatus(null);
  }, []);

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
    clearConversationActivityTranscript(activityTranscriptReadiness, readyTranscriptConversationIdRef);
    setFailedConversationId(null);
    setIsHydratingConversation(false);
  }, [activityTranscriptReadiness, clearColdTranscriptRetrieval, transcriptSessionCache]);

  useLayoutEffect(() => {
    requestSessions.synchronizeAccountScope(account?.user.id ?? null);
    requestSessions.updateRouteContext({
      activeConversationId: conversationId,
      currentView,
      routeState: readActiveConversationRouteState(),
    });
  }, [account?.user.id, conversationId, currentView, requestSessions]);

  useLayoutEffect(() => {
    synchronizeConversationViewRefs(activeConversationIdRef, currentViewRef, conversationId, currentView);
  }, [conversationId, currentView]);

  const resetToEmptyChatSurface = useCallback(
    (nextConversationId: string | null = null) => {
      cancelTranscriptNavigation();
      retireActiveTranscriptPresentationForNavigation();
      if (nextConversationId) {
        rememberActiveConversationId(nextConversationId);
      } else {
        const clearedRoute = clearActiveConversationPointer();
        if (clearedRoute) router.replace(clearedRoute, { scroll: false });
      }
      synchronizeConversationViewRefs(activeConversationIdRef, currentViewRef, nextConversationId, "chat");
      hasAcceptedUserInputRef.current = false;
      setConversationId(nextConversationId);
      setMessages([]);
      setStreamStatus(null);
      setIsHydratingConversation(false);
      setShowChatOptions(false);
      setIsRenamingHeaderChat(false);
      setHeaderRenameValue("");
      setCurrentView("chat");
    },
    [
      cancelTranscriptNavigation,
      retireActiveTranscriptPresentationForNavigation,
      router,
    ],
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
  }, [account?.user.id, resetToEmptyChatSurface, transcriptSessionCache]);

  // ── History ────────────────────────────────────────────────────────────────

  function schedulePostTurnHistoryRefresh(
    targetConversationId?: string | null,
    isAccountCurrent: () => boolean = () => true,
  ) {
    let settled = false;

    const refreshAndCheckTitle = async () => {
      if (settled || !isAccountCurrent()) return;
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

  function finishRequestTransport(session: ChatRequestSession) {
    if (!requestSessions.finishTransport(session)) return false;
    schedulePostTurnHistoryRefresh(
      session.identity.conversationId,
      () => requestSessions.isAccountCurrent(session),
    );
    return true;
  }
  useEffect(
    () => () => {
      for (const timerId of postTurnHistoryRefreshTimersRef.current) {
        window.clearTimeout(timerId);
      }
      postTurnHistoryRefreshTimersRef.current = [];
      transcriptSessionCache.clearAuthenticatedState();
      if (coldRetrievalTimerRef.current !== null) {
        window.clearTimeout(coldRetrievalTimerRef.current);
      }
    },
    [transcriptSessionCache],
  );

  useEffect(() => {
    if (!isSidebarOpen) {
      setIsRecentsExpanded(false);
    }
  }, [isSidebarOpen]);

  useEffect(() => {
    const saved = readStored("argus:sidebar_mode") as SidebarMode | null;
    if (saved === "expanded" || saved === "collapsed" || saved === "hover") {
      setSidebarMode(saved);
      setIsSidebarOpen(saved === "expanded");
    }
  }, []);

  const handleSetSidebarMode = (mode: SidebarMode) => {
    setSidebarMode(mode);
    writeStored("argus:sidebar_mode", mode);
    if (mode === "expanded") setIsSidebarOpen(true);
    if (mode === "collapsed" || mode === "hover") setIsSidebarOpen(false);
  };

  const toggleSidebar = () => {
    setIsSidebarOpen((open) => !open);
  };

  const closeDrawer = mobileShell.closeDrawer;
  const closeTransientSidebar = useCallback(() => {
    // Navigating out of the drawer always dismisses it; the rail keeps its own
    // transient rule, which depends on the user's sidebar mode.
    closeDrawer();
    setIsSidebarOpen((currentOpen) =>
      sidebarOpenAfterTransientNavigation({
        currentOpen,
        mode: sidebarMode,
      }),
    );
  }, [closeDrawer, sidebarMode]);

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
    clearConversationActivityTranscript(activityTranscriptReadiness, readyTranscriptConversationIdRef);
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
    options: Readonly<{
      bootstrap?: boolean;
      messageId?: string;
      scrollToLatest?: boolean;
    }> = {},
  ): Promise<void> {
    if (!userId) return;
    rememberCurrentConversationScroll();
    retireActiveTranscriptPresentationForNavigation();
    rememberActiveConversationId(targetConversationId, options.messageId);
    activeConversationIdRef.current = targetConversationId;
    currentViewRef.current = "chat";
    setConversationId(targetConversationId);
    setCurrentView("chat");
    setStreamStatus(null);
    setShowChatOptions(false);

    if (options.messageId) {
      const requestedMessageId = options.messageId;
      transcriptSessionCache.cancelActiveNavigation();
      beginColdTranscriptRetrieval(targetConversationId);
      const isCurrentRequest = () =>
        isCurrentAnchoredConversationRequest({
          activeConversationId: activeConversationIdRef.current,
          targetConversationId,
          routeState: readActiveConversationRouteState(),
          requestedMessageId,
        });
      try {
        const items = await loadAllConversationMessagePages(
          targetConversationId,
        );
        if (!isCurrentRequest()) return;
        const snapshot = hydrateMessagesFromApi(items).messages;
        const anchorMessageId = projectedTranscriptAnchorId(snapshot, requestedMessageId);
        if (!anchorMessageId) throw new Error("Transcript anchor was not returned.");
        clearColdTranscriptRetrieval();
        setIsHydratingConversation(false);
        readyTranscriptConversationIdRef.current = targetConversationId;
        activityTranscriptReadiness.stageCanonical(targetConversationId);
        pendingScrollRestoreRef.current = null;
        pendingMessageAnchorRef.current = {
          conversationId: targetConversationId,
          messageId: anchorMessageId,
        };
        shouldAutoScrollRef.current = false;
        setMessages(snapshot);
      } catch (error) {
        if (!isCurrentRequest()) return;
        clearColdTranscriptRetrieval();
        setIsHydratingConversation(false);
        clearConversationActivityTranscript(activityTranscriptReadiness, readyTranscriptConversationIdRef);
        pendingMessageAnchorRef.current = null;
        setMessages([]);
        if (options.bootstrap && isMissingConversationLoadError(error)) {
          resetToEmptyChatSurface();
          return;
        }
        setFailedConversationId(targetConversationId);
      }
      return;
    }

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
          activityTranscriptReadiness.stageCached(targetConversationId);
          stageTranscriptSnapshot(
            targetConversationId,
            userId,
            state.snapshot,
            options.scrollToLatest ? null : undefined,
          );
          return;
        }
        if (state.phase === "ready") {
          const currentScrollTop = options.scrollToLatest
            ? null
            : renderedStaleSnapshot &&
                readyTranscriptConversationIdRef.current ===
                  targetConversationId
              ? (scrollContainerRef.current?.scrollTop ?? null)
              : undefined;
          activityTranscriptReadiness.stageCanonical(targetConversationId);
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
          activityTranscriptReadiness.stageCached(targetConversationId);
          setMessages(state.snapshot);
          return;
        }
        clearConversationActivityTranscript(activityTranscriptReadiness, readyTranscriptConversationIdRef);
        pendingScrollRestoreRef.current = null;
        setMessages([]);
        if (options.bootstrap && isMissingConversationLoadError(state.error)) {
          setHistoryItems((current) =>
            current.filter(
              (item) =>
                !historyItemBelongsToConversation(item, targetConversationId),
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
  function beginConversationActivityTerminalReadiness(getRequest: () => ChatRequestSession) { const terminalReadiness = createConversationActivityTerminalReadinessSession({ getRequest: () => ({ conversationId: getRequest().identity.conversationId, kind: getRequest().kind }), activeConversationIdRef, currentViewRef, readyTranscriptConversationIdRef, transcriptReadiness: activityTranscriptReadiness, reconcileCanonical: (id) => void navigateConversationTranscript(id) }); terminalReadiness.stage(); return terminalReadiness; }
  // ── Init conversation ──────────────────────────────────────────────────────

  useInitialChatSession({
    hasAcceptedUserInputRef,
    setAccount,
    setProfileState,
    setMessages,
    setIsHydratingConversation,
    resetToEmptyChatSurface,
    navigateConversationTranscript,
    cancelActiveNavigation: () => transcriptSessionCache.cancelActiveNavigation(),
  });

  const { scrollToLatest, updateScrollPositionState } = useChatScrollControls({
    accountUserId: account?.user.id,
    activeConversationIdRef,
    readyTranscriptConversationIdRef,
    bottomRef,
    scrollContainerRef,
    shouldAutoScrollRef,
    transcriptSessionCache,
    setShowJumpToLatest,
  });

  const { anchorToTurn } = useTranscriptTurnAnchor({
    conversationId,
    messages,
    jumpToLatestThresholdPx: JUMP_TO_LATEST_THRESHOLD_PX,
    activeConversationIdRef,
    pendingMessageAnchorRef,
    pendingScrollRestoreRef,
    messageElementRefs,
    scrollContainerRef,
    shouldAutoScrollRef,
    setShowJumpToLatest,
  });

  useConversationActivityViewport({
    activity: conversationActivity, accountScopeKey: account?.user.id ?? null,
    activeRouteConversationId: currentView === "chat" ? readActiveConversationRouteState().conversationId : null,
    activeConversationId: currentView === "chat" ? conversationId : null,
    activeConversationIdRef, readyTranscriptConversationIdRef,
    transcriptRootRef: scrollContainerRef, sentinelRef: latestActivitySentinelRef,
    transcriptReadiness: activityTranscriptReadiness,
    pendingScrollRestoreRef, pendingMessageAnchorRef,
    hydrationComplete: !isHydratingConversation,
  });

  useEffect(() => {
    executeChatTranscriptUpdateScroll({ shouldAutoScrollRef, scrollToLatest, updateScrollPositionState });
  }, [messages.length, scrollToLatest, streamStatus, updateScrollPositionState]);

  // ── Load existing conversation ─────────────────────────────────────────────

  const loadConversation = async (
    convId: string, messageId?: string, scrollToLatest = false,
  ) => {
    closeChatOptions();
    await navigateConversationTranscript(
      convId, undefined, { messageId, scrollToLatest },
    );
  };

  const loadConversationForRun = async (
    item: Pick<HistoryItem | SearchConversationItem, "id" | "conversation_id">,
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

  const openHistoryItem = (item: HistoryItem | SearchConversationItem) => {
    if (item.type === "chat") {
      void loadConversation(item.id);
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
      clearConversationActivityTranscript(activityTranscriptReadiness, readyTranscriptConversationIdRef);
      pendingScrollRestoreRef.current = null;
    },
  });
  const archiveActiveConversation = useArchiveActiveConversation({
    conversationId, onArchived: handleConversationRemoved,
    onSuccess: () => showToast(t("common.archive", "Archive")), onError: () => showToast(t("common.error_occurred"), "error"),
  });
  const guestBootstrapRequired = profileState === "bootstrap_required";
  const guestExperience = useGuestExperience({
    account,
    guestBootstrapRequired,
    conversationId,
    messages,
    sendRef: guestSendRef,
    refreshAccount,
    refreshHistory,
    refreshHistoryForActivity,
    closeTransientSidebar,
    startNewChat,
    onOpenFeedback: () =>
      setFeedbackState({
        isOpen: true,
        type: "general",
        context: { surface: "guest_header", conversation_id: conversationId },
      }),
    // The one door into Omnisearch, so the drawer closes here rather than at
    // each caller. The palette paints below the drawer, and gating the shortcut
    // hook alone still left the guest shell's own key listener opening it into
    // a layer nobody can see.
    onOpenOmnisearch: () => {
      closeDrawer();
      setSearchOverlayOpen(true);
    },
    onRequestPendingGuestSignIn: () => router.push("/?auth=login"),
    onAdoptConversation: adoptGuestConversation,
    onGuestBootstrapExpired: (publicAccountAccessEnabled) => {
      guestSubmissionRetryRef.current = null;
      setGuestSubmissionError(false);
      setExpiredPublicAccountAccessEnabled(publicAccountAccessEnabled);
      setProfileState("expired");
    },
    onGuestBootstrapError: () => setGuestSubmissionError(true),
    onGateError: () => showToast(t("chat.error_generic"), "error"),
    onStartOverError: () =>
      showToast(
        t(
          "guest.new_conversation.error",
          "The temporary chat was left unchanged.",
        ),
        "error",
      ),
    // The single owner of the Omnisearch shortcut; useChatKeyboardShortcuts
    // never claims it. Whether any surface is open is asked at press time
    // against the layer registry, rather than named here one surface at a
    // time: naming only the drawer left the same bug behind every other modal.
    // Withheld below the mobile threshold on the same rule as the rest of the
    // layer, so there is one answer to whether this width has shortcuts.
    omnisearchShortcutEnabled: omnisearchEnabled && !mobileShell.isBelowTablet,
  });
  const {
    isGuest,
    canManageConversation,
    canSaveDecision,
    canUseOmnisearch,
    canUseGroundedDiscovery,
    canSubmitFeedback,
    requestGuestDecision,
    requestGuestFeedback,
    requestGuestSearchUpgrade,
    requestGuestSignIn,
    requestNewChat,
    requestOmnisearch,
    recoverGuestSimulationRejection,
    resumeDecisionTarget,
    resumeDecisionArtifactId,
    resumeDecisionMessageId,
    clearResumeDecision,
  } = guestExperience;

  const memoryChrome = useMemoryChrome(isGuest, conversationId);

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

  const handleMessageFeedback = useCallback(
    async (
      type: "bug" | "feature" | "general" | "rating",
      context: Record<string, unknown> | undefined,
      rating?: "positive" | "negative",
    ) => {
      if (type === "rating" && rating) {
        try {
          await postFeedback({
            type: "general",
            message: t("feedback.rating_message_fallback", { rating }),
            context: feedbackContextForSubmission(context, {
              includeConversationContext: true,
              rating,
              tags: [],
              attachmentCount: 0,
            }),
          });
        } catch {
          showToast(
            t(
              "feedback.error",
              "We could not submit that yet. Please try again.",
            ),
            "error",
          );
        }
        return;
      }

      setFeedbackState(
        openFeedbackDialogState(type, context, rating, conversationId),
      );
      setIsSidebarOpen(false);
    },
    [conversationId, showToast, t],
  );

  // ── Send message ───────────────────────────────────────────────────────────

  const handleSend = async (
    text: string,
    mentionsOrAction?: SendSelection,
    actionArg?: ChatActionOption,
    options?: SendOptions,
  ) => {
    const trimmed = text.trim();
    let guestSubmissionHandedToStream = false;
    // Never decline a real message in silence; see lib/send-refusal.ts.
    const refuseSend = sendRefusal(showToast, t);
    if (!trimmed) return false;
    if (sendAdmissionInFlightRef.current || isStreamingResponse) {
      return false;
    }
    const mentions = Array.isArray(mentionsOrAction) ? mentionsOrAction : [];
    const starterSelection = isStarterSelectionMetadata(mentionsOrAction)
      ? mentionsOrAction
      : undefined;
    const action: ChatActionOption | undefined = Array.isArray(mentionsOrAction)
      ? actionArg
      : starterSelection
        ? undefined
        : (mentionsOrAction as ChatActionOption | undefined);
    const isDeferredGuestSubmission =
      guestBootstrapRequired && !options?.bypassGuestGate;

    sendAdmissionInFlightRef.current = true;
    if (isDeferredGuestSubmission) {
      guestSubmissionRetryRef.current = {
        text,
        mentionsOrAction,
        actionArg,
        options,
      };
      setGuestSubmissionError(false);
      setGuestSubmissionPending(true);
      setStreamStatus(t("guest.entry.sending", "Sending..."));
    }

    try {
    if (
      !options?.bypassGuestGate &&
      !(await guestExperience.admitSend({
        text: trimmed,
        mentions,
        action,
        starterSelection,
        language: i18n.resolvedLanguage ?? i18n.language,
      }))
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
        showToast(t("chat.error_generic"), "error");
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
        showToast(t("chat.error_generic"), "error");
        return false;
      }
    }

    if (!targetConversationId) {
      return refuseSend("chat.error_generic", SEND_GENERIC_FALLBACK);
    }
    if (conversationActivity.isConversationLocked(targetConversationId)) {
      return refuseSend("chat.send_busy", SEND_BUSY_FALLBACK);
    }
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
    synchronizeConversationViewRefs(activeConversationIdRef, currentViewRef, targetConversationId, "chat");

    closeTransientSidebar();
    shouldAutoScrollRef.current = true;
    const renderUserMessage = options?.renderUserMessage ?? !isRetryAction(action);

    const userMsg: Message = {
      id: randomId(),
      role: "user",
      kind: action?.type ? "action" : "text",
      content: action?.type ? actionDisplayLabel(action) : trimmed,
      mentions,
      selectedAction: action,
      retestReceiptPending: action?.type === RETEST_ACTION_TYPE,
    };
    const assistantId = replacementAssistantId ?? randomId();
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
    if (!isDeferredGuestSubmission) setStreamStatus(null);

    const streamInput: string | ChatActionRequest = action?.type
      ? chatActionRequestFromAction(action)
      : trimmed;
    const requestKind =
      action?.type === "run_backtest" ? "backtest_job" : "chat_turn";
    const initialRequestSession = requestSessions.begin(
      targetConversationId,
      requestKind,
    );
    if (!initialRequestSession) return refuseSend("chat.send_busy", SEND_BUSY_FALLBACK);
    guestSubmissionRetryRef.current = null;
    let requestSession: ChatRequestSession = initialRequestSession;
    const terminalReadiness = beginConversationActivityTerminalReadiness(() => requestSession);
    const ordinaryTransportMessageIds =
      action?.type === "run_backtest"
        ? null
        : await snapshotOrdinaryTransportMessageIds(async () =>
            loadAllConversationMessagePages(targetConversationId),
          );

    const canApplyVisibleStreamUpdate = () =>
      requestSessions.canWriteVisible(requestSession);
    const clearNeutralGuestSubmission = () => { if (isDeferredGuestSubmission) setGuestSubmissionPending(false); };
    const recoverQuotaRejectedRun = (failureCode: unknown) => {
      if (!isGuestSimulationConversionRejection(failureCode, action) || !recoverGuestSimulationRejection(action)) return false;
      void loadConversation(requestSession.identity.conversationId);
      finishRequestTransport(requestSession);
      return true;
    };
    const handleStreamEvent = (event: ChatStreamEvent) => {
      if (event.event === "stage_start") {
        if (!requestSessions.authorize(requestSession, "stage")) return;
        conversationActivity.progressRequest(
          requestSession.identity.conversationId,
          requestSession.identity.requestId,
          "running",
        );
        clearNeutralGuestSubmission();
        if (!canApplyVisibleStreamUpdate()) return;
        const stageKey = `chat.status.${event.data.stage}`;
        const detail = event.data.detail;
        setStreamStatus(
          (detail ? t(`${stageKey}_detail`, { detail }) || t(stageKey) : t(stageKey)) ||
            t("chat.status.preparing"),
        );
      }
      if (event.event === "token") {
        if (!requestSessions.authorize(requestSession, "token")) return;
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
        if (!requestSessions.authorize(requestSession, "error")) return;
        clearNeutralGuestSubmission();
        const errorPayload = event.data as typeof event.data & Record<string, unknown>;
        if (recoverQuotaRejectedRun(errorPayload.code)) return;
        throwIfAmbiguousRunSseError(event, action?.type === "run_backtest");
        if (!canApplyVisibleStreamUpdate()) {
          finishRequestTransport(requestSession);
          return;
        }
        const persistedErrorMessageId = event.data.message_id?.trim();
        const errorRecoveryDisplay = recoveryDisplayFromMetadata(errorPayload);
        const errorStrategyPathContext = strategyPathContextFromMetadata(errorPayload);
        // Same gate the `final` frame applies: a retryable failure wears the
        const errorAssistantRecoveryCode = retryableAssistantRecoveryCode(
          errorPayload.recovery,
        );
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
        setMessages((prev) =>
          normalizeDurableRetryActionHistory(
            settleOpenConfirmationsAfterStreamError(
              applyRetestReceipt(prev, userMsg.id, null).map((m) =>
                durableRetry && m.id === userMsg.id
                  ? {
                      ...m,
                      id: durableRetry.requestMessageId,
                      content: durableRetry.persistedMessage,
                      recoveryDisplay: errorRecoveryDisplay,
                      strategyPathContext: errorStrategyPathContext,
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
                        strategyPathContext: errorStrategyPathContext,
                        assistantRecoveryCode: errorAssistantRecoveryCode,
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
        if (!terminalReadiness.accept({ message_id: event.data.message_id, recovery: event.data.recovery ?? null, retry_last_turn: event.data.retry_last_turn ?? null }, true)) terminalReadiness.finish(true);
        finishRequestTransport(requestSession);
      }
      if (event.event === "final") {
        const identityAuthorized = requestSessions.authorize(requestSession, "final");
        if (!identityAuthorized) return;
        clearNeutralGuestSubmission();
        setStreamStatus(null);
        const finalPayload = event.data as typeof event.data & Record<string, unknown>;
        if (recoverQuotaRejectedRun((finalPayload.final_response_payload as { code?: unknown } | undefined)?.code ?? finalPayload.code)) return;
        const finalText =
          event.data.assistant_response ?? event.data.assistant_prompt ?? "";
        const finalStageOutcome = event.data.stage_outcome;
        const finalMessageId =
          typeof finalPayload.message_id === "string"
            ? finalPayload.message_id
            : undefined;
        setMessages((prev) =>
          applyRetestReceipt(prev, userMsg.id, retestReceiptFromFinalPayload(finalPayload)),
        );
        const finalRecoveryDisplay = recoveryDisplayFromMetadata(finalPayload);
        const finalStrategyPathContext =
          strategyPathContextFromMetadata(finalPayload);
        const finalAssistantRecoveryCode = retryableAssistantRecoveryCode(
          finalPayload.recovery,
        );
        const finalDiscovery = discoverySidecarFromMetadata(finalPayload);
        const finalMemoryRecalls = memoryRecallsFromFinalPayload(finalPayload);
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
        if (
          finalAssistantRecoveryCode &&
          !finalTextActions.some(isFailedActionRetry) &&
          text.trim()
        ) {
          const compositionRetry = retryLastTurnActionFromMessage(text, {
            assistantMessageId: finalMessageId ?? assistantId,
          });
          if (compositionRetry) finalTextActions.push(compositionRetry);
        }
        const finalHasFailedAction = hasFailedActionMetadata(finalPayload);
        const finalBacktestJob = backtestJobFromFinalPayload(finalPayload);
        if (event.data.confirmation) {
          const confirmation = event.data
            .confirmation as StrategyConfirmationPayload;
          const finalAssistantId = finalMessageId ?? assistantId;
          // Researched peer adds ride the ordinary Try-next surface below
          // the card's turn (research rail, spec section 6).
          const confirmationNextExperiments =
            nextExperimentRowsFromMetadata(finalPayload) ?? undefined;
          setMessages((prev) =>
            normalizeDurableRetryActionHistory(
              normalizeConfirmationHistory(
                replaceOrAppendFinalAssistantMessage(prev, assistantId, {
                  id: finalAssistantId,
                  role: "ai",
                  kind: "strategy_confirmation",
                  content: undefined,
                  confirmation,
                  strategyPathContext: finalStrategyPathContext,
                  actions: confirmation.actions ?? [],
                  nextExperiments: confirmationNextExperiments,
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
            savedStrategyId: run.strategy_id ?? null,
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
                  memoryRecalls: finalMemoryRecalls,
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
          const finalTextNextExperiments =
            nextExperimentRowsFromMetadata(finalPayload) ?? undefined;
          const finalResearchSources = researchSourcesForFinalPayload(finalPayload);
          const finalTextPresentation =
            action?.type === "show_breakdown" ? "result_breakdown" : undefined;
          setMessages((prev) => {
            const finalAssistantId = finalMessageId ?? assistantId;
            const nextMessages = replaceOrAppendFinalAssistantMessage(
              prev.map((m) =>
                mergeFinalTextMessage(m, {
                  assistantId,
                  finalText,
                  finalActions: finalTextActions,
                  recoveryDisplay: finalRecoveryDisplay,
                  strategyPathContext: finalStrategyPathContext,
                  assistantRecoveryCode: finalAssistantRecoveryCode,
                  discovery: finalDiscovery,
                  memoryRecalls: finalMemoryRecalls,
                  researchSources: finalResearchSources,
                  nextExperiments: finalTextNextExperiments,
                  contentPresentation: finalTextPresentation,
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
                strategyPathContext: finalStrategyPathContext,
                assistantRecoveryCode: finalAssistantRecoveryCode,
                discovery: finalDiscovery,
                memoryRecalls: finalMemoryRecalls,
                researchSources: finalResearchSources,
                nextExperiments: finalTextNextExperiments,
                contentPresentation: finalTextPresentation,
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
        } else {
          // A final frame with neither prose nor an artifact must still yield
          // a visible assistant turn; an empty placeholder reads as the app
          // dying silently. The generic turn-failure copy is the honest
          // render, and it is localized in both bundles.
          setMessages((prev) =>
            normalizeDurableRetryActionHistory(
              replaceOrAppendFinalAssistantMessage(prev, assistantId, {
                id: finalMessageId ?? assistantId,
                role: "ai",
                kind: "text",
                content: t("chat.error_backtest"),
                actions:
                  finalTextActions.length > 0 ? finalTextActions : undefined,
              }),
            ),
          );
        }
        terminalReadiness.accept(event.data, identityAuthorized);
      }
      if (event.event === "title") {
        if (
          !requestSessions.authorize(
            requestSession,
            "title",
            event.data.conversation_id,
          )
        ) return;
        setHistoryItems((prev) =>
          prev.map((item) =>
            item.id === requestSession.identity.conversationId
              ? { ...item, title: event.data.title }
              : item,
          ),
        );
      }
      if (event.event === "done") {
        if (!requestSessions.authorize(requestSession, "done")) return;
        clearNeutralGuestSubmission();
        setMessages((prev) => applyRetestReceipt(prev, userMsg.id, null));
        terminalReadiness.finish(true); finishRequestTransport(requestSession);
      }
    };
    const moveRequestToConversation = (nextConversationId: string) => {
      const transferred = requestSessions.transfer(
        requestSession,
        nextConversationId,
      );
      if (!transferred) return false;
      requestSession = transferred;
      return true;
    };
    const streamToConversation = async (nextTargetConversationId: string) => {
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
        {
          requestId: requestSession.identity.requestId,
          signal: requestSession.controller.signal,
        },
      );
      throwIfAmbiguousRunStreamTermination(
        action?.type === "run_backtest",
        runStreamFinalSeen,
      );
    };

    guestSubmissionHandedToStream = true;
    void (async () => {
      try {
        await streamToConversation(targetConversationId);
      } catch (err: unknown) {
        if (!requestSessions.authorize(requestSession, "catch")) return;
        if (
          err instanceof ChatStreamError &&
          err.status === 404 &&
          !action?.type
        ) {
          try {
            const retryWasVisible = canApplyVisibleStreamUpdate();
            if (retryWasVisible) clearActiveConversationPointer();
            const { conversation } = await createConversation(i18n.language);
            if (!moveRequestToConversation(conversation.id)) return;
            if (retryWasVisible) {
              rememberActiveConversationId(conversation.id);
              activeConversationIdRef.current = conversation.id;
              setConversationId(conversation.id);
            }
            await streamToConversation(conversation.id);
            return;
          } catch (retryErr) {
            err = retryErr;
          }
        }
        clearNeutralGuestSubmission();
        const isOrdinaryTransportAmbiguity =
          action?.type !== "run_backtest" &&
          (!(err instanceof ChatStreamError) || err.status === 0);
        if (isOrdinaryTransportAmbiguity) {
          if (!requestSessions.authorize(requestSession, "ambiguity")) return;
          conversationActivity.progressRequest(
            requestSession.identity.conversationId,
            requestSession.identity.requestId,
            "checking",
          );
          if (canApplyVisibleStreamUpdate()) {
            setStreamStatus(t("chat.status.checking"));
          }
          const view = await resolveOrdinaryTransportAmbiguityView(
            async () =>
              loadAllConversationMessagePages(requestSession.identity.conversationId),
            hydrateMessagesFromApi,
            {
              assistantId,
              message: conversationLoadFailureMessage(
                requestSession.identity.conversationId,
                t("chat.error_load"),
              ),
            },
            ordinaryTransportMessageIds,
            err instanceof ChatStreamError ? err.requestId : null,
            { signal: requestSession.controller.signal },
          );
          if (requestSessions.authorize(requestSession, "ambiguity")) {
            if (canApplyVisibleStreamUpdate()) {
              setMessages((current) => settleRetestReceiptProjection(view.messages, current, userMsg.id));
            }
            terminalReadiness.finish(true);
            finishRequestTransport(requestSession);
          }
          return;
        }
        const confirmationId = ambiguousRunConfirmationId(action, err);
        if (confirmationId) {
          if (!requestSessions.authorize(requestSession, "run_replay")) return;
          conversationActivity.progressRequest(
            requestSession.identity.conversationId,
            requestSession.identity.requestId,
            "checking",
          );
          if (canApplyVisibleStreamUpdate()) {
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
              streamToConversation(requestSession.identity.conversationId),
          });
          if (!requestSessions.authorize(requestSession, "run_replay")) return;
          if (reconciliation.kind === "replayed") return;
          if (reconciliation.kind === "durable") {
            if (canApplyVisibleStreamUpdate()) {
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
            }
            terminalReadiness.finish(true);
            finishRequestTransport(requestSession);
            return;
          }
          if (reconciliation.kind === "recoverable") {
            if (canApplyVisibleStreamUpdate()) {
              setMessages((prev) =>
                applyRecoverableRunReconciliation(
                  prev,
                  assistantId,
                  requestSession.identity.conversationId,
                  reconciliation.error,
                ),
              );
            }
            terminalReadiness.finish(true);
            finishRequestTransport(requestSession);
            return;
          }
        }
        const canApplyVisibleUpdate = canApplyVisibleStreamUpdate();
        const status = (err as { status?: number }).status;
        const isRateLimit = status === 429;
        const rejectionCode = err instanceof ChatStreamError ? err.code : null;
        const staleConfirmationRejected =
          isStaleConfirmationActionRejectionCode(rejectionCode);
        const fallbackMessage =
          err instanceof ChatStreamError && err.message
            ? err.message
            : t("chat.error_backtest");
        const httpErrorDisplay = chatHttpErrorDisplay(rejectionCode, fallbackMessage);
        if (canApplyVisibleUpdate) {
          setMessages((prev) =>
            normalizeDurableRetryActionHistory(
              settleConfirmationAfterActionTransportError(
                applyRetestReceipt(prev, userMsg.id, null).map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: staleConfirmationRejected
                          ? ""
                          : isRateLimit ? t("chat.rate_limit_error") : httpErrorDisplay.content,
                        recoveryDisplay: staleConfirmationRejected
                          ? {
                              kind: "recovery_code" as const,
                              code: rejectionCode,
                            }
                          : isRateLimit
                            ? m.recoveryDisplay
                            : (httpErrorDisplay.recoveryDisplay ?? m.recoveryDisplay),
                      }
                    : m,
                ),
                action,
                { rejectionCode },
              ),
            ),
          );
        }
        terminalReadiness.finish(requestSessions.authorize(requestSession, "catch"));
        finishRequestTransport(requestSession);
      }
    })();
    return true;
    } finally {
      sendAdmissionInFlightRef.current = false;
      if (isDeferredGuestSubmission && !guestSubmissionHandedToStream) {
        setGuestSubmissionPending(false);
        setStreamStatus(null);
      }
    }
  };

  const retryGuestSubmission = () => {
    const pending = guestSubmissionRetryRef.current;
    if (!pending) return;
    void handleSend(
      pending.text,
      pending.mentionsOrAction,
      pending.actionArg,
      pending.options,
    );
  };

  useGuestSendBridge(guestSendRef, handleSend);
  // ── Action routing ─────────────────────────────────────────────────────────

  const handleLogout = async () => {
    try {
      const result = await logoutFromApi();
      if (result.revocation === "failed") {
        showToast(
          t(
            "settings.logout_error",
            "We couldn’t sign out this browser. Try again.",
          ),
          "error",
        );
        return;
      }
      requestSessions.synchronizeAccountScope(null);
      setAccount(null);
      transcriptSessionCache.clearAuthenticatedState();
      resetToEmptyChatSurface();
      clearHistory();
      window.location.href = "/";
    } catch {
      showToast(
        t(
          "settings.logout_error",
          "We couldn’t sign out this browser. Try again.",
        ),
        "error",
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
    if (!targetConversationId) return;
    invalidateTranscriptForMutation(targetConversationId, "message_send");
    if (targetConversationId !== conversationId) {
      rememberActiveConversationId(targetConversationId);
      synchronizeConversationViewRefs(activeConversationIdRef, currentViewRef, targetConversationId, "chat");
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
    const request = requestSessions.begin(targetConversationId, "chat_turn");
    if (!request) return;
    const terminalReadiness = beginConversationActivityTerminalReadiness(() => request);

    setStreamStatus(null);
    try {
      await streamChatMessage(
        targetConversationId,
        streamInput,
        i18n.language,
        (event) => {
          if (event.event === "stage_start") {
            if (!requestSessions.authorize(request, "stage")) return;
            conversationActivity.progressRequest(request.identity.conversationId, request.identity.requestId, "running");
          }
          if (event.event === "final") {
            const identityAuthorized = requestSessions.authorize(request, "cancel");
            if (!identityAuthorized) return;
            setMessages((prev) =>
              applyConfirmationActionEffects(
                markComposerActionsInactive(prev),
                [effect],
              ),
            );
            terminalReadiness.accept(event.data, identityAuthorized);
          }
          if (event.event === "error") {
            if (!requestSessions.authorize(request, "error")) return;
            if (requestSessions.canWriteVisible(request)) {
              showToast(
                chatStreamErrorText(event.data.detail, t("chat.error_generic")),
                "error",
              );
            }
            terminalReadiness.finish(true);
            finishRequestTransport(request);
          }
          if (event.event === "done") {
            if (!requestSessions.authorize(request, "done")) return;
            terminalReadiness.finish(true);
            finishRequestTransport(request);
          }
        },
        [],
        {
          requestId: request.identity.requestId,
          signal: request.controller.signal,
        },
      );
    } catch (err: unknown) {
      if (!requestSessions.authorize(request, "catch")) return;
      const message =
        err instanceof ChatStreamError && err.message
          ? err.message
          : t("chat.error_generic");
      if (requestSessions.canWriteVisible(request)) showToast(message, "error");
      terminalReadiness.finish(true);
      finishRequestTransport(request);
    }
  };

  const handleAction = (action: ChatActionOption) => {
    const value = action.value ?? "";
    if (action.type === "cancel_confirmation") {
      void handleCancelConfirmationAction(action);
      return;
    }
    if (action.type === "add_confirmation_peer") {
      // No turn is spent: the typed endpoint patches the pending card
      // deterministically and returns the superseding card message.
      void handleAddConfirmationPeer(action);
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
          failedAssistantId
            ? {
                renderUserMessage: false,
                replacementAssistantId: failedAssistantId,
              }
            : requestMessageId
              ? { renderUserMessage: true }
              : { renderUserMessage: false },
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

  const {
    handleAddConfirmationPeer,
    handleDirectEditConfirmation,
  } = confirmationSupersedingHandlers(() => ({
    activeConversationId: () => activeConversationIdRef.current,
    // Through the ref: the undo toast outlives its render.
    activeConfirmationId: () => activeConfirmationIdFrom(latestMessagesRef.current),
    hydrate: (created) => hydrateMessagesFromApi(created),
    setMessages,
    showToast,
    hideToast,
    t,
  }));

  const omnisearch = omnisearchActionHandlers(() => ({
    closeOverlay: () => setSearchOverlayOpen(false),
    loadConversation,
    send: handleSend,
    isSourceConversationReady: (id) =>
      activeConversationIdRef.current === id &&
      readyTranscriptConversationIdRef.current === id,
  }));

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
      invalidateTranscriptForMutation(conversationId, "conversation_rename");
      refreshHistory();
      showToast(t("common.save"));
      closeChatOptions();
    } catch {
      showToast(t("chat.rename_failed"), "error");
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
      showToast(t("common.error_occurred"), "error");
    } finally {
      setIsPinningHeaderChat(false);
    }
  };

  const handleRequestHeaderDelete = (fromKeyboardShortcut = false) => {
    if (!conversationId) return;
    setPendingHeaderDelete({ conversationId, showKeyboardHints: fromKeyboardShortcut });
    closeChatOptions();
  };
  const handleConfirmHeaderDelete = async () => {
    if (!pendingHeaderDelete || isDeletingHeaderChat) return;
    setIsDeletingHeaderChat(true);
    try {
      await deleteConversation(pendingHeaderDelete.conversationId);
      showToast(t("common.delete"));
      handleConversationRemoved(pendingHeaderDelete.conversationId);
    } catch {
      showToast(t("common.error_occurred"), "error");
    } finally {
      setIsDeletingHeaderChat(false);
      setPendingHeaderDelete(null);
    }
  };
  // One in-flight lock for every way to start a turn. The composer already
  // disables itself while a turn runs; persistent discovery rows have to obey
  // the same lock or they become a way to spam turns around it.
  const turnInFlight =
    Boolean(visibleStreamStatus) ||
    isStreamingResponse ||
    isHydratingConversation ||
    guestSubmissionPending;
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
    visibleStreamStatus && latestAssistantContent.length === 0,
  );
  const showConversationDisclaimer = shouldShowConversationDisclaimer(
    messages,
    isStreamingResponse,
  );
  // Spec 10b: both empty-state placeholders carry the same invitation once the
  // rail ships; the pre-rail strings stay behind the flag so flag-off behavior
  // is unchanged. The follow-up placeholder is deliberately untouched.
  const chatInputPlaceholder =
    messages.length === 0
      ? t(
          isGuest
            ? researchRailEnabled
              ? "guest.shell.input_placeholder"
              : "guest.shell.input_placeholder_prerail"
            : researchRailEnabled
              ? "chat.input_placeholder"
              : "chat.input_placeholder_prerail",
        )
      : t("chat.followup_placeholder", "Ask a follow-up...");
  const hasConversationLoadFailure =
    failedConversationId !== null && failedConversationId === conversationId;
  const showEmptyChatSurface = shouldShowEmptyChatSurface({
    messages,
    isHydratingConversation,
    hasConversationLoadFailure,
  });
  const conversationComposerUnavailable =
    isStreamingResponse ||
    isHydratingConversation ||
    guestSubmissionPending ||
    hasConversationLoadFailure;

  const keyboardShortcuts = useChatKeyboardShortcuts({
    enabled: !mobileShell.isBelowTablet,
    isChatView: currentView === "chat",
    canManageConversation,
    conversationId,
    isGuest,
    searchOverlayOpen,
    deleteConfirmationOpen: Boolean(pendingHeaderDelete),
    // The drawer is a modal too. Left out, its shortcuts still fired, and
    // Recents Quick Peek opened at z-65 behind a z-68 drawer: a real modal
    // nobody could see, reachable only by keyboard or switch control.
    modalOpen:
      isSidebarPreferenceModalOpen ||
      feedbackState.isOpen ||
      showChatOptions ||
      mobileShell.isDrawerOpen,
    sidebarOpen: isSidebarOpen,
    setSidebarOpen: setIsSidebarOpen,
    recentsExpanded: isRecentsExpanded,
    setRecentsExpanded: setIsRecentsExpanded,
    requestNewChat,
    closeTransientSidebar,
    requestDelete: () => handleRequestHeaderDelete(true),
    startRename: handleStartHeaderRename,
    archiveConversation: archiveActiveConversation,
    toggleRead: () => toggleConversationUnread(conversationActivity, conversationId),
    togglePin: handleToggleHeaderPin,
    showChatOptions: () => setShowChatOptions(true),
  });
  // ── Render ─────────────────────────────────────────────────────────────────

  if (profileState === "probing" || profileState === "unavailable") {
    return (
      <div className="flex h-[100dvh] w-full items-center justify-center bg-background">
        <div
          aria-label={t("guest.entry.loading", "Opening Argus")}
          className="h-8 w-8 animate-spin rounded-full border-2 border-primary border-t-transparent"
          role="status"
        />
      </div>
    );
  }

  if (profileState === "expired") {
    return (
      <ExpiredGuestSession
        publicAccountAccessEnabled={expiredPublicAccountAccessEnabled}
      />
    );
  }

  return (
    <ConversationActivityPresentationProvider
      selectPresentation={conversationActivity.selectPresentation}
      selectAggregatePresentation={conversationActivity.selectAggregatePresentation} selectOperationLabel={conversationActivity.selectOperationLabel}
    >
      <div className="relative flex h-[100dvh] w-full overflow-hidden bg-[#f9f9f9] text-black dark:bg-[#141517] dark:text-white tablet:flex-row">
      {/* ── Sidebar: rail on desktop, off-canvas drawer below the mobile threshold ── */}
      <SidebarShell
        isBelowTablet={mobileShell.isBelowTablet}
        isDrawerOpen={mobileShell.isDrawerOpen}
        onCloseDrawer={mobileShell.closeDrawer}
        label={t("common.navigation", "Navigation")}
      >
      <ChatSidebar
        variant={mobileShell.isBelowTablet ? "drawer" : "rail"}
        onRequestClose={mobileShell.closeDrawer}
        guestSettings={
          mobileShell.isBelowTablet && isGuest ? (
            <GuestSettingsMenu
              feedbackEnabled={canSubmitFeedback}
              onFeedback={requestGuestFeedback}
              placement="drawer"
            />
          ) : null
        }
        isOpen={mobileShell.isBelowTablet ? true : isSidebarOpen}
        onToggle={toggleSidebar}
        currentView={currentView}
        conversationId={conversationId}
        conversationActivity={conversationActivity}
        isRecentsExpanded={isRecentsExpanded}
        onToggleRecents={() => setIsRecentsExpanded((expanded) => !expanded)}
        historyItems={historyItems}
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
          closeDrawer();
          if (omnisearchEnabled) {
            requestOmnisearch();
          }
        }}
        onHistoryMutated={refreshHistory}
        onProfileUpdated={onProfileUpdated}
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
        onOpenKeyboardShortcuts={() =>
          keyboardShortcuts.setKeyboardShortcutsOpen(true)
        }
        settingsOpenRequest={keyboardShortcuts.settingsOpenRequest}
        mode={sidebarMode}
        omnisearchEnabled={
          omnisearchEnabled && (!isGuest || canUseOmnisearch)
        }
        shortcutHintsSuppressed={searchOverlayOpen}
        canManageConversation={canManageConversation}
        showProfileMenu={!isGuest}
        isGuest={guestExperience.isEstablishedGuest}
        guestExpiresAt={account?.guest?.expires_at}
      />
      </SidebarShell>

      <KeyboardShortcutSurfaces
        keyboardShortcutsOpen={keyboardShortcuts.keyboardShortcutsOpen}
        onCloseKeyboardShortcuts={() =>
          keyboardShortcuts.setKeyboardShortcutsOpen(false)
        }
        recentsQuickPeekOpen={keyboardShortcuts.isRecentsQuickPeekOpen}
        historyItems={historyItems}
        activeConversationId={conversationId}
        onOpenHistoryItem={openHistoryItem}
        onCloseRecentsQuickPeek={() =>
          keyboardShortcuts.setIsRecentsQuickPeekOpen(false)
        }
      />

      {omnisearchEnabled &&
        (!isGuest || canUseOmnisearch) &&
        searchOverlayOpen && (
          <ChatCommandPalette
            onClose={() => setSearchOverlayOpen(false)}
            onOpenConversation={(convId, messageId, openAtLeftOff) => {
              setSearchOverlayOpen(false);
              void loadConversation(convId, messageId, openAtLeftOff);
            }}
            onRetest={omnisearch.retest}
            turnInFlight={turnInFlight}
            activeConversationId={conversationId}
            isGuest={isGuest}
            groundedDiscoveryAvailable={canUseGroundedDiscovery}
            canManageConversation={canManageConversation}
            onDecisionUnavailable={requestGuestDecision}
            decisionResumeTarget={resumeDecisionTarget}
            onDecisionResumeHandled={clearResumeDecision}
            onMutated={refreshHistory}
            onConversationRemoved={handleConversationRemoved}
          />
        )}

      <ConfirmDialog
        isOpen={Boolean(pendingHeaderDelete)}
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
        showKeyboardHints={pendingHeaderDelete?.showKeyboardHints}
        onCancel={() => {
          if (!isDeletingHeaderChat) setPendingHeaderDelete(null);
        }}
        onConfirm={() => void handleConfirmHeaderDelete()}
      />

      <section className="relative z-10 flex h-full flex-1 flex-col overflow-hidden bg-[#f9f9f9] dark:bg-[#141517]">
        {/* ── Unified View Header (SOTA: Absolute to content panel for perfect centering) ── */}
        {currentView !== "settings" && (
          <header className="absolute inset-x-0 top-0 z-[50] flex h-20 items-center justify-between gap-2 px-4 pointer-events-none tablet:gap-4 tablet:px-8">
            {mobileShell.isBelowTablet && (
              <div className="pointer-events-auto shrink-0">
                <ChatShellMenuTrigger
                  onOpen={mobileShell.openDrawer}
                  activityPresentation={
                    mobileShell.isDrawerOpen
                      ? null
                      : conversationActivity.selectAggregatePresentation(
                          historyItems.map((item) => item.conversation_id ?? item.id),
                        )
                  }
                />
              </div>
            )}
            {/* Title (left-aligned; truncates before the action cluster) */}
            <h1 className="font-display pointer-events-auto min-w-0 flex-1 truncate text-left text-[17px] font-semibold tracking-tight text-black/80 dark:text-white/80 tablet:text-[18px]">
              {currentView === "chat" &&
                (conversationId !== null || messages.length > 0) &&
                !showEmptyChatSurface && (
                  <ChatHeaderTitle
                    conversationId={conversationId}
                    title={headerConversationTitle}
                    titleSource={headerConversationTitleSource}
                  />
                )}
            </h1>

            {/* Action cluster (guest settings or durable owner menu) */}
            <div className="flex shrink-0 justify-end pointer-events-auto">
              {currentView === "chat" && isGuest ? (
                <GuestHeader
                  expiresAt={account?.guest?.expires_at ?? null}
                  feedbackEnabled={canSubmitFeedback}
                  onFeedback={requestGuestFeedback}
                  onSignIn={requestGuestSignIn}
                  showSettings={!mobileShell.isBelowTablet}
                />
              ) : currentView === "chat" &&
                conversationId &&
                canManageConversation ? (
                <ChatHeaderMenu
                  isOpen={showChatOptions}
                  onToggleOpen={() => setShowChatOptions(!showChatOptions)}
                  onRequestClose={closeChatOptions}
                  isUnread={conversationActivity.hasEffectiveUnread(conversationId)}
                  isReadMutationPending={conversationActivity.hasEffectiveUnread(conversationId) ? conversationActivity.isMutationPending(conversationId, "mark_read") : conversationActivity.isMutationPending(conversationId, "mark_unread")}
                  onToggleUnread={() => void toggleConversationUnread(conversationActivity, conversationId)}
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
                  onRequestDelete={() => handleRequestHeaderDelete()}
                  memoryChrome={memoryChrome}
                />
              ) : null}
            </div>
          </header>
        )}
        {currentView === "chat" && (
          <div className="relative mx-auto flex h-[100dvh] w-full max-w-5xl flex-col">
            <ConversationActivityAnnouncement activity={conversationActivity} conversationId={conversationId} title={activeTitleRecord ? headerConversationTitle : null} enabled={!isHydratingConversation} />
            {showEmptyChatSurface ? (
              <EmptyChatSurface
                isGuest={isGuest}
                expiresAt={account?.guest?.expires_at}
                guestSubmissionPending={guestSubmissionPending}
                guestSubmissionError={guestSubmissionError}
                isStreamingResponse={isStreamingResponse}
                isHydratingConversation={isHydratingConversation}
                preferredName={greetingName}
                placeholder={chatInputPlaceholder}
                onSend={handleSend}
                onRetryGuestSubmission={retryGuestSubmission}
                onToast={showToast}
              />
            ) : (
              <>
                <div className="pointer-events-none absolute inset-x-0 top-0 z-10 h-32 bg-[#f9f9f9]/80 backdrop-blur-[0.8px] [mask-image:linear-gradient(to_bottom,black_48%,transparent_100%)] dark:bg-[#141517]/80" />

                {showConversationRetrievalState && isHydratingConversation && (
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
                  aria-busy={isHydratingConversation || guestSubmissionPending}
                  className="argus-scrollbar flex-1 overflow-y-auto px-4 pb-[190px] pt-[86px]"
                >
                  <div className="space-y-8">
                    {showConversationRetrievalState &&
                      isHydratingConversation && (
                        <ConversationRetrievalState state="loading" />
                      )}
                    {hasConversationLoadFailure && (
                      <ConversationRetrievalState
                        state="error"
                        onRetry={() => {
                          if (failedConversationId) void loadConversation(failedConversationId);
                        }}
                      />
                    )}
                    {messages.map((msg, index) => {
                      const { isLatestAi, isWorkingMessage } =
                        messageStreamPresentation(
                          messages,
                          msg,
                          index,
                          isStreamingResponse,
                          !!visibleStreamStatus,
                        );
                      return (
                        <div
                          key={msg.id}
                          ref={messageElementRegistrar(messageElementRefs, msg.id)}
                          data-message-id={msg.id}
                          tabIndex={-1}
                          className="scroll-m-24 outline-none"
                        >
                          <ChatMessage
                            message={msg}
                            onAction={handleAction}
                            onDirectEdit={handleDirectEditConfirmation}
                            onFeedback={(type, context, rating) => {
                              void handleMessageFeedback(type, context, rating);
                            }}
                            onToast={showToast}
                            isLatest={isLatestAi}
                            isStreaming={isWorkingMessage}
                            conversationId={conversationId}
                            memoryProposalEnabled={memoryChrome.proposalEnabled}
                            nextMovesEnabled={nextMovesEnabled}
                            turnInFlight={turnInFlight}
                            isGuest={isGuest}
                            canSaveDecision={canSaveDecision}
                            onDecisionUnavailable={(artifactId) =>
                              requestGuestDecision({ surface: "result_card", artifactId })
                            }
                            onDecisionSaved={(decisionState) => {
                              setMessages((prev) =>
                                messagesWithSavedDecisionState(
                                  prev,
                                  msg.id,
                                  decisionState,
                                ),
                              );
                              if (conversationId) invalidateTranscriptForMutation(conversationId, "durable_result_action");
                            }}
                            onRequestSearchUpgrade={requestGuestSearchUpgrade}
                            resumeDecisionArtifactId={
                              msg.id === resumeDecisionMessageId ? resumeDecisionArtifactId : null
                            }
                            onDecisionResumeHandled={clearResumeDecision}
                          />
                        </div>
                      );
                    })}
                    {showStreamStatus && (
                      <div className="ml-12">
                        <span className="animate-ethereal-shimmer text-[13px] text-black/45 dark:text-white/45">
                          {visibleStreamStatus}
                        </span>
                      </div>
                    )}
                    <div ref={latestActivitySentinelRef} data-testid="latest-activity-sentinel" className="h-px" aria-hidden="true" />
                    <div ref={bottomRef} className="h-28" aria-hidden="true" />
                  </div>
                </div>

                <ConversationActivityRail
                  messages={messages}
                  onSelectTick={anchorToTurn}
                />

                {/* Input fade + bar */}
                <div className="pointer-events-none absolute bottom-0 inset-x-0 z-10 h-40 bg-[#f9f9f9]/80 backdrop-blur-[0.8px] [mask-image:linear-gradient(to_top,black_50%,transparent_100%)] dark:bg-[#141517]/80" />
                <div className="pointer-events-none absolute bottom-6 inset-x-0 z-20 px-4">
                  <div className="pointer-events-auto mx-auto max-w-3xl rounded-full">
                    {showJumpToLatest && (
                      <div className="mb-3 flex justify-center">
                        <ConversationActivityJumpButton
                          presentation={conversationActivity.selectPresentation(conversationId)}
                          onJump={() => scrollToLatest("smooth")}
                        />
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

        <ChatToast
          message={toast?.message ?? null}
          variant={toast?.variant}
          action={toast?.action}
        />
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
    </ConversationActivityPresentationProvider>
  );
}
