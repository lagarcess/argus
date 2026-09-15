import { describe, expect, test } from "bun:test";
import { createTranscriptFreshnessRuntime, type SavedConversationTranscript, type TranscriptFreshnessInputs } from "../lib/conversation-transcript-freshness";
import { deferred, drainMicrotasks } from "./fixtures/conversation-activity-runtime";

const snapshot = (id: string): SavedConversationTranscript => ({ apiMessages: [], messages: [], latestMessageId: id, unansweredUserMessage: null });
function harness(clock?: { now: () => number; schedule: (callback: () => void, delayMs: number) => () => void }) {
  const requests: { signal: AbortSignal; result: ReturnType<typeof deferred<SavedConversationTranscript>> }[] = [];
  const applied: string[] = [];
  const runtime = createTranscriptFreshnessRuntime({
    clock,
    load: (_id, signal) => {
      const result = deferred<SavedConversationTranscript>();
      requests.push({ signal, result });
      return result.promise;
    },
    apply: (_id, saved) => applied.push(saved.latestMessageId!),
  });
  const inputs: TranscriptFreshnessInputs = {
    accountId: "account", conversationId: "conversation", latestMessageId: "old",
    activityRevision: 1, requestId: null, ready: true, visibleMessages: [],
  };
  runtime.recordLoaded("account", "conversation", snapshot("old"));
  runtime.update(inputs);
  const update = (patch: Partial<TranscriptFreshnessInputs>) => { Object.assign(inputs, patch); runtime.update({ ...inputs }); };
  return { runtime, inputs, requests, applied, update };
}

describe("saved transcript freshness", () => {
  test("an idle-only activity update refreshes from a saved message id, then deduplicates", async () => {
    const h = harness();
    h.update({ latestMessageId: "reply", activityRevision: 2 });
    h.update({ activityRevision: 3 });
    expect(h.requests).toHaveLength(1);
    h.requests[0].result.resolve(snapshot("reply"));
    await drainMicrotasks();
    h.update({ activityRevision: 4 });
    expect(h.requests).toHaveLength(1);
    expect(h.applied).toEqual(["reply"]);
  });

  test("only a successful API read advances the loaded identity; next focus/update retries a failed read", async () => {
    const h = harness();
    h.update({ latestMessageId: "reply", activityRevision: 2 });
    h.requests[0].result.reject(new Error("offline"));
    await drainMicrotasks(); await drainMicrotasks();
    h.update({});
    expect(h.requests).toHaveLength(1);
    h.update({ activityRevision: 3 });
    expect(h.requests).toHaveLength(2);
    expect(h.applied).toEqual([]);
  });

  test("does not overwrite a sender, including after its canonical final is visible", () => {
    const h = harness();
    h.update({ latestMessageId: "reply", activityRevision: 2, requestId: "local" });
    expect(h.requests).toHaveLength(0);
    h.update({ requestId: null, visibleMessages: [{ id: "reply", role: "ai" }] });
    expect(h.requests).toHaveLength(0);
  });

  for (const change of [
    { conversationId: "other" }, { accountId: "other" }, { requestId: "new-local-turn" }, { ready: false },
  ]) {
    test(`rejects a late refresh after ${Object.keys(change)[0]} changes`, async () => {
      const h = harness();
      h.update({ latestMessageId: "reply", activityRevision: 2 });
      h.update(change);
      expect(h.requests[0].signal.aborted).toBe(true);
      h.requests[0].result.resolve(snapshot("reply"));
      await drainMicrotasks();
      expect(h.applied).toEqual([]);
      h.runtime.dispose();
    });
  }

  test("a completion during the read is compared with the actual returned snapshot", async () => {
    const h = harness();
    h.update({ latestMessageId: "reply", activityRevision: 2 });
    h.update({ latestMessageId: "newer-reply", activityRevision: 3 });
    h.requests[0].result.resolve(snapshot("reply"));
    await drainMicrotasks(); await drainMicrotasks();
    expect(h.requests).toHaveLength(2);
    h.requests[1].result.resolve(snapshot("newer-reply"));
    await drainMicrotasks();
    expect(h.applied).toEqual(["reply", "newer-reply"]);
  });

  test("server identity absent or transcript not ready does not invent freshness", () => {
    const h = harness();
    h.update({ latestMessageId: null });
    h.update({ latestMessageId: "reply", ready: false });
    expect(h.requests).toHaveLength(0);
  });
});

function controlledClock() {
  let now = Date.parse("2026-09-15T12:00:00Z");
  let scheduled: { at: number; callback: () => void } | null = null;
  return {
    now: () => now,
    schedule: (callback: () => void, delayMs: number) => {
      const timer = { at: now + delayMs, callback };
      scheduled = timer;
      return () => { if (scheduled === timer) scheduled = null; };
    },
    advance: (ms: number) => {
      now += ms;
      const timer = scheduled;
      if (timer && timer.at <= now) { scheduled = null; timer.callback(); }
    },
    hasTimer: () => scheduled !== null,
  };
}

const unanswered = (id: string, createdAt: number): SavedConversationTranscript => ({
  ...snapshot(id), unansweredUserMessage: { id, createdAt: new Date(createdAt).toISOString() },
});

describe("bounded unanswered user-message checks", () => {
  test("an idle/new-user interleaving keeps reading saved messages until the reply arrives", async () => {
    const clock = controlledClock();
    const h = harness(clock);
    h.update({ latestMessageId: "user", activityRevision: 2 });
    h.requests[0].result.resolve(unanswered("user", clock.now()));
    await drainMicrotasks(); await drainMicrotasks();
    expect(clock.hasTimer()).toBe(true);
    h.update({ visibleMessages: [{ id: "user", role: "user" }] });
    // No further activity update: it stays idle with this same user-message id.
    clock.advance(2_000);
    expect(h.requests).toHaveLength(2);
    h.requests[1].result.resolve(snapshot("reply"));
    await drainMicrotasks(); await drainMicrotasks();
    expect(h.applied).toEqual(["user", "reply"]);
    expect(clock.hasTimer()).toBe(false);
    clock.advance(180_000);
    expect(h.requests).toHaveLength(2);
  });

  test("repeated reads of an unanswered turn stop at its original 180-second deadline", async () => {
    const clock = controlledClock();
    const h = harness(clock);
    const saved = unanswered("user", clock.now());
    h.runtime.recordLoaded("account", "conversation", saved);
    h.update({ latestMessageId: "user", visibleMessages: [{ id: "user", role: "user" }] });
    for (let second = 2; second < 180; second += 2) {
      clock.advance(2_000);
      expect(h.requests).toHaveLength(second / 2);
      h.requests.at(-1)!.result.resolve(saved);
      await drainMicrotasks(); await drainMicrotasks();
    }
    clock.advance(2_000);
    expect(clock.hasTimer()).toBe(false);
    const reads = h.requests.length;
    h.runtime.retry();
    h.update({ activityRevision: 3 });
    clock.advance(180_000);
    expect(h.requests).toHaveLength(reads);
    expect(h.applied).toEqual([]);
  });

  test("an already expired saved user message does not start a fresh timeout window", () => {
    const clock = controlledClock();
    const h = harness(clock);
    h.runtime.recordLoaded("account", "conversation", unanswered("user", clock.now() - 180_000));
    h.update({ latestMessageId: "user" });
    expect(clock.hasTimer()).toBe(false);
    expect(h.requests).toHaveLength(0);
  });

  for (const change of [{ conversationId: "other" }, { accountId: "other" }, { requestId: "local" }, { ready: false }]) {
    test(`stops observer polling when ${Object.keys(change)[0]} changes`, () => {
      const clock = controlledClock();
      const h = harness(clock);
      h.runtime.recordLoaded("account", "conversation", unanswered("user", clock.now()));
      h.update({ latestMessageId: "user" });
      expect(clock.hasTimer()).toBe(true);
      h.update(change);
      expect(clock.hasTimer()).toBe(false);
      h.runtime.dispose();
    });
  }
});

test("a canonical streamed reply after the loaded user stops polling without a sender reload", () => {
  const clock = controlledClock();
  const h = harness(clock);
  h.runtime.recordLoaded("account", "conversation", unanswered("user", clock.now()));
  h.update({ latestMessageId: "user", visibleMessages: [{ id: "user", role: "user" }] });
  expect(clock.hasTimer()).toBe(true);
  h.update({ latestMessageId: "reply", visibleMessages: [{ id: "user", role: "user" }, { id: "reply", role: "ai" }] });
  expect(clock.hasTimer()).toBe(false);
  expect(h.requests).toHaveLength(0);
});

test("an older visible assistant with a stale activity id cannot end the unanswered window", () => {
  const clock = controlledClock();
  const h = harness(clock);
  h.runtime.recordLoaded("account", "conversation", unanswered("user", clock.now()));
  h.update({ visibleMessages: [{ id: "old", role: "ai" }, { id: "user", role: "user" }] });
  expect(clock.hasTimer()).toBe(true);
  h.runtime.dispose();
});

test("the deadline aborts an in-flight reply check and rejects its late result", async () => {
  const clock = controlledClock();
  const h = harness(clock);
  h.runtime.recordLoaded("account", "conversation", unanswered("user", clock.now() - 177_000));
  h.update({ latestMessageId: "user" });
  clock.advance(2_000);
  expect(h.requests).toHaveLength(1);
  clock.advance(1_000);
  expect(clock.hasTimer()).toBe(false);
  expect(h.requests[0].signal.aborted).toBe(true);
  h.requests[0].result.resolve(snapshot("late-reply"));
  await drainMicrotasks();
  expect(h.applied).toEqual([]);
});
