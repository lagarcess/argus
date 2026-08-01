"use client";

import {
  useEffect,
  useLayoutEffect,
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
  createConversationActivityCausalClock,
  conversationActivityReducer,
  createConversationActivityState,
  selectAggregateConversationActivityPresentation,
  selectConversationActivityPresentation,
  selectConversationAttentionCursor,
  selectConversationAnnouncement,
  selectConversationHasEffectiveUnread,
  selectConversationIsLocked,
  selectConversationMutationIsPending,
  selectConversationOperationLabel,
  selectConversationRequestIsCurrent,
  selectManualUnreadGuard,
  type ConversationActivityCausalClock,
  type ConversationActivityHistorySnapshot,
  type ConversationActivityAnnouncement,
  type ConversationActivityPresentation,
  type ConversationActivityOperationLabel,
  type ConversationActivityState,
} from "@/lib/conversation-activity-state";

const ACTIVITY_POLL_CADENCE_MS = 2_000;

type ActiveOperationStatus = Exclude<ConversationOperationStatus, "idle">;
type ActiveOperationKind = Exclude<ConversationOperationKind, null>;
type MutationAction = ConversationActivityPatch["action"];
type StateListener = () => void;

const isConversationActivityHistorySnapshot = (
  value: ConversationActivityHistorySnapshot | readonly HistoryItem[],
): value is ConversationActivityHistorySnapshot => !Array.isArray(value);

export type ConversationActivityMutationNotice = Readonly<{
  conversationId: string;
  action: MutationAction;
  outcome: "success" | "error";
}>;

export type ConversationActivityMutationNoticeDescriptor = Readonly<{
  key: string;
  defaultValue: string;
  variant: "neutral" | "error";
}>;

export const conversationActivityMutationNoticeDescriptor = (
  notice: ConversationActivityMutationNotice,
): ConversationActivityMutationNoticeDescriptor => {
  if (notice.outcome === "error") {
    return notice.action === "mark_read"
      ? {
          key: "chat.activity.mark_read_error",
          defaultValue: "Couldn’t mark this conversation as read. Try again.",
          variant: "error",
        }
      : {
          key: "chat.activity.mark_unread_error",
          defaultValue: "Couldn’t mark this conversation as unread. Try again.",
          variant: "error",
        };
  }
  return notice.action === "mark_read"
    ? {
        key: "chat.activity.mark_read_success",
        defaultValue: "Marked as read.",
        variant: "neutral",
      }
    : {
        key: "chat.activity.mark_unread_success",
        defaultValue: "Marked as unread.",
        variant: "neutral",
      };
};

export type ConversationActivityPatchTransport = (
  conversationId: string,
  patch: ConversationActivityPatch,
  options: Readonly<{ signal: AbortSignal }>,
) => Promise<ConversationActivity>;

export type ConversationActivityEffectsAdapter = Readonly<{
  schedulePoll: (callback: () => void, delayMs: number) => () => void;
  subscribeWindowFocus: (callback: () => void) => () => void;
  subscribeVisibilityChange: (callback: () => void) => () => void;
  isDocumentVisible: () => boolean;
}>;

type ConversationActivityInputs = Readonly<{
  historyItems: readonly HistoryItem[];
  historyActivityRevision?: number;
  activeConversationId: string | null;
  accountScopeKey: string | null;
}>;

type ConversationActivityCallbacks = Readonly<{
  refreshHistory: () =>
    | ConversationActivityHistorySnapshot
    | readonly HistoryItem[]
    | void
    | Promise<ConversationActivityHistorySnapshot | readonly HistoryItem[] | void>;
  invalidateInactiveTranscript: (conversationId: string) => void;
  onMutationNotice: (notice: ConversationActivityMutationNotice) => void;
}>;

export type CreateConversationActivityRuntimeOptions =
  ConversationActivityInputs &
    ConversationActivityCallbacks &
    Readonly<{
      patchActivity: ConversationActivityPatchTransport;
      effects: ConversationActivityEffectsAdapter;
      causalClock?: ConversationActivityCausalClock;
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
  selectOperationLabel: (
    conversationId: string | null | undefined,
  ) => ConversationActivityOperationLabel | null;
  hasEffectiveUnread: (
    conversationId: string | null | undefined,
  ) => boolean;
  selectAttentionCursor: (
    conversationId: string | null | undefined,
  ) => string | null;
  isConversationLocked: (
    conversationId: string | null | undefined,
  ) => boolean;
  hasManualUnreadGuard: (
    conversationId: string | null | undefined,
  ) => boolean;
  updateActiveConversationId: (conversationId: string | null) => void;
  startRequest: (
    conversationId: string,
    requestId: string,
    status: ActiveOperationStatus,
    kind: ActiveOperationKind,
  ) => number;
  progressRequest: (
    conversationId: string,
    requestId: string,
    status: ActiveOperationStatus,
  ) => void;
  finishTransport: (
    conversationId: string,
    requestId: string,
    controller?: AbortController,
  ) => boolean;
  retireRequest: (conversationId: string, requestId: string) => boolean;
  isRequestCurrent: (conversationId: string, requestId: string) => boolean;
  synchronizeAccountScope: (accountScopeKey: string | null) => boolean;
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

const activitiesAreEqual = (
  left: ConversationActivity | null,
  right: ConversationActivity,
): boolean =>
  left?.operation.status === right.operation.status &&
  left.operation.kind === right.operation.kind &&
  left.operation.updated_at === right.operation.updated_at &&
  left.attention.status === right.attention.status &&
  left.attention.cursor === right.attention.cursor;

const transportKey = (conversationId: string, requestId: string): string =>
  JSON.stringify([conversationId, requestId]);

const createBrowserEffectsAdapter = (): ConversationActivityEffectsAdapter => ({
  schedulePoll: (callback, delayMs) => {
    if (typeof window === "undefined") return () => undefined;
    const timeoutId = window.setTimeout(callback, delayMs);
    return () => window.clearTimeout(timeoutId);
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
  private readonly mutationTransports = new Map<
    string,
    Readonly<{ mutationId: string; controller: AbortController }>
  >();
  private readonly loadedConversationIds = new Set<string>();
  private activeConversationId: string | null;
  private lastInputActiveConversationId: string | null;
  private accountScopeKey: string | null;
  private responseRevision = 0;
  private accountEpoch = 0;
  private accountRefreshPending = false;
  private started = false;
  private cancelPoll: (() => void) | null = null;
  private refreshInFlight: Readonly<{
    epoch: number;
    promise: Promise<void>;
  }> | null = null;
  private unsubscribeFocus: (() => void) | null = null;
  private unsubscribeVisibility: (() => void) | null = null;
  private callbacks: ConversationActivityCallbacks;
  private readonly causalClock: ConversationActivityCausalClock;

  constructor(private readonly options: CreateConversationActivityRuntimeOptions) {
    this.activeConversationId = options.activeConversationId;
    this.lastInputActiveConversationId = options.activeConversationId;
    this.accountScopeKey = options.accountScopeKey;
    this.causalClock =
      options.causalClock ?? createConversationActivityCausalClock();
    this.callbacks = {
      refreshHistory: options.refreshHistory,
      invalidateInactiveTranscript: options.invalidateInactiveTranscript,
      onMutationNotice: options.onMutationNotice,
    };
    if (this.accountScopeKey) {
      this.mergeHistory(
        options.historyItems,
        options.historyActivityRevision,
      );
    }
  }

  start = (): void => {
    if (this.started) return;
    this.started = true;
    this.unsubscribeFocus = this.options.effects.subscribeWindowFocus(() => {
      void this.refreshCanonicalHistory();
    });
    this.unsubscribeVisibility =
      this.options.effects.subscribeVisibilityChange(() => {
        if (this.options.effects.isDocumentVisible()) {
          void this.refreshCanonicalHistory();
        }
      });
    void this.refreshCanonicalHistory();
  };

  dispose = (): void => {
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
      inputs.activeConversationId !== this.lastInputActiveConversationId;
    if (accountChanged) {
      this.resetAccount(inputs.accountScopeKey);
    }
    const accountRefreshPending = this.accountRefreshPending;
    this.activeConversationId = inputs.activeConversationId;
    this.lastInputActiveConversationId = inputs.activeConversationId;
    if (inputs.accountScopeKey) {
      this.mergeHistory(inputs.historyItems, inputs.historyActivityRevision);
    } else {
      this.loadedConversationIds.clear();
    }
    this.accountRefreshPending = false;
    this.reconcilePolling();
    if (
      this.started &&
      inputs.accountScopeKey &&
      (accountChanged || accountRefreshPending || navigationChanged)
    ) {
      void this.refreshCanonicalHistory();
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

  selectOperationLabel = (
    conversationId: string | null | undefined,
  ): ConversationActivityOperationLabel | null =>
    selectConversationOperationLabel(this.state, conversationId);

  hasEffectiveUnread = (
    conversationId: string | null | undefined,
  ): boolean => selectConversationHasEffectiveUnread(this.state, conversationId);

  selectAttentionCursor = (
    conversationId: string | null | undefined,
  ): string | null => selectConversationAttentionCursor(this.state, conversationId);

  isConversationLocked = (
    conversationId: string | null | undefined,
  ): boolean => selectConversationIsLocked(this.state, conversationId);

  hasManualUnreadGuard = (
    conversationId: string | null | undefined,
  ): boolean => selectManualUnreadGuard(this.state, conversationId);

  updateActiveConversationId = (conversationId: string | null): void => {
    this.activeConversationId = conversationId;
  };

  startRequest = (
    conversationId: string,
    requestId: string,
    status: ActiveOperationStatus,
    kind: ActiveOperationKind,
  ): number => {
    const revision = this.nextResponseRevision();
    this.dispatch({
      type: "request_started",
      conversationId,
      requestId,
      status,
      kind,
      revision,
    });
    void this.refreshCanonicalHistory();
    return revision;
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

  finishTransport = (
    conversationId: string,
    requestId: string,
    controller?: AbortController,
  ): boolean => {
    this.releaseTransport(conversationId, requestId, controller);
    if (!this.isRequestCurrent(conversationId, requestId)) return false;
    const revision = this.nextResponseRevision();
    this.dispatch({
      type: "request_transport_finished",
      conversationId,
      requestId,
      revision,
    });
    void this.refreshCanonicalHistory();
    return true;
  };

  retireRequest = (conversationId: string, requestId: string): boolean => {
    if (!this.isRequestCurrent(conversationId, requestId)) return false;
    this.dispatch({ type: "request_retired", conversationId, requestId });
    return true;
  };

  isRequestCurrent = (conversationId: string, requestId: string): boolean =>
    selectConversationRequestIsCurrent(this.state, conversationId, requestId);

  synchronizeAccountScope = (accountScopeKey: string | null): boolean => {
    if (accountScopeKey === this.accountScopeKey) return false;
    this.resetAccount(accountScopeKey);
    return true;
  };

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
  ): boolean =>
    selectConversationMutationIsPending(this.state, conversationId, action);

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

  private mergeHistory(
    historyItems: readonly HistoryItem[],
    responseRevision?: number,
    replaceLoadedConversationIds = true,
  ): void {
    if (replaceLoadedConversationIds) this.loadedConversationIds.clear();
    for (const item of historyItems) {
      if (item.type !== "chat") continue;
      const conversationId = item.conversation_id ?? item.id;
      this.loadedConversationIds.add(conversationId);
      if (!item.activity) continue;

      const priorRecord = this.state.byConversationId[conversationId];
      const priorActivity = priorRecord?.canonical ?? null;
      const revision = responseRevision ?? this.nextResponseRevision();
      const transportFinishedRevision =
        priorRecord?.request?.transportFinishedRevision;
      const canSettleRequest = Boolean(
        typeof transportFinishedRevision === "number" &&
        revision > transportFinishedRevision &&
        item.activity.operation.status === "idle",
      );
      if (activitiesAreEqual(priorActivity, item.activity) && !canSettleRequest) continue;
      const settled =
        isUnresolvedOperation(priorActivity) &&
        !isUnresolvedOperation(item.activity);
      this.dispatch({
        type: "server_projection_merged",
        conversationId,
        activity: item.activity,
        revision,
        activeView:
          conversationId === this.currentActiveConversationId(),
      });
      const requestSettled = Boolean(
        priorRecord?.request &&
        !this.state.byConversationId[conversationId]?.request,
      );
      if ((settled || requestSettled) && conversationId !== this.currentActiveConversationId()) {
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
    this.abortMutationTransport(conversationId);
    const controller = new AbortController();
    this.mutationTransports.set(conversationId, { mutationId, controller });
    this.dispatch({
      type: "mutation_started",
      conversationId,
      mutationId,
      action,
      revision: this.nextResponseRevision(),
      activeView: conversationId === this.currentActiveConversationId(),
    });

    let request: Promise<ConversationActivity>;
    try {
      request = this.options.patchActivity(conversationId, patch, {
        signal: controller.signal,
      });
    } catch (error) {
      request = Promise.reject(error);
    }

    return request.then(
      (activity) => {
        if (!this.mutationIsCurrent(conversationId, mutationId, epoch)) return;
        const priorActivity =
          this.state.byConversationId[conversationId]?.canonical ?? null;
        this.dispatch({
          type: "mutation_succeeded",
          conversationId,
          mutationId,
          activity,
        });
        const nextActivity =
          this.state.byConversationId[conversationId]?.canonical ?? null;
        if (
          isUnresolvedOperation(priorActivity) &&
          !isUnresolvedOperation(nextActivity) &&
          conversationId !== this.currentActiveConversationId()
        ) {
          this.callbacks.invalidateInactiveTranscript(conversationId);
        }
        this.callbacks.onMutationNotice({
          conversationId,
          action,
          outcome: "success",
        });
        void this.refreshCanonicalHistory();
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
    ).finally(() => {
      const registered = this.mutationTransports.get(conversationId);
      if (registered?.mutationId === mutationId) {
        this.mutationTransports.delete(conversationId);
      }
    });
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
    this.responseRevision = Math.max(
      this.responseRevision + 1,
      this.causalClock.nextRevision(),
    );
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
      this.started &&
      Boolean(this.accountScopeKey) &&
      this.hasUnresolvedWork() &&
      this.refreshInFlight?.epoch !== this.accountEpoch;
    if (!shouldPoll) {
      this.cancelPolling();
      return;
    }
    if (this.cancelPoll) return;
    this.cancelPoll = this.options.effects.schedulePoll(
      () => {
        this.cancelPoll = null;
        void this.refreshCanonicalHistory();
      },
      ACTIVITY_POLL_CADENCE_MS,
    );
  }

  private cancelPolling(): void {
    this.cancelPoll?.();
    this.cancelPoll = null;
  }

  private refreshCanonicalHistory(): Promise<void> {
    if (!this.accountScopeKey) return Promise.resolve();
    if (this.refreshInFlight?.epoch === this.accountEpoch) {
      return this.refreshInFlight.promise;
    }
    this.cancelPolling();
    const epoch = this.accountEpoch;
    const responseRevision = this.nextResponseRevision();
    let refreshResult:
      | ConversationActivityHistorySnapshot
      | readonly HistoryItem[]
      | void
      | Promise<
          ConversationActivityHistorySnapshot | readonly HistoryItem[] | void
        >;
    try {
      refreshResult = this.callbacks.refreshHistory();
    } catch {
      refreshResult = Promise.reject(new Error("Activity refresh failed"));
    }
    const promise = Promise.resolve(refreshResult)
      .then((historyItems) => {
        if (epoch !== this.accountEpoch || historyItems === undefined) return;
        if (isConversationActivityHistorySnapshot(historyItems)) {
          this.mergeHistory(
            historyItems.items,
            historyItems.revision,
            false,
          );
        } else {
          this.mergeHistory(historyItems, responseRevision, false);
        }
      })
      .catch(() => {
        // A failed refresh carries no activity truth. Keep the current surface.
      })
      .finally(() => {
        if (this.refreshInFlight?.promise === promise) {
          this.refreshInFlight = null;
          this.reconcilePolling();
        }
      });
    this.refreshInFlight = { epoch, promise };
    return promise;
  }

  private resetAccount(nextAccountScopeKey: string | null): void {
    this.abortRegisteredTransports();
    this.accountEpoch += 1;
    this.accountScopeKey = nextAccountScopeKey;
    this.accountRefreshPending = Boolean(nextAccountScopeKey);
    this.responseRevision = 0;
    this.mutationSequences.clear();
    this.loadedConversationIds.clear();
    this.dispatch({ type: "account_reset" });
  }

  private abortRegisteredTransports(): void {
    for (const controller of this.transports.values()) controller.abort();
    this.transports.clear();
    for (const { controller } of this.mutationTransports.values()) {
      controller.abort();
    }
    this.mutationTransports.clear();
  }

  private abortMutationTransport(conversationId: string): void {
    this.mutationTransports.get(conversationId)?.controller.abort();
    this.mutationTransports.delete(conversationId);
  }

  private currentActiveConversationId(): string | null {
    return this.activeConversationId;
  }
}

export const createConversationActivityRuntime = (
  options: CreateConversationActivityRuntimeOptions,
): ConversationActivityRuntime => new ConversationActivityRuntimeOwner(options);

export type UseConversationActivityOptions = ConversationActivityInputs &
  ConversationActivityCallbacks &
    Readonly<{
      causalClock?: ConversationActivityCausalClock;
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
    | "updateActiveConversationId"
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
      causalClock: options.causalClock,
    }),
  );
  const state = useSyncExternalStore(
    runtime.subscribe,
    runtime.getState,
    runtime.getState,
  );

  useLayoutEffect(() => {
    runtime.synchronizeAccountScope(options.accountScopeKey);
    runtime.updateActiveConversationId(options.activeConversationId);
  }, [runtime, options.accountScopeKey, options.activeConversationId]);

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
      historyActivityRevision: options.historyActivityRevision,
      activeConversationId: options.activeConversationId,
      accountScopeKey: options.accountScopeKey,
    });
  }, [
    runtime,
    options.historyItems,
    options.historyActivityRevision,
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
    selectOperationLabel: runtime.selectOperationLabel,
    hasEffectiveUnread: runtime.hasEffectiveUnread,
    selectAttentionCursor: runtime.selectAttentionCursor,
    isConversationLocked: runtime.isConversationLocked,
    hasManualUnreadGuard: runtime.hasManualUnreadGuard,
    startRequest: runtime.startRequest,
    progressRequest: runtime.progressRequest,
    finishTransport: runtime.finishTransport,
    retireRequest: runtime.retireRequest,
    isRequestCurrent: runtime.isRequestCurrent,
    synchronizeAccountScope: runtime.synchronizeAccountScope,
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
