import { describe, expect, test } from "bun:test";
import { createTranscriptFreshnessRuntime, loadSavedConversationTranscript, type SavedConversationTranscript } from "../lib/conversation-transcript-freshness";
import type { ApiMessage, getConversationMessages } from "../lib/argus-api";
import { hydrateMessagesFromApi } from "../components/chat/chat-message-projection";
import { drainMicrotasks } from "./fixtures/conversation-activity-runtime";

function history(count = 1_000) {
  const messages: ApiMessage[] = Array.from({ length: count }, (_, i) => ({
    id: crypto.randomUUID(), conversation_id: "conversation", role: i === count - 1 ? "user" : "assistant",
    content: `Saved message ${i}`, created_at: new Date(Date.now() - (count - i) * 1_000).toISOString(),
  }));
  const requests: { anchor?: string; cursor?: string; count: number }[] = [];
  const loadPage: typeof getConversationMessages = async (_id, limit = 50, cursor, options = {}) => {
    const start = cursor ? Number(cursor) : options.anchorMessageId ? messages.findIndex((m) => m.id === options.anchorMessageId) : 0;
    if (start < 0) throw new Error("Anchor not found");
    const items = messages.slice(start, start + limit);
    requests.push({ anchor: options.anchorMessageId, cursor, count: items.length });
    return { items, next_cursor: start + limit < messages.length ? String(start + limit) : null };
  };
  const load = (signal?: AbortSignal, previous?: SavedConversationTranscript) =>
    loadSavedConversationTranscript("conversation", signal, previous, loadPage);
  const append = (n = 1) => {
    for (let i = 0; i < n; i++) messages.push({ ...messages.at(-1)!, id: crypto.randomUUID(), role: "assistant", metadata: null, content: `New reply ${i}`, created_at: new Date(Date.now() + i).toISOString() });
  };
  return { messages, requests, load, append };
}

describe("saved tail read cost", () => {
  test("1000-message history costs one one-message read per unchanged check and no UI apply", async () => {
    const h = history();
    const initial = await h.load();
    expect(h.requests).toHaveLength(10);
    h.requests.length = 0;
    let tick: (() => void) | undefined;
    let now = Date.now();
    let applied = 0;
    const runtime = createTranscriptFreshnessRuntime({
      load: (_id, signal, previous) => h.load(signal, previous), apply: () => { applied++; },
      clock: { now: () => now, schedule: (fn) => { tick = fn; return () => { if (tick === fn) tick = undefined; }; } },
    });
    runtime.recordLoaded("account", "conversation", initial);
    runtime.update({ accountId: "account", conversationId: "conversation", latestMessageId: initial.latestMessageId, activityRevision: 1, requestId: null, ready: true, visibleMessages: initial.messages });
    for (let i = 0; i < 3; i++) {
      now += 2_000; const callback = tick; tick = undefined; callback?.();
      for (let j = 0; j < 15; j++) await drainMicrotasks();
    }
    expect(h.requests).toHaveLength(3);
    expect(h.requests.map((r) => r.count)).toEqual([1, 1, 1]);
    expect(applied).toBe(0);
    h.append(); now += 2_000; tick?.();
    for (let j = 0; j < 15; j++) await drainMicrotasks();
    expect(h.requests).toHaveLength(4);
    expect(h.requests.at(-1)!.count).toBe(2);
    expect(applied).toBe(1);
    runtime.dispose();
  });

  test("an unchanged tail returns the exact saved snapshot", async () => {
    const h = history(); const saved = await h.load();
    expect(await h.load(undefined, saved)).toBe(saved);
  });

  test("new replies transfer only the suffix and retain unchanged display objects", async () => {
    const h = history(); const saved = await h.load(); h.requests.length = 0; h.append();
    const refreshed = await h.load(undefined, saved);
    expect(h.requests).toHaveLength(1);
    expect(h.requests[0].count).toBe(2);
    expect(refreshed.messages).toHaveLength(saved.messages.length + 1);
    expect(refreshed.messages[0]).toBe(saved.messages[0]);
    expect(refreshed.messages.at(-1)!.id).toBe(h.messages.at(-1)!.id);
    expect(refreshed.unansweredUserMessage).toBeNull();
  });

  test("a suffix spanning pages follows cursors without rereading history", async () => {
    const h = history(); const saved = await h.load(); h.requests.length = 0; h.append(205);
    const refreshed = await h.load(undefined, saved);
    expect(h.requests).toHaveLength(3);
    expect(h.requests.reduce((n, r) => n + r.count, 0)).toBe(206);
    expect(h.requests[0].anchor).toBe(saved.latestMessageId!);
    expect(h.requests.slice(1).every((r) => r.anchor === undefined && r.cursor)).toBe(true);
    expect(refreshed.messages).toEqual(hydrateMessagesFromApi(h.messages).messages);
  });

  test("a changed anchor is projected even if no later message exists", async () => {
    const h = history(); const saved = await h.load();
    h.messages[h.messages.length - 1] = { ...h.messages.at(-1)!, content: "Updated saved content" };
    const refreshed = await h.load(undefined, saved);
    expect(refreshed).not.toBe(saved);
    expect(refreshed.messages).toEqual(hydrateMessagesFromApi(h.messages).messages);
    expect(refreshed.messages[0]).toBe(saved.messages[0]);
  });

  test("a new suffix updates existing retry actions through canonical projection", async () => {
    const h = history();
    const user = h.messages.at(-1)!;
    user.metadata = {
      agent_runtime_turn: { turn_id: user.id, request_id: "request", status: "abandoned", terminal: true, failure_code: "turn_abandoned", retryable: true },
      recovery: { code: "turn_abandoned", retryable: true },
      retry_last_turn: { request_message_id: user.id, message: user.content },
    };
    const saved = await h.load();
    expect(saved.messages.at(-1)!.actions?.some((action) => action.type === "retry_last_turn")).toBe(true);
    h.append();
    const refreshed = await h.load(undefined, saved);
    expect(refreshed.messages.find((message) => message.id === user.id)!.actions).toBeUndefined();
    expect(refreshed.messages).toEqual(hydrateMessagesFromApi(h.messages).messages);
    expect(refreshed.messages[0]).toBe(saved.messages[0]);
  });

  test("empty histories can discover their first saved message", async () => {
    const h = history(0); const saved = await h.load();
    h.messages.push({ id: crypto.randomUUID(), conversation_id: "conversation", role: "assistant", content: "First reply", created_at: new Date().toISOString() });
    expect((await h.load(undefined, saved)).latestMessageId).toBe(h.messages[0].id);
  });

  test("a missing anchor fails without replacing the readable history", async () => {
    const h = history(); const saved = await h.load(); h.messages.pop();
    await expect(h.load(undefined, saved)).rejects.toThrow("Anchor not found");
    expect(saved.messages).toHaveLength(1_000);
  });
});
