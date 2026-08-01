import { afterEach, describe, expect, test } from "bun:test";

import {
  getConversationActivity,
  listConversations,
  listHistory,
  patchConversationActivity,
  streamChatMessage,
  type ConversationActivity,
} from "../lib/argus-api";

const activity: ConversationActivity = {
  operation: {
    status: "running",
    kind: "chat_turn",
    updated_at: "2026-08-01T12:00:00Z",
  },
  attention: {
    status: "new_activity",
    cursor: "attention:chat_turn:1",
  },
};

describe("conversation activity API contract", () => {
  const originalFetch = globalThis.fetch;
  const originalMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    if (originalMockAuth === undefined) {
      delete process.env.NEXT_PUBLIC_MOCK_AUTH;
    } else {
      process.env.NEXT_PUBLIC_MOCK_AUTH = originalMockAuth;
    }
  });

  test("keeps optional activity on chat conversation and history rows only", async () => {
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    const responses = [
      {
        items: [
          {
            id: "conversation-1",
            title: "Tesla dip idea",
            title_source: "system_default",
            pinned: false,
            archived: false,
            created_at: "2026-08-01T11:00:00Z",
            updated_at: "2026-08-01T12:00:00Z",
            activity,
          },
        ],
        next_cursor: null,
      },
      {
        items: [
          {
            type: "chat",
            id: "conversation-1",
            title: "Tesla dip idea",
            title_source: "system_default",
            subtitle: "Latest message",
            pinned: false,
            created_at: "2026-08-01T11:00:00Z",
            conversation_id: "conversation-1",
            expires_at: null,
            activity,
          },
          {
            type: "run",
            id: "run-1",
            title: "Tesla dip result",
            subtitle: "Backtest",
            pinned: false,
            created_at: "2026-08-01T11:30:00Z",
            conversation_id: "conversation-1",
            expires_at: null,
          },
        ],
        next_cursor: null,
      },
    ];
    globalThis.fetch = (() =>
      Promise.resolve(
        new Response(JSON.stringify(responses.shift()), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )) as typeof fetch;

    const conversations = await listConversations();
    const history = await listHistory();

    expect(conversations.items[0]?.activity).toEqual(activity);
    expect(history.items[0]).toMatchObject({ type: "chat", activity });
    expect(history.items[1]).toEqual({
      type: "run",
      id: "run-1",
      title: "Tesla dip result",
      subtitle: "Backtest",
      pinned: false,
      created_at: "2026-08-01T11:30:00Z",
      conversation_id: "conversation-1",
      expires_at: null,
    });
  });

  test("uses the owner-scoped activity GET and discriminated PATCH contract", async () => {
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    const requests: Array<{ url: string; init?: RequestInit }> = [];
    globalThis.fetch = ((url, init) => {
      requests.push({ url: String(url), init });
      return Promise.resolve(
        new Response(JSON.stringify(activity), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }) as typeof fetch;

    await getConversationActivity("conversation-1");
    const controller = new AbortController();
    await patchConversationActivity(
      "conversation-1",
      { action: "mark_unread" },
      { signal: controller.signal },
    );
    await patchConversationActivity("conversation-1", {
      action: "mark_read",
      through_attention_cursor: "attention:chat_turn:1",
    });

    expect(requests.map(({ url }) => url)).toEqual([
      "http://127.0.0.1:8000/api/v1/conversations/conversation-1/activity",
      "http://127.0.0.1:8000/api/v1/conversations/conversation-1/activity",
      "http://127.0.0.1:8000/api/v1/conversations/conversation-1/activity",
    ]);
    expect(requests[0]?.init?.method).toBeUndefined();
    expect(requests[1]?.init).toMatchObject({
      method: "PATCH",
      body: JSON.stringify({ action: "mark_unread" }),
    });
    expect(requests[1]?.init?.signal).toBe(controller.signal);
    expect(requests[2]?.init).toMatchObject({
      method: "PATCH",
      body: JSON.stringify({
        action: "mark_read",
        through_attention_cursor: "attention:chat_turn:1",
      }),
    });
  });

  test("preserves caller-owned stream identity and abort signal", async () => {
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    const controller = new AbortController();
    let request: RequestInit | undefined;
    globalThis.fetch = ((_url, init) => {
      request = init;
      return Promise.resolve(
        new Response("data: [DONE]\n\n", {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        }),
      );
    }) as typeof fetch;

    await streamChatMessage(
      "conversation-1",
      "Backtest TSLA",
      "en",
      () => {},
      [],
      { requestId: "caller-request-1", signal: controller.signal },
    );

    expect(new Headers(request?.headers).get("X-Request-Id")).toBe(
      "caller-request-1",
    );
    expect(request?.signal).toBe(controller.signal);
  });
});
