import { describe, expect, test } from "bun:test";

import type {
  ConversationActivity,
  ConversationActivityPatch,
  HistoryItem,
} from "../lib/argus-api";
import {
  createConversationActivityRuntime,
  type ConversationActivityEffectsAdapter,
  type ConversationActivityMutationNotice,
} from "../components/chat/useConversationActivity";

const idleActivity = (
  attention: ConversationActivity["attention"]["status"] = "none",
  cursor: string | null = null,
): ConversationActivity => ({
  operation: { status: "idle", kind: null, updated_at: null },
  attention: { status: attention, cursor },
});

const workingActivity = (
  status: Exclude<ConversationActivity["operation"]["status"], "idle">,
): ConversationActivity => ({
  operation: {
    status,
    kind: "chat_turn",
    updated_at: "2026-08-01T12:00:00Z",
  },
  attention: { status: "none", cursor: null },
});

const chat = (
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

const deferred = <T,>(): Deferred<T> => {
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

class ControlledEffects implements ConversationActivityEffectsAdapter {
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

function runtimeHarness(options: Readonly<{
  historyItems?: HistoryItem[];
  activeConversationId?: string | null;
  accountScopeKey?: string | null;
  patchActivity?: (
    conversationId: string,
    patch: ConversationActivityPatch,
    options: Readonly<{ signal: AbortSignal }>,
  ) => Promise<ConversationActivity>;
  refreshHistory?: () =>
    | readonly HistoryItem[]
    | void
    | Promise<readonly HistoryItem[] | void>;
}> = {}) {
  const effects = new ControlledEffects();
  const refreshes: string[] = [];
  const invalidations: string[] = [];
  const notices: ConversationActivityMutationNotice[] = [];
  const runtime = createConversationActivityRuntime({
    historyItems: options.historyItems ?? [],
    activeConversationId: options.activeConversationId ?? null,
    accountScopeKey: options.accountScopeKey ?? "account-a",
    refreshHistory: options.refreshHistory ?? (() => {
      refreshes.push("refresh");
    }),
    invalidateInactiveTranscript: (conversationId) => {
      invalidations.push(conversationId);
    },
    onMutationNotice: (notice) => {
      notices.push(notice);
    },
    patchActivity:
      options.patchActivity ??
      (async () => idleActivity()),
    effects,
  });
  return { runtime, effects, refreshes, invalidations, notices };
}

const drainMicrotasks = async (): Promise<void> => {
  await Promise.resolve();
  await Promise.resolve();
};

describe("conversation activity refresh ownership", () => {
  test("bootstraps and polls only while loaded canonical or local work is unresolved", async () => {
    const harness = runtimeHarness({
      historyItems: [chat("conversation-a", workingActivity("queued"))],
      activeConversationId: "conversation-b",
    });

    harness.runtime.start();
    await drainMicrotasks();
    expect(harness.refreshes).toHaveLength(1);
    expect(harness.effects.hasPoll()).toBe(true);

    harness.effects.firePoll();
    await drainMicrotasks();
    expect(harness.refreshes).toHaveLength(2);

    harness.runtime.updateInputs({
      historyItems: [chat("conversation-a", idleActivity("new_activity", "cursor-a"))],
      activeConversationId: "conversation-b",
      accountScopeKey: "account-a",
    });
    expect(harness.effects.hasPoll()).toBe(false);
    expect(harness.invalidations).toEqual(["conversation-a"]);
    harness.effects.firePoll();
    expect(harness.refreshes).toHaveLength(2);

    harness.runtime.startRequest(
      "conversation-local",
      "request-local",
      "queued",
      "chat_turn",
    );
    await drainMicrotasks();
    expect(harness.refreshes).toHaveLength(3);
    expect(harness.effects.hasPoll()).toBe(true);

    harness.runtime.settleRequest("conversation-local", "request-local");
    await drainMicrotasks();
    expect(harness.refreshes).toHaveLength(4);
    expect(harness.effects.hasPoll()).toBe(false);
  });

  test("does not invent working state or idle polling when cold activity refresh fails", () => {
    const effects = new ControlledEffects();
    const runtime = createConversationActivityRuntime({
      historyItems: [chat("cold-conversation")],
      activeConversationId: "cold-conversation",
      accountScopeKey: "account-a",
      refreshHistory: () => {
        throw new Error("activity unavailable");
      },
      invalidateInactiveTranscript: () => undefined,
      onMutationNotice: () => undefined,
      patchActivity: async () => idleActivity(),
      effects,
    });

    expect(() => runtime.start()).not.toThrow();
    expect(runtime.selectPresentation("cold-conversation")).toBe("none");
    expect(runtime.isConversationLocked("cold-conversation")).toBe(false);
    expect(effects.hasPoll()).toBe(false);
  });

  test("refreshes on focus and only on a visible-document resume", async () => {
    const harness = runtimeHarness();
    harness.runtime.start();
    await drainMicrotasks();

    harness.effects.fireFocus();
    await drainMicrotasks();
    harness.effects.setVisible(false);
    expect(harness.refreshes).toHaveLength(2);

    harness.effects.setVisible(true);
    await drainMicrotasks();
    expect(harness.refreshes).toHaveLength(3);
  });

  test("refreshes bounded history when navigation changes the active conversation", async () => {
    const harness = runtimeHarness({ activeConversationId: "conversation-a" });
    harness.runtime.start();
    await drainMicrotasks();

    harness.runtime.updateInputs({
      historyItems: [],
      activeConversationId: "conversation-b",
      accountScopeKey: "account-a",
    });
    await drainMicrotasks();

    expect(harness.refreshes).toHaveLength(2);
  });

  test("keeps inactive settlement independent and transport release non-terminal", async () => {
    const harness = runtimeHarness({ activeConversationId: "conversation-b" });
    harness.runtime.start();
    await drainMicrotasks();
    harness.runtime.startRequest(
      "conversation-a",
      "request-current",
      "running",
      "chat_turn",
    );

    const controller = new AbortController();
    harness.runtime.registerTransport(
      "conversation-a",
      "request-current",
      controller,
    );
    harness.runtime.releaseTransport(
      "conversation-a",
      "request-current",
      controller,
    );
    expect(controller.signal.aborted).toBe(false);
    expect(harness.invalidations).toEqual([]);

    harness.runtime.settleRequest("conversation-a", "request-stale", {
      invalidateInactiveTranscript: true,
    });
    expect(harness.runtime.isRequestCurrent("conversation-a", "request-current")).toBe(
      true,
    );
    expect(harness.invalidations).toEqual([]);

    harness.runtime.settleRequest("conversation-a", "request-current", {
      invalidateInactiveTranscript: true,
    });
    expect(harness.invalidations).toEqual(["conversation-a"]);
  });

  test("coalesces polling, focus, and visibility into one refresh with no idle tail", async () => {
    const firstRefresh = deferred<readonly HistoryItem[] | void>();
    const secondRefresh = deferred<readonly HistoryItem[] | void>();
    const refreshes = [firstRefresh, secondRefresh];
    let refreshIndex = 0;
    const harness = runtimeHarness({
      historyItems: [chat("conversation-a", workingActivity("running"))],
      activeConversationId: "conversation-b",
      refreshHistory: () => refreshes[refreshIndex++]!.promise,
    });

    harness.runtime.start();
    harness.effects.fireFocus();
    harness.effects.setVisible(true);
    expect(refreshIndex).toBe(1);

    firstRefresh.resolve([
      chat("conversation-a", workingActivity("running")),
    ]);
    await drainMicrotasks();
    expect(harness.effects.hasPoll()).toBe(true);

    harness.effects.firePoll();
    harness.effects.fireFocus();
    harness.effects.setVisible(true);
    expect(refreshIndex).toBe(2);

    harness.runtime.updateInputs({
      historyItems: [
        chat("conversation-a", idleActivity("new_activity", "cursor-done")),
      ],
      activeConversationId: "conversation-b",
      accountScopeKey: "account-a",
    });
    secondRefresh.resolve([
      chat("conversation-a", idleActivity("new_activity", "cursor-done")),
    ]);
    await drainMicrotasks();

    expect(harness.effects.hasPoll()).toBe(false);
    harness.effects.firePoll();
    expect(refreshIndex).toBe(2);
  });
});

describe("conversation activity mutations", () => {
  test("optimistically marks read with the exact cursor and refreshes canonical truth", async () => {
    const request = deferred<ConversationActivity>();
    const patches: Array<{
      conversationId: string;
      patch: ConversationActivityPatch;
    }> = [];
    const harness = runtimeHarness({
      historyItems: [
        chat("conversation-a", idleActivity("new_activity", "cursor-visible")),
      ],
      activeConversationId: "conversation-a",
      patchActivity: (conversationId, patch) => {
        patches.push({ conversationId, patch });
        return request.promise;
      },
    });
    harness.runtime.start();
    await drainMicrotasks();

    const mutation = harness.runtime.markRead("conversation-a", null);
    expect(patches).toEqual([
      {
        conversationId: "conversation-a",
        patch: { action: "mark_read", through_attention_cursor: null },
      },
    ]);
    expect(harness.runtime.selectPresentation("conversation-a")).toBe("none");
    expect(harness.runtime.isMutationPending("conversation-a", "mark_read")).toBe(
      true,
    );

    request.resolve(idleActivity());
    await mutation;
    await drainMicrotasks();

    expect(harness.runtime.isMutationPending("conversation-a")).toBe(false);
    expect(harness.notices).toEqual([
      {
        conversationId: "conversation-a",
        action: "mark_read",
        outcome: "success",
      },
    ]);
    expect(harness.refreshes).toHaveLength(2);
  });

  test("scopes stale success, stale failure, and current rollback to mutation identity", async () => {
    const requests = [
      deferred<ConversationActivity>(),
      deferred<ConversationActivity>(),
      deferred<ConversationActivity>(),
    ];
    let requestIndex = 0;
    const harness = runtimeHarness({
      historyItems: [chat("conversation-a", idleActivity())],
      activeConversationId: "conversation-a",
      patchActivity: () => requests[requestIndex++]!.promise,
    });
    harness.runtime.start();

    const staleSuccess = harness.runtime.markUnread("conversation-a");
    const staleFailure = harness.runtime.markRead("conversation-a", null);
    requests[0]!.resolve(idleActivity("manual_unread"));
    await staleSuccess;
    expect(harness.notices).toEqual([]);

    const currentFailure = harness.runtime.markUnread("conversation-a");
    requests[1]!.reject(new Error("older read failed"));
    await staleFailure;
    expect(harness.runtime.selectPresentation("conversation-a")).toBe(
      "manual_unread",
    );
    expect(harness.notices).toEqual([]);

    requests[2]!.reject(new Error("current unread failed"));
    await currentFailure;
    expect(harness.runtime.selectPresentation("conversation-a")).toBe("none");
    expect(harness.notices).toEqual([
      {
        conversationId: "conversation-a",
        action: "mark_unread",
        outcome: "error",
      },
    ]);
  });

  test("keeps local response revisions increasing after a successful mutation", async () => {
    const harness = runtimeHarness({
      historyItems: [chat("conversation-a", idleActivity("new_activity", "cursor-1"))],
      patchActivity: async () => idleActivity(),
    });
    harness.runtime.start();
    const before = harness.runtime.getState().byConversationId["conversation-a"]
      ?.serverRevision;

    await harness.runtime.markRead("conversation-a", "cursor-1");
    harness.runtime.updateInputs({
      historyItems: [chat("conversation-a", idleActivity("needs_input", "cursor-2"))],
      activeConversationId: null,
      accountScopeKey: "account-a",
    });

    const after = harness.runtime.getState().byConversationId["conversation-a"]
      ?.serverRevision;
    expect(after).toBeGreaterThan(before ?? 0);
    expect(harness.runtime.selectPresentation("conversation-a")).toBe("needs_input");
  });

  test("keeps an optimistic mutation current across identical navigation replays", async () => {
    const request = deferred<ConversationActivity>();
    const activity = idleActivity("new_activity", "cursor-stable");
    const harness = runtimeHarness({
      historyItems: [chat("conversation-a", activity)],
      activeConversationId: "conversation-a",
      patchActivity: () => request.promise,
    });
    harness.runtime.start();
    await drainMicrotasks();

    const mutation = harness.runtime.markRead("conversation-a", "cursor-stable");
    harness.runtime.updateInputs({
      historyItems: [chat("conversation-a", { ...activity })],
      activeConversationId: "conversation-b",
      accountScopeKey: "account-a",
    });

    expect(harness.runtime.selectPresentation("conversation-a")).toBe("none");
    request.resolve(idleActivity());
    await mutation;
    expect(
      harness.runtime.getState().byConversationId["conversation-a"]?.canonical,
    ).toEqual(idleActivity());
  });

  test("does not let an older in-flight history response supersede a newer mutation", async () => {
    const refresh = deferred<readonly HistoryItem[] | void>();
    const mutationResponse = deferred<ConversationActivity>();
    let refreshCount = 0;
    const harness = runtimeHarness({
      historyItems: [
        chat("conversation-a", idleActivity("new_activity", "cursor-old")),
      ],
      activeConversationId: "conversation-a",
      refreshHistory: () =>
        refreshCount++ === 0
          ? refresh.promise
          : [chat("conversation-a", idleActivity())],
      patchActivity: () => mutationResponse.promise,
    });
    harness.runtime.start();

    const mutation = harness.runtime.markRead("conversation-a", "cursor-old");
    refresh.resolve([
      chat("conversation-a", idleActivity("needs_input", "cursor-before-read")),
    ]);
    await drainMicrotasks();
    expect(harness.runtime.selectPresentation("conversation-a")).toBe("none");

    mutationResponse.resolve(idleActivity());
    await mutation;
    expect(harness.runtime.selectPresentation("conversation-a")).toBe("none");
    expect(
      harness.runtime.getState().byConversationId["conversation-a"]?.canonical,
    ).toEqual(idleActivity());
  });

  test("invalidates one inactive transcript when a mutation response settles canonical work", async () => {
    const request = deferred<ConversationActivity>();
    const harness = runtimeHarness({
      historyItems: [chat("conversation-a", workingActivity("checking"))],
      activeConversationId: "conversation-b",
      patchActivity: () => request.promise,
    });
    harness.runtime.start();
    await drainMicrotasks();

    const mutation = harness.runtime.markUnread("conversation-a");
    request.resolve(idleActivity("manual_unread", "cursor-terminal"));
    await mutation;
    harness.runtime.updateInputs({
      historyItems: [
        chat(
          "conversation-a",
          idleActivity("manual_unread", "cursor-terminal"),
        ),
      ],
      activeConversationId: "conversation-b",
      accountScopeKey: "account-a",
    });

    expect(harness.invalidations).toEqual(["conversation-a"]);
  });
});

describe("conversation activity account and presentation ownership", () => {
  test("aborts registered transports and ignores late mutation settlement on logout", async () => {
    const request = deferred<ConversationActivity>();
    let mutationSignal: AbortSignal | null = null;
    const harness = runtimeHarness({
      historyItems: [chat("conversation-a", workingActivity("running"))],
      patchActivity: (_conversationId, _patch, options) => {
        mutationSignal = options.signal;
        return request.promise;
      },
    });
    harness.runtime.start();
    const controllerA = new AbortController();
    const controllerB = new AbortController();
    harness.runtime.registerTransport("conversation-a", "request-a", controllerA);
    harness.runtime.registerTransport("conversation-b", "request-b", controllerB);
    const mutation = harness.runtime.markUnread("conversation-a");

    harness.runtime.updateInputs({
      historyItems: [],
      activeConversationId: null,
      accountScopeKey: null,
    });

    expect(controllerA.signal.aborted).toBe(true);
    expect(controllerB.signal.aborted).toBe(true);
    expect(mutationSignal?.aborted).toBe(true);
    expect(harness.runtime.getState().byConversationId).toEqual({});
    expect(harness.effects.hasPoll()).toBe(false);

    request.resolve(idleActivity("manual_unread"));
    await mutation;
    expect(harness.notices).toEqual([]);
  });

  test("uses layout-synchronous active identity before passive inputs settle", async () => {
    const harness = runtimeHarness({
      activeConversationId: "conversation-a",
    });
    harness.runtime.startRequest(
      "conversation-a",
      "request-a",
      "running",
      "chat_turn",
    );
    await drainMicrotasks();

    harness.runtime.updateActiveConversationId("conversation-b");
    harness.runtime.settleRequest("conversation-a", "request-a", {
      invalidateInactiveTranscript: true,
    });

    expect(harness.invalidations).toEqual(["conversation-a"]);
  });

  test("exposes request, guard, aggregate, and announcement accessors", () => {
    const harness = runtimeHarness({
      historyItems: [
        chat("conversation-a", idleActivity("manual_unread", "cursor-a")),
        chat("conversation-b", idleActivity("needs_input", "cursor-b")),
      ],
      activeConversationId: "conversation-a",
    });
    harness.runtime.start();

    expect(harness.runtime.selectAggregatePresentation()).toBe("needs_input");
    expect(harness.runtime.hasManualUnreadGuard("conversation-a")).toBe(true);
    harness.runtime.resetViewEpoch("conversation-a");
    expect(harness.runtime.hasManualUnreadGuard("conversation-a")).toBe(false);

    harness.runtime.startRequest(
      "conversation-a",
      "request-a",
      "running",
      "chat_turn",
    );
    expect(harness.runtime.isRequestCurrent("conversation-a", "request-a")).toBe(
      true,
    );
    expect(harness.runtime.selectAggregatePresentation()).toBe("working");

    const announcement = harness.runtime.getAnnouncement("conversation-a");
    expect(announcement?.presentation).toBe("working");
    harness.runtime.acknowledgeAnnouncement(
      "conversation-a",
      announcement?.key ?? "",
    );
    expect(harness.runtime.getAnnouncement("conversation-a")).toBeNull();
  });
});
