import { describe, expect, test } from "bun:test";

import {
  TRANSCRIPT_CACHE_POLICY,
  TranscriptSessionCache,
  type TranscriptMutation,
  type TranscriptNavigationState,
} from "../lib/chat-transcript-session-cache";

type Snapshot = {
  messages: string[];
  actions: string[];
};

function snapshot(conversationId: string, suffix = "current"): Snapshot {
  return {
    messages: [`${conversationId}:${suffix}:message`],
    actions: [`${conversationId}:${suffix}:action`],
  };
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, reject, resolve };
}

async function seed(
  cache: TranscriptSessionCache<Snapshot>,
  userId: string,
  conversationId: string,
  value = snapshot(conversationId),
) {
  const states: TranscriptNavigationState<Snapshot>[] = [];
  const navigation = cache.navigate({
    userId,
    conversationId,
    load: async () => value,
    onState: (state) => states.push(state),
  });
  await navigation.completion;
  return states;
}

describe("chat transcript session cache", () => {
  test("allows only the latest delayed navigation to commit transcript state", async () => {
    const cache = new TranscriptSessionCache<Snapshot>();
    const delayedA = deferred<Snapshot>();
    const delayedB = deferred<Snapshot>();
    const statesA: TranscriptNavigationState<Snapshot>[] = [];
    const statesB: TranscriptNavigationState<Snapshot>[] = [];
    const observedA: { signal?: AbortSignal } = {};

    const navigationA = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-a",
      load: (signal) => {
        observedA.signal = signal;
        return delayedA.promise;
      },
      onState: (state) => statesA.push(state),
    });
    const navigationB = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-b",
      load: () => delayedB.promise,
      onState: (state) => statesB.push(state),
    });

    expect(observedA.signal?.aborted).toBe(true);
    expect(statesA).toEqual([
      { phase: "loading", source: "cache_miss", snapshot: null },
    ]);
    expect(statesB).toEqual([
      { phase: "loading", source: "cache_miss", snapshot: null },
    ]);

    delayedB.resolve(snapshot("conversation-b", "network"));
    await navigationB.completion;
    delayedA.resolve(snapshot("conversation-a", "late-network"));
    await navigationA.completion;

    expect(statesA).toEqual([
      { phase: "loading", source: "cache_miss", snapshot: null },
    ]);
    expect(statesB).toEqual([
      { phase: "loading", source: "cache_miss", snapshot: null },
      {
        phase: "ready",
        source: "network",
        snapshot: snapshot("conversation-b", "network"),
      },
    ]);
  });

  test("suppresses an older navigation error after a newer conversation wins", async () => {
    const cache = new TranscriptSessionCache<Snapshot>();
    const delayedA = deferred<Snapshot>();
    const statesA: TranscriptNavigationState<Snapshot>[] = [];
    const statesB: TranscriptNavigationState<Snapshot>[] = [];

    const navigationA = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-a",
      load: () => delayedA.promise,
      onState: (state) => statesA.push(state),
    });
    const navigationB = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-b",
      load: async () => snapshot("conversation-b"),
      onState: (state) => statesB.push(state),
    });

    await navigationB.completion;
    delayedA.reject(new Error("late A failure"));
    await navigationA.completion;

    expect(statesA).toEqual([
      { phase: "loading", source: "cache_miss", snapshot: null },
    ]);
    expect(statesB.at(-1)).toEqual({
      phase: "ready",
      source: "network",
      snapshot: snapshot("conversation-b"),
    });
  });

  test("starts a new request when revisiting a key whose prior request was aborted", async () => {
    const cache = new TranscriptSessionCache<Snapshot>();
    const firstA = deferred<Snapshot>();
    const secondA = deferred<Snapshot>();
    let aLoadCount = 0;

    const initialA = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-a",
      load: () => {
        aLoadCount += 1;
        return firstA.promise;
      },
      onState: () => undefined,
    });
    const navigationB = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-b",
      load: async () => snapshot("conversation-b"),
      onState: () => undefined,
    });
    await navigationB.completion;

    const revisitStates: TranscriptNavigationState<Snapshot>[] = [];
    const revisitA = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-a",
      load: () => {
        aLoadCount += 1;
        return secondA.promise;
      },
      onState: (state) => revisitStates.push(state),
    });

    expect(aLoadCount).toBe(2);
    secondA.resolve(snapshot("conversation-a", "revisit"));
    await revisitA.completion;
    firstA.resolve(snapshot("conversation-a", "aborted"));
    await initialA.completion;

    expect(revisitStates.at(-1)).toEqual({
      phase: "ready",
      source: "network",
      snapshot: snapshot("conversation-a", "revisit"),
    });
  });

  test("clears prior conversation content on a new-key cache miss", async () => {
    const cache = new TranscriptSessionCache<Snapshot>();
    await seed(cache, "user-1", "conversation-a");
    const delayedB = deferred<Snapshot>();
    const states: TranscriptNavigationState<Snapshot>[] = [];

    const navigation = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-b",
      load: () => delayedB.promise,
      onState: (state) => states.push(state),
    });

    expect(states[0]).toEqual({
      phase: "loading",
      source: "cache_miss",
      snapshot: null,
    });
    delayedB.resolve(snapshot("conversation-b"));
    await navigation.completion;
  });

  test("reuses a fresh A transcript on A to B to A without another load", async () => {
    let now = 0;
    const cache = new TranscriptSessionCache<Snapshot>({ now: () => now });
    const loads = new Map<string, number>();

    const navigate = async (conversationId: string) => {
      const states: TranscriptNavigationState<Snapshot>[] = [];
      const navigation = cache.navigate({
        userId: "user-1",
        conversationId,
        load: async () => {
          loads.set(conversationId, (loads.get(conversationId) ?? 0) + 1);
          return snapshot(conversationId);
        },
        onState: (state) => states.push(state),
      });
      await navigation.completion;
      return states;
    };

    await navigate("conversation-a");
    now += 1_000;
    await navigate("conversation-b");
    now += 1_000;
    const revisitStates = await navigate("conversation-a");

    expect(loads).toEqual(
      new Map([
        ["conversation-a", 1],
        ["conversation-b", 1],
      ]),
    );
    expect(revisitStates).toEqual([
      {
        phase: "ready",
        source: "fresh_cache",
        snapshot: snapshot("conversation-a"),
      },
    ]);
  });

  test("deduplicates stale background revalidation and commits only its latest selection", async () => {
    let now = 0;
    const cache = new TranscriptSessionCache<Snapshot>({ now: () => now });
    await seed(cache, "user-1", "conversation-a");
    now = TRANSCRIPT_CACHE_POLICY.freshForMs + 1;

    const refresh = deferred<Snapshot>();
    let loadCount = 0;
    const statesFirst: TranscriptNavigationState<Snapshot>[] = [];
    const statesSecond: TranscriptNavigationState<Snapshot>[] = [];
    const load = () => {
      loadCount += 1;
      return refresh.promise;
    };

    const first = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-a",
      load,
      onState: (state) => statesFirst.push(state),
    });
    const second = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-a",
      load,
      onState: (state) => statesSecond.push(state),
    });

    expect(loadCount).toBe(1);
    expect(statesFirst[0]).toEqual({
      phase: "refreshing",
      source: "stale_cache",
      snapshot: snapshot("conversation-a"),
    });
    expect(statesSecond[0]).toEqual(statesFirst[0]);

    refresh.resolve(snapshot("conversation-a", "refreshed"));
    await Promise.all([first.completion, second.completion]);

    expect(statesFirst).toHaveLength(1);
    expect(statesSecond.at(-1)).toEqual({
      phase: "ready",
      source: "network",
      snapshot: snapshot("conversation-a", "refreshed"),
    });
  });

  test("preserves successful same-key content when stale revalidation fails", async () => {
    let now = 0;
    const cache = new TranscriptSessionCache<Snapshot>({ now: () => now });
    await seed(cache, "user-1", "conversation-a");
    now = TRANSCRIPT_CACHE_POLICY.freshForMs + 1;
    const states: TranscriptNavigationState<Snapshot>[] = [];
    const error = new Error("temporary failure");

    const navigation = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-a",
      load: async () => {
        throw error;
      },
      onState: (state) => states.push(state),
    });
    await navigation.completion;

    expect(states).toEqual([
      {
        phase: "refreshing",
        source: "stale_cache",
        snapshot: snapshot("conversation-a"),
      },
      {
        phase: "error",
        source: "network",
        snapshot: snapshot("conversation-a"),
        error,
      },
    ]);
  });

  test("evicts least-recently-used entries by count", async () => {
    const cache = new TranscriptSessionCache<Snapshot>({
      maxEntries: 2,
      maxEstimatedBytes: 10_000,
    });
    await seed(cache, "user-1", "conversation-a");
    await seed(cache, "user-1", "conversation-b");
    expect(
      cache.readSnapshot({ userId: "user-1", conversationId: "conversation-a" }),
    ).not.toBeNull();
    await seed(cache, "user-1", "conversation-c");

    expect(
      cache.readSnapshot({ userId: "user-1", conversationId: "conversation-b" }),
    ).toBeNull();
    expect(
      cache.readSnapshot({ userId: "user-1", conversationId: "conversation-a" }),
    ).not.toBeNull();
    expect(
      cache.readSnapshot({ userId: "user-1", conversationId: "conversation-c" }),
    ).not.toBeNull();
  });

  test("evicts least-recently-used entries by estimated payload bytes", async () => {
    const cache = new TranscriptSessionCache<Snapshot>({
      estimateBytes: (value) => value.messages[0]?.length ?? 0,
      maxEntries: 10,
      maxEstimatedBytes: 20,
    });
    await seed(cache, "user-1", "conversation-a", {
      messages: ["a".repeat(12)],
      actions: [],
    });
    await seed(cache, "user-1", "conversation-b", {
      messages: ["b".repeat(12)],
      actions: [],
    });

    expect(
      cache.readSnapshot({ userId: "user-1", conversationId: "conversation-a" }),
    ).toBeNull();
    expect(
      cache.readSnapshot({ userId: "user-1", conversationId: "conversation-b" }),
    ).not.toBeNull();
  });

  test("clears transcripts scroll state and pending work on user change and logout", async () => {
    const cache = new TranscriptSessionCache<Snapshot>();
    await seed(cache, "user-1", "conversation-a");
    cache.rememberScroll({
      userId: "user-1",
      conversationId: "conversation-a",
      scrollTop: 240,
    });
    const pending = deferred<Snapshot>();
    const observedPending: { signal?: AbortSignal } = {};
    const pendingNavigation = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-b",
      load: (signal) => {
        observedPending.signal = signal;
        return pending.promise;
      },
      onState: () => undefined,
    });

    await seed(cache, "user-2", "conversation-a", snapshot("user-2-a"));
    expect(observedPending.signal?.aborted).toBe(true);
    expect(
      cache.readSnapshot({ userId: "user-1", conversationId: "conversation-a" }),
    ).toBeNull();
    expect(
      cache.readScroll({ userId: "user-1", conversationId: "conversation-a" }),
    ).toBeNull();

    pending.resolve(snapshot("conversation-b", "late"));
    await pendingNavigation.completion;
    await seed(cache, "user-2", "conversation-a", snapshot("user-2-a"));
    cache.rememberScroll({
      userId: "user-2",
      conversationId: "conversation-a",
      scrollTop: 80,
    });
    cache.clearAuthenticatedState();

    expect(
      cache.readSnapshot({ userId: "user-2", conversationId: "conversation-a" }),
    ).toBeNull();
    expect(
      cache.readScroll({ userId: "user-2", conversationId: "conversation-a" }),
    ).toBeNull();
  });

  test("invalidates only documented transcript mutations and preserves rename", async () => {
    const evictingMutations: TranscriptMutation[] = [
      "message_send",
      "retry",
      "recovery",
      "durable_job_completion",
      "conversation_delete",
    ];

    for (const mutation of evictingMutations) {
      const cache = new TranscriptSessionCache<Snapshot>();
      await seed(cache, "user-1", "conversation-a");
      await seed(cache, "user-1", "conversation-b");
      cache.rememberScroll({
        userId: "user-1",
        conversationId: "conversation-a",
        scrollTop: 120,
      });

      expect(
        cache.invalidateForMutation({
          userId: "user-1",
          conversationId: "conversation-a",
          mutation,
        }),
      ).toBe("evicted");
      expect(
        cache.readSnapshot({ userId: "user-1", conversationId: "conversation-a" }),
      ).toBeNull();
      expect(
        cache.readScroll({ userId: "user-1", conversationId: "conversation-a" }),
      ).toBeNull();
      expect(
        cache.readSnapshot({ userId: "user-1", conversationId: "conversation-b" }),
      ).not.toBeNull();
    }

    const cache = new TranscriptSessionCache<Snapshot>();
    await seed(cache, "user-1", "conversation-a");
    expect(
      cache.invalidateForMutation({
        userId: "user-1",
        conversationId: "conversation-a",
        mutation: "conversation_rename",
      }),
    ).toBe("preserved");
    expect(
      cache.readSnapshot({ userId: "user-1", conversationId: "conversation-a" }),
    ).not.toBeNull();
  });

  test("does not retain per-key metadata after invalidation and ignored abort", async () => {
    const cache = new TranscriptSessionCache<Snapshot>();
    const pending = deferred<Snapshot>();
    const navigation = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-active",
      load: () => pending.promise,
      onState: () => undefined,
    });

    cache.invalidateForMutation({
      userId: "user-1",
      conversationId: "conversation-active",
      mutation: "message_send",
    });
    for (let index = 0; index < 1_000; index += 1) {
      cache.invalidateForMutation({
        userId: "user-1",
        conversationId: `conversation-${index}`,
        mutation: "message_send",
      });
    }

    pending.resolve(snapshot("conversation-active", "late"));
    await navigation.completion;

    expect(
      cache.readSnapshot({
        userId: "user-1",
        conversationId: "conversation-active",
      }),
    ).toBeNull();
    const retainedMapSizes = Object.values(
      cache as unknown as Record<string, unknown>,
    )
      .filter((value): value is Map<unknown, unknown> => value instanceof Map)
      .map((value) => value.size);
    expect(retainedMapSizes.every((size) => size === 0)).toBe(true);
  });

  test("keeps latest-navigation safety when cache retention is disabled", async () => {
    const cache = new TranscriptSessionCache<Snapshot>({ maxEntries: 0 });
    const delayedA = deferred<Snapshot>();
    const statesA: TranscriptNavigationState<Snapshot>[] = [];
    const statesB: TranscriptNavigationState<Snapshot>[] = [];

    const navigationA = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-a",
      load: () => delayedA.promise,
      onState: (state) => statesA.push(state),
    });
    const navigationB = cache.navigate({
      userId: "user-1",
      conversationId: "conversation-b",
      load: async () => snapshot("conversation-b"),
      onState: (state) => statesB.push(state),
    });

    await navigationB.completion;
    delayedA.resolve(snapshot("conversation-a", "late"));
    await navigationA.completion;

    expect(statesA).toEqual([
      { phase: "loading", source: "cache_miss", snapshot: null },
    ]);
    expect(statesB.at(-1)).toEqual({
      phase: "ready",
      source: "network",
      snapshot: snapshot("conversation-b"),
    });
    expect(
      cache.readSnapshot({ userId: "user-1", conversationId: "conversation-b" }),
    ).toBeNull();
  });
});
