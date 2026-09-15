import { describe, expect, test } from "bun:test";
import { createTranscriptFreshnessRuntime, type SavedConversationTranscript, type TranscriptFreshnessInputs } from "../lib/conversation-transcript-freshness";
import { deferred, drainMicrotasks } from "./fixtures/conversation-activity-runtime";

const snapshot = (id: string): SavedConversationTranscript => ({ messages: [], latestMessageId: id });
function harness() {
  const requests: { signal: AbortSignal; result: ReturnType<typeof deferred<SavedConversationTranscript>> }[] = [];
  const applied: string[] = [];
  const runtime = createTranscriptFreshnessRuntime({
    load: (_id, signal) => {
      const result = deferred<SavedConversationTranscript>();
      requests.push({ signal, result });
      return result.promise;
    },
    apply: (_id, saved) => applied.push(saved.latestMessageId!),
  });
  const inputs: TranscriptFreshnessInputs = {
    accountId: "account", conversationId: "conversation", latestMessageId: "old",
    activityRevision: 1, requestId: null, ready: true, visibleMessageIds: new Set(),
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
    h.update({ requestId: null, visibleMessageIds: new Set(["reply"]) });
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
