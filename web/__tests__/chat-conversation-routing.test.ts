import { describe, expect, test } from "bun:test";

import {
  activeConversationRouteStateFromUrl,
  shouldStartConversationForVisibleEmptyChat,
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
});
