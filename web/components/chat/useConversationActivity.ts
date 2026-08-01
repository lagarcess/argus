"use client";

import {
  useEffect,
  useState,
  useSyncExternalStore,
} from "react";

import {
  patchConversationActivity,
  type ConversationActivity,
  type ConversationActivityPatch,
  type ConversationOperationKind,
  type ConversationOperationStatus,
  type HistoryItem,
} from "@/lib/argus-api";
import {
  conversationActivityReducer,
  createConversationActivityState,
  selectAggregateConversationActivityPresentation,
  selectConversationActivityPresentation,
  selectConversationAnnouncement,
  selectConversationIsLocked,
  selectConversationRequestIsCurrent,
  selectManualUnreadGuard,
  type ConversationActivityAnnouncement,
  type ConversationActivityPresentation,
  type ConversationActivityState,
} from "@/lib/conversation-activity-state";

const ACTIVITY_POLL_CADENCE_MS = 2_000;

type ActiveOperationStatus = Exclude<ConversationOperationStatus, "idle">;
type ActiveOperationKind = Exclude<ConversationOperationKind, null>;
type MutationAction = ConversationActivityPatch["action"];
type StateListener = () => void;

export type ConversationActivityMutationNotice = Readonly<{
  conversationId: string;
  action: MutationAction;
  outcome: "success" | "error";
}>;

export type ConversationActivityPatchTransport = (
  conversationId: string,
  patch: ConversationActivityPatch,
) => Promise<ConversationActivity>;

export type ConversationActivityEffectsAdapter = Readonly<{
  schedulePoll: (callback: () => void, delayMs: number) => () => void;
  subscribeWindowFocus: (callback: () => void) => () => void;
  subscribeVisibilityChange: (callback: () => void) => () => void;
  isDocumentVisible: () => boolean;
}>;

type ConversationActivityInputs = Readonly<{
  historyItems: readonly HistoryItem[];
  activeConversationId: string | null;
  accountScopeKey: string | null;
}>;

type ConversationActivityCallbacks = Readonly<{
  refreshHistory: () => void;
  invalidateInactiveTranscript: (conversationId: string) => void;
  onMutationNotice: (notice: ConversationActivityMutationNotice) => void;
}>;

export type CreateConversationActivityRuntimeOptions =
  ConversationActivityInputs &
    ConversationActivityCallbacks &
    Readonly<{
      patchActivity: ConversationActivityPatchTransport;
      effects: ConversationActivityEffectsAdapter;
    }>;

export type ConversationActivityRuntime = Readonly<{
  start: () => void;
  dispose: () => void;
  subscribe: (listener: StateListener) => () => void;
  getState: () => ConversationActivityState;
  updateCallbacks: (callbacks: ConversationActivityCallbacks) => void;
  updateInputs: (inputs: ConversationActivityInputs) => void;
  selectPresentation: (
    conversationId: string | null | undefined,
  ) => ConversationActivityPresentation;
  selectAggregatePresentation: (
    conversationIds?: readonly string[],
  ) => ConversationActivityPresentation;
  isConversationLocked: (
    conversationId: string | null | undefined,
  ) => boolean;
  hasManualUnreadGuard: (
    conversationId: string | null | undefined,
  ) => boolean;
  startRequest: (
    conversationId: string,
    requestId: string,
    status: ActiveOperationStatus,
    kind: ActiveOperationKind,
  ) => void;
  progressRequest: (
    conversationId: string,
    requestId: string,
    status: ActiveOperationStatus,
  ) => void;
  settleRequest: (
    conversationId: string,
    requestId: string,
    options?: Readonly<{ invalidateInactiveTranscript?: boolean }>,
  ) => void;
  isRequestCurrent: (conversationId: string, requestId: string) => boolean;
  markRead: (
    conversationId: string,
    throughCursor: string | null,
  ) => Promise<void>;
  markUnread: (conversationId: string) => Promise<void>;
  isMutationPending: (
    conversationId: string,
    action?: MutationAction,
  ) => boolean;
  registerTransport: (
    conversationId: string,
    requestId: string,
    controller: AbortController,
  ) => void;
  releaseTransport: (
    conversationId: string,
    requestId: string,
    controller?: AbortController,
  ) => void;
  resetViewEpoch: (conversationId: string) => void;
  getAnnouncement: (
    conversationId: string | null | undefined,
  ) => ConversationActivityAnnouncement | null;
  acknowledgeAnnouncement: (conversationId: string, key: string) => void;
}>;

const isUnresolvedOperation = (
  activity: ConversationActivity | null,
): boolean => {
  const status: unknown = activity?.operation.status;
  return status != null && status !== "idle";
};

const transportKey = (conversationId: string, requestId: string): string =>
  JSON.stringify([conversationId, requestId]);

const createBrowserEffectsAdapter = (): ConversationActivityEffectsAdapter => ({
  schedulePoll: (callback, delayMs) => {
    if (typeof window === "undefined") return () => undefined;
    const intervalId = window.setInterval(callback, delayMs);
    return () => window.clearInterval(intervalId);
  },
  subscribeWindowFocus: (callback) => {
    if (typeof window === "undefined") return () => undefined;
    window.addEventListener("focus", callback);
    return () => window.removeEventListener("focus", callback);
  },
  subscribeVisibilityChange: (callback) => {
    if (typeof document === "undefined") return () => undefined;
    document.addEventListener("visibilitychange", callback);
    return () => document.removeEventListener("visibilitychange", callback);
  },
  isDocumentVisible: () =>
    typeof document === "undefined" || document.visibilityState === "visible",
});

class ConversationActivityRuntimeOwner implements ConversationActivityRuntime {
  private state = createConversationActivityState();
  private readonly listeners = new Set<StateListener>();
  private readonly mutationSequences = new Map<string, number>();
  private readonly transports = new Map<string, AbortController>();
  private readonly loadedConversationIds = new Set<string>();
  private activeConversationId: string | null;
  private accountScopeKey: string | null;
  private responseRevision = 0;
  private accountEpoch = 0;
  private started = false;
  private cancelPoll: (() => void) | null = null;
  private unsubscribeFocus: (() => void) | null = null;
  private unsubscribeVisibility: (() => void) | null = null;
  private callbacks: ConversationActivityCallbacks;

  constructor(private readonly options: CreateConversationActivityRuntimeOptions) {
    this.activeConversationId = options.activeConversationId;
    this.accountScopeKey = options.accountScopeKey;
    this.callbacks = {
      refreshHistory: options.refreshHistory,
      invalidateInactiveTranscript: options.invalidateInactiveTranscript,
      onMutationNotice: options.onMutationNotice,
    };
    if (this.accountScopeKey) {
      this.mergeHistory(options.historyItems);
    }
  }

  start = (): void => {
    if (this.started) return;
    this.started = true;
    this.unsubscribeFocus = this.options.effects.subscribeWindowFocus(() => {
      this.refreshCanonicalHistory();
    });
    this.unsubscribeVisibility =
      this.options.effects.subscribeVisibilityChange(() => {
        if (this.options.effects.isDocumentVisible()) {
          this.refreshCanonicalHistory();
        }
      });
    this.refreshCanonicalHistory();
    this.reconcilePolling();
  };

  dispose = (): void => {
    if (!this.started) return;
    this.started = false;
    this.cancelPolling();
    this.unsubscribeFocus?.();
    this.unsubscribeVisibility?.();
    this.unsubscribeFocus = null;
    this.unsubscribeVisibility = null;
    this.abortRegisteredTransports();
    this.accountEpoch += 1;
  };

  subscribe = (listener: StateListener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  getState = (): ConversationActivityState => this.state;

  updateCallbacks = (callbacks: ConversationActivityCallbacks): void => {
    this.callbacks = callbacks;
  };

  updateInputs = (inputs: ConversationActivityInputs): void => {
    const accountChanged = inputs.accountScopeKey !== this.accountScopeKey;
    const navigationChanged =
      inputs.activeConversationId !== this.activeConversationId;
    if (accountChanged) {
      this.resetAccount(inputs.accountScopeKey);
    }
    this.activeConversationId = inputs.activeConversationId;
    if (inputs.accountScopeKey) {
      this.mergeHistory(inputs.historyItems);
    } else {
      this.loadedConversationIds.clear();
    }
    this.reconcilePolling();
    if (
      this.started &&
      inputs.accountScopeKey &&
      (accountChanged || navigationChanged)
    ) {
      this.refreshCanonicalHistory();
    }
  };

  selectPresentation = (
    conversationId: string | null | undefined,
  ): ConversationActivityPresentation =>
    selectConversationActivityPresentation(this.state, conversationId);

  selectAggregatePresentation = (
    conversationIds?: readonly string[],
  ): ConversationActivityPresentation =>
    selectAggregateConversationActivityPresentation(
      this.state,
      conversationIds ?? Array.from(this.loadedConversationIds),
    );

  isConversationLocked = (
    conversationId: string | null | undefined,
  ): boolean => selectConversationIsLocked(this.state, conversationId);

  hasManualUnreadGuard = (
    conversationId: string | null | undefined,
  ): boolean => selectManualUnreadGuard(this.state, conversationId);

  startRequest = (
    conversationId: string,
    requestId: string,
    status: ActiveOperationStatus,
    kind: ActiveOperationKind,
  ): void => {
    this.dispatch({
      type: "request_started",
      conversationId,
      requestId,
      status,
      kind,
    });
    this.refreshCanonicalHistory();
  };

  progressRequest = (
    conversationId: string,
    requestId: string,
    status: ActiveOperationStatus,
  ): void => {
    this.dispatch({
      type: "request_progressed",
      conversationId,
      requestId,
      status,
    });
  };

  settleRequest = (
    conversationId: string,
    requestId: string,
    options: Readonly<{ invalidateInactiveTranscript?: boolean }> = {},
  ): void => {
    if (!this.isRequestCurrent(conversationId, requestId)) return;
    this.dispatch({ type: "request_settled", conversationId, requestId });
    if (
      options.invalidateInactiveTranscript === true &&
      conversationId !== this.activeConversationId
    ) {
      this.callbacks.invalidateInactiveTranscript(conversationId);
    }
    this.refreshCanonicalHistory();
  };

  isRequestCurrent = (conversationId: string, requestId: string): boolean =>
    selectConversationRequestIsCurrent(this.state, conversationId, requestId);

  markRead = (
    conversationId: string,
    throughCursor: string | null,
  ): Promise<void> =>
    this.mutateActivity(conversationId, {
      action: "mark_read",
      through_attention_cursor: throughCursor,
    });

  markUnread = (conversationId: string): Promise<void> =>
    this.mutateActivity(conversationId, { action: "mark_unread" });

  isMutationPending = (
    conversationId: string,
    action?: MutationAction,
  ): boolean => {
    const mutation = this.state.byConversationId[conversationId]?.mutation;
    return Boolean(mutation && (action === undefined || mutation.action === action));
  };

  registerTransport = (
    conversationId: string,
    requestId: string,
    controller: AbortController,
  ): void => {
    const key = transportKey(conversationId, requestId);
    const existing = this.transports.get(key);
    if (existing && existing !== controller) existing.abort();
    this.transports.set(key, controller);
  };

  releaseTransport = (
    conversationId: string,
    requestId: string,
    controller?: AbortController,
  ): void => {
    const key = transportKey(conversationId, requestId);
    const existing = this.transports.get(key);
    if (!existing || (controller && existing !== controller)) return;
    this.transports.delete(key);
  };

  resetViewEpoch = (conversationId: string): void => {
    this.dispatch({ type: "view_epoch_reset", conversationId });
  };

  getAnnouncement = (
    conversationId: string | null | undefined,
  ): ConversationActivityAnnouncement | null =>
    selectConversationAnnouncement(this.state, conversationId);

  acknowledgeAnnouncement = (conversationId: string, key: string): void => {
    this.dispatch({ type: "announcement_acknowledged", conversationId, key });
  };

  private dispatch(
    action: Parameters<typeof conversationActivityReducer>[1],
  ): void {
    const nextState = conversationActivityReducer(this.state, action);
    if (nextState === this.state) return;
    this.state = nextState;
    this.synchronizeResponseRevision();
    this.reconcilePolling();
    for (const listener of this.listeners) listener();
  }

  private mergeHistory(historyItems: readonly HistoryItem[]): void {
    this.loadedConversationIds.clear();
    for (const item of historyItems) {
      if (item.type !== "chat") continue;
      const conversationId = item.conversation_id ?? item.id;
      this.loadedConversationIds.add(conversationId);
      if (!item.activity) continue;

      const priorActivity =
        this.state.byConversationId[conversationId]?.canonical ?? null;
      const settled =
        isUnresolvedOperation(priorActivity) &&
        !isUnresolvedOperation(item.activity);
      this.dispatch({
        type: "server_projection_merged",
        conversationId,
        activity: item.activity,
        revision: this.nextResponseRevision(),
        activeView: conversationId === this.activeConversationId,
      });
      if (settled && conversationId !== this.activeConversationId) {
        this.callbacks.invalidateInactiveTranscript(conversationId);
      }
    }
  }

  private mutateActivity(
    conversationId: string,
    patch: ConversationActivityPatch,
  ): Promise<void> {
    const action = patch.action;
    const sequenceKey = JSON.stringify([conversationId, action]);
    const sequence = (this.mutationSequences.get(sequenceKey) ?? 0) + 1;
    this.mutationSequences.set(sequenceKey, sequence);
    const mutationId = `${this.accountEpoch}:${sequenceKey}:${sequence}`;
    const epoch = this.accountEpoch;
    this.dispatch({
      type: "mutation_started",
      conversationId,
      mutationId,
      action,
      revision: this.nextResponseRevision(),
      activeView: conversationId === this.activeConversationId,
    });

    let request: Promise<ConversationActivity>;
    try {
      request = this.options.patchActivity(conversationId, patch);
    } catch (error) {
      request = Promise.reject(error);
    }

    return request.then(
      (activity) => {
        if (!this.mutationIsCurrent(conversationId, mutationId, epoch)) return;
        this.dispatch({
          type: "mutation_succeeded",
          conversationId,
          mutationId,
          activity,
        });
        this.callbacks.onMutationNotice({
          conversationId,
          action,
          outcome: "success",
        });
        this.refreshCanonicalHistory();
      },
      () => {
        if (!this.mutationIsCurrent(conversationId, mutationId, epoch)) return;
        this.dispatch({ type: "mutation_failed", conversationId, mutationId });
        this.callbacks.onMutationNotice({
          conversationId,
          action,
          outcome: "error",
        });
      },
    );
  }

  private mutationIsCurrent(
    conversationId: string,
    mutationId: string,
    epoch: number,
  ): boolean {
    return (
      epoch === this.accountEpoch &&
      this.state.byConversationId[conversationId]?.mutation?.mutationId ===
        mutationId
    );
  }

  private nextResponseRevision(): number {
    this.responseRevision += 1;
    return this.responseRevision;
  }

  private synchronizeResponseRevision(): void {
    for (const record of Object.values(this.state.byConversationId)) {
      this.responseRevision = Math.max(
        this.responseRevision,
        record.serverRevision,
      );
    }
  }

  private hasUnresolvedWork(): boolean {
    for (const record of Object.values(this.state.byConversationId)) {
      if (record.request) return true;
    }
    for (const conversationId of this.loadedConversationIds) {
      const canonical =
        this.state.byConversationId[conversationId]?.canonical ?? null;
      if (isUnresolvedOperation(canonical)) return true;
    }
    return false;
  }

  private reconcilePolling(): void {
    const shouldPoll =
      this.started && Boolean(this.accountScopeKey) && this.hasUnresolvedWork();
    if (!shouldPoll) {
      this.cancelPolling();
      return;
    }
    if (this.cancelPoll) return;
    this.cancelPoll = this.options.effects.schedulePoll(
      () => this.refreshCanonicalHistory(),
      ACTIVITY_POLL_CADENCE_MS,
    );
  }

  private cancelPolling(): void {
    this.cancelPoll?.();
    this.cancelPoll = null;
  }

  private refreshCanonicalHistory(): void {
    if (!this.accountScopeKey) return;
    try {
      this.callbacks.refreshHistory();
    } catch {
      // A cold refresh failure carries no activity truth. The existing surface
      // remains neutral until a canonical projection arrives.
    }
  }

  private resetAccount(nextAccountScopeKey: string | null): void {
    this.abortRegisteredTransports();
    this.accountEpoch += 1;
    this.accountScopeKey = nextAccountScopeKey;
    this.responseRevision = 0;
    this.mutationSequences.clear();
    this.loadedConversationIds.clear();
    this.dispatch({ type: "account_reset" });
  }

  private abortRegisteredTransports(): void {
    for (const controller of this.transports.values()) controller.abort();
    this.transports.clear();
  }
}

export const createConversationActivityRuntime = (
  options: CreateConversationActivityRuntimeOptions,
): ConversationActivityRuntime => new ConversationActivityRuntimeOwner(options);

export type UseConversationActivityOptions = ConversationActivityInputs &
  ConversationActivityCallbacks &
  Readonly<{
    testAdapters?: Readonly<{
      patchActivity?: ConversationActivityPatchTransport;
      effects?: ConversationActivityEffectsAdapter;
    }>;
  }>;

export type UseConversationActivityResult = Readonly<{
  state: ConversationActivityState;
}> &
  Omit<
    ConversationActivityRuntime,
    | "start"
    | "dispose"
    | "subscribe"
    | "getState"
    | "updateCallbacks"
    | "updateInputs"
  >;

export function useConversationActivity(
  options: UseConversationActivityOptions,
): UseConversationActivityResult {
  const [runtime] = useState<ConversationActivityRuntime>(() =>
    createConversationActivityRuntime({
      historyItems: options.historyItems,
      activeConversationId: options.activeConversationId,
      accountScopeKey: options.accountScopeKey,
      refreshHistory: options.refreshHistory,
      invalidateInactiveTranscript: options.invalidateInactiveTranscript,
      onMutationNotice: options.onMutationNotice,
      patchActivity:
        options.testAdapters?.patchActivity ?? patchConversationActivity,
      effects:
        options.testAdapters?.effects ?? createBrowserEffectsAdapter(),
    }),
  );
  const state = useSyncExternalStore(
    runtime.subscribe,
    runtime.getState,
    runtime.getState,
  );

  useEffect(() => {
    runtime.updateCallbacks({
      refreshHistory: options.refreshHistory,
      invalidateInactiveTranscript: options.invalidateInactiveTranscript,
      onMutationNotice: options.onMutationNotice,
    });
  }, [
    runtime,
    options.refreshHistory,
    options.invalidateInactiveTranscript,
    options.onMutationNotice,
  ]);

  useEffect(() => {
    runtime.updateInputs({
      historyItems: options.historyItems,
      activeConversationId: options.activeConversationId,
      accountScopeKey: options.accountScopeKey,
    });
  }, [
    runtime,
    options.historyItems,
    options.activeConversationId,
    options.accountScopeKey,
  ]);

  useEffect(() => {
    runtime.start();
    return () => runtime.dispose();
  }, [runtime]);

  return {
    state,
    selectPresentation: runtime.selectPresentation,
    selectAggregatePresentation: runtime.selectAggregatePresentation,
    isConversationLocked: runtime.isConversationLocked,
    hasManualUnreadGuard: runtime.hasManualUnreadGuard,
    startRequest: runtime.startRequest,
    progressRequest: runtime.progressRequest,
    settleRequest: runtime.settleRequest,
    isRequestCurrent: runtime.isRequestCurrent,
    markRead: runtime.markRead,
    markUnread: runtime.markUnread,
    isMutationPending: runtime.isMutationPending,
    registerTransport: runtime.registerTransport,
    releaseTransport: runtime.releaseTransport,
    resetViewEpoch: runtime.resetViewEpoch,
    getAnnouncement: runtime.getAnnouncement,
    acknowledgeAnnouncement: runtime.acknowledgeAnnouncement,
  };
}
