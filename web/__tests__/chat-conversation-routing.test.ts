import { describe, expect, test } from "bun:test";

import {
  activeConversationRouteStateFromUrl,
  shouldApplyConversationOwnedUpdate,
  shouldRetireActiveStreamForNavigation,
  shouldStartConversationForVisibleEmptyChat,
  shouldApplyConversationScopedUpdate,
  targetConversationIdForSend,
} from "../lib/chat-conversation-routing";

describe("chat conversation route state", () => {
  test("treats /chat without a conversation id as an empty new-chat intent", () => {
    const routeState = activeConversationRouteStateFromUrl("http://localhost:3000/chat");

    expect(routeState).toEqual({
      conversationId: null,
      isChatRoute: true,
      isNewChatRoute: true,
    });
    expect(
      shouldStartConversationForVisibleEmptyChat({
        routeState,
        visibleMessageCount: 0,
        hasStructuredAction: false,
      }),
    ).toBe(true);
  });

  test("preserves explicit conversation routes and visible existing chat state", () => {
    const explicitRoute = activeConversationRouteStateFromUrl(
      "http://localhost:3000/chat?conversation=existing-1",
    );
    const visibleRouteWithoutQuery = activeConversationRouteStateFromUrl(
      "http://localhost:3000/chat",
    );

    expect(explicitRoute.conversationId).toBe("existing-1");
    expect(explicitRoute.isNewChatRoute).toBe(false);
    expect(
      shouldStartConversationForVisibleEmptyChat({
        routeState: explicitRoute,
        visibleMessageCount: 0,
        hasStructuredAction: false,
      }),
    ).toBe(false);
    expect(
      shouldStartConversationForVisibleEmptyChat({
        routeState: visibleRouteWithoutQuery,
        visibleMessageCount: 2,
        hasStructuredAction: false,
      }),
    ).toBe(false);
    expect(
      shouldStartConversationForVisibleEmptyChat({
        routeState: visibleRouteWithoutQuery,
        visibleMessageCount: 0,
        hasStructuredAction: true,
      }),
    ).toBe(false);
  });

  test("routes structured card actions through their owning conversation", () => {
    expect(
      targetConversationIdForSend({
        routeConversationId: "stale-route",
        stateConversationId: "stale-state",
        action: {
          label: "Change asset",
          type: "change_asset",
          presentation: "confirmation",
          payload: { conversation_id: "card-conversation" },
        },
      }),
    ).toBe("card-conversation");

    expect(
      targetConversationIdForSend({
        routeConversationId: "stale-route",
        stateConversationId: null,
        action: {
          label: "Run backtest",
          type: "run_backtest",
          presentation: "confirmation",
          payload: { conversationId: "camel-card-conversation" },
        },
      }),
    ).toBe("camel-card-conversation");

    expect(
      targetConversationIdForSend({
        routeConversationId: "route-conversation",
        stateConversationId: "state-conversation",
        action: undefined,
      }),
    ).toBe("route-conversation");
  });

  test("blocks async updates when the visible route has moved to a new chat", () => {
    expect(
      shouldApplyConversationScopedUpdate({
        targetConversationId: "old-conversation",
        activeConversationId: "old-conversation",
        currentView: "chat",
        routeState: activeConversationRouteStateFromUrl(
          "http://localhost:3000/chat?conversation=old-conversation",
        ),
      }),
    ).toBe(true);

    expect(
      shouldApplyConversationScopedUpdate({
        targetConversationId: "old-conversation",
        activeConversationId: "old-conversation",
        currentView: "chat",
        routeState: activeConversationRouteStateFromUrl("http://localhost:3000/chat"),
      }),
    ).toBe(false);

    expect(
      shouldApplyConversationScopedUpdate({
        targetConversationId: "old-conversation",
        activeConversationId: "old-conversation",
        currentView: "strategies",
        routeState: activeConversationRouteStateFromUrl(
          "http://localhost:3000/chat?conversation=old-conversation",
        ),
      }),
    ).toBe(false);

    expect(
      shouldApplyConversationScopedUpdate({
        targetConversationId: "old-conversation",
        activeConversationId: "other-conversation",
        currentView: "chat",
        routeState: activeConversationRouteStateFromUrl(
          "http://localhost:3000/chat?conversation=old-conversation",
        ),
      }),
    ).toBe(false);
  });

  test("allows durable same-conversation updates when chat is off-screen", () => {
    expect(
      shouldApplyConversationOwnedUpdate({
        targetConversationId: "active-conversation",
        activeConversationId: "active-conversation",
      }),
    ).toBe(true);

    expect(
      shouldApplyConversationScopedUpdate({
        targetConversationId: "active-conversation",
        activeConversationId: "active-conversation",
        currentView: "strategies",
        routeState: activeConversationRouteStateFromUrl(
          "http://localhost:3000/chat?conversation=active-conversation",
        ),
      }),
    ).toBe(false);

    expect(
      shouldApplyConversationOwnedUpdate({
        targetConversationId: "old-conversation",
        activeConversationId: "new-conversation",
      }),
    ).toBe(false);
  });

  test("retires active streams only when navigation leaves the stream conversation", () => {
    expect(
      shouldRetireActiveStreamForNavigation({
        activeStreamConversationId: "conversation-a",
        nextConversationId: "conversation-b",
      }),
    ).toBe(true);

    expect(
      shouldRetireActiveStreamForNavigation({
        activeStreamConversationId: "conversation-a",
        nextConversationId: null,
      }),
    ).toBe(true);

    expect(
      shouldRetireActiveStreamForNavigation({
        activeStreamConversationId: "conversation-a",
        nextConversationId: "conversation-a",
      }),
    ).toBe(false);

    expect(
      shouldRetireActiveStreamForNavigation({
        activeStreamConversationId: null,
        nextConversationId: "conversation-a",
      }),
    ).toBe(false);
  });
});
