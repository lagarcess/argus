import type { ConversationActivity, ConversationActivityPatch, HistoryItem } from "../../lib/argus-api";
import { createConversationActivityRuntime, type ConversationActivityEffectsAdapter, type ConversationActivityMutationNotice } from "../../components/chat/useConversationActivity";
import type { ConversationActivityCausalClock, ConversationActivityHistorySnapshot } from "../../lib/conversation-activity-state";

export const idleActivity = (
  attention: ConversationActivity["attention"]["status"] = "none",
  cursor: string | null = null,
): ConversationActivity => ({
  operation: { status: "idle", kind: null, updated_at: null },
  attention: { status: attention, cursor },
});

export const workingActivity = (
  status: Exclude<ConversationActivity["operation"]["status"], "idle">,
): ConversationActivity => ({
  operation: {
    status,
    kind: "chat_turn",
    updated_at: "2026-08-01T12:00:00Z",
  },
  attention: { status: "none", cursor: null },
});

export const chat = (
  id: string,
  activity?: ConversationActivity | null,
): HistoryItem => ({
  type: "chat",
  id,
  title: id,
  title_source: "ai_generated",
  subtitle: "Recent work",
  pinned: false,
  created_at: "2026-08-01T12:00:00Z",
  conversation_id: id,
  ...(activity === undefined ? {} : { activity }),
});

type Deferred<T> = Readonly<{
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (error: unknown) => void;
}>;

export const deferred = <T,>(): Deferred<T> => {
  let resolvePromise: ((value: T) => void) | null = null;
  let rejectPromise: ((error: unknown) => void) | null = null;
  const promise = new Promise<T>((resolve, reject) => {
    resolvePromise = resolve;
    rejectPromise = reject;
  });
  return {
    promise,
    resolve: (value: T) => resolvePromise?.(value),
    reject: (error: unknown) => rejectPromise?.(error),
  };
};

export class ControlledEffects implements ConversationActivityEffectsAdapter {
  private poll: (() => void) | null = null;
  private focus: (() => void) | null = null;
  private visibilityChange: (() => void) | null = null;
  private visible = true;
  readonly scheduledDelays: number[] = [];

  schedulePoll(callback: () => void, delayMs: number): () => void {
    this.poll = callback;
    this.scheduledDelays.push(delayMs);
    return () => {
      if (this.poll === callback) this.poll = null;
    };
  }

  subscribeWindowFocus(callback: () => void): () => void {
    this.focus = callback;
    return () => {
      if (this.focus === callback) this.focus = null;
    };
  }

  subscribeVisibilityChange(callback: () => void): () => void {
    this.visibilityChange = callback;
    return () => {
      if (this.visibilityChange === callback) this.visibilityChange = null;
    };
  }

  isDocumentVisible(): boolean {
    return this.visible;
  }

  firePoll(): void {
    const callback = this.poll;
    this.poll = null;
    callback?.();
  }

  fireFocus(): void {
    this.focus?.();
  }

  setVisible(visible: boolean): void {
    this.visible = visible;
    this.visibilityChange?.();
  }

  hasPoll(): boolean {
    return this.poll !== null;
  }
}

export function runtimeHarness(options: Readonly<{
  historyItems?: HistoryItem[];
  historyActivityRevision?: number;
  activeConversationId?: string | null;
  accountScopeKey?: string | null;
  patchActivity?: (
    conversationId: string,
    patch: ConversationActivityPatch,
    options: Readonly<{ signal: AbortSignal }>,
  ) => Promise<ConversationActivity>;
  getActivity?: (conversationId: string) => Promise<ConversationActivity>;
  refreshHistory?: () =>
    | ConversationActivityHistorySnapshot
    | readonly HistoryItem[]
    | void
    | Promise<ConversationActivityHistorySnapshot | readonly HistoryItem[] | void>;
  causalClock?: ConversationActivityCausalClock;
}> = {}) {
  const effects = new ControlledEffects();
  const refreshes: string[] = [];
  const invalidations: string[] = [];
  const reloads: string[] = [];
  const notices: ConversationActivityMutationNotice[] = [];
  const runtime = createConversationActivityRuntime({
    historyItems: options.historyItems ?? [],
    historyActivityRevision: options.historyActivityRevision,
    activeConversationId: options.activeConversationId ?? null,
    accountScopeKey: options.accountScopeKey ?? "account-a",
    refreshHistory: options.refreshHistory ?? (() => {
      refreshes.push("refresh");
    }),
    invalidateInactiveTranscript: (conversationId) => {
      invalidations.push(conversationId);
    },
    refreshActiveTranscript: (conversationId) => reloads.push(conversationId),
    onMutationNotice: (notice) => {
      notices.push(notice);
    },
    patchActivity:
      options.patchActivity ??
      (async () => idleActivity()),
    getActivity:
      options.getActivity ??
      (async () => idleActivity()),
    effects,
    causalClock: options.causalClock,
  });
  return { runtime, effects, refreshes, invalidations, reloads, notices };
}

export const drainMicrotasks = async (): Promise<void> => {
  await Promise.resolve();
  await Promise.resolve();
};

