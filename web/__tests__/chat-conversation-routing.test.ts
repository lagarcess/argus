import { describe, expect, test } from "bun:test";

import {
  activeConversationRouteStateFromUrl,
  isCurrentAnchoredConversationRequest,
  shouldApplyConversationRequestUpdate,
  shouldApplyConversationOwnedUpdate,
  shouldStartConversationForVisibleEmptyChat,
  shouldApplyConversationScopedUpdate,
  targetConversationIdForSend,
} from "../lib/chat-conversation-routing";
import * as conversationRouting from "../lib/chat-conversation-routing";

describe("chat conversation route state", () => {
  test("treats /chat without a conversation id as an empty new-chat intent", () => {
    const routeState = activeConversationRouteStateFromUrl("http://localhost:3000/chat");

    expect(routeState).toEqual({
      conversationId: null,
      messageId: null,
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
    expect(explicitRoute.messageId).toBeNull();
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

  test("preserves an owned transcript match anchor on an explicit chat route", () => {
    const routeState = activeConversationRouteStateFromUrl(
      "http://localhost:3000/chat?conversation=existing-1&message=message-7",
    );

    expect(routeState).toEqual({
      conversationId: "existing-1",
      messageId: "message-7",
      isChatRoute: true,
      isNewChatRoute: false,
    });
  });

  test("rejects stale anchor A after same-conversation ordinary or anchor B navigation", () => {
    expect(
      isCurrentAnchoredConversationRequest({
        activeConversationId: "conversation-1",
        targetConversationId: "conversation-1",
        routeState: activeConversationRouteStateFromUrl(
          "http://localhost:3000/chat?conversation=conversation-1&message=message-a",
        ),
        requestedMessageId: "message-a",
      }),
    ).toBe(true);
    expect(
      isCurrentAnchoredConversationRequest({
        activeConversationId: "conversation-1",
        targetConversationId: "conversation-1",
        routeState: activeConversationRouteStateFromUrl(
          "http://localhost:3000/chat?conversation=conversation-1",
        ),
        requestedMessageId: "message-a",
      }),
    ).toBe(false);
    expect(
      isCurrentAnchoredConversationRequest({
        activeConversationId: "conversation-1",
        targetConversationId: "conversation-1",
        routeState: activeConversationRouteStateFromUrl(
          "http://localhost:3000/chat?conversation=conversation-1&message=message-b",
        ),
        requestedMessageId: "message-a",
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
        currentView: "settings",
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
        currentView: "settings",
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

  test("exposes request-scoped routing instead of navigation retirement", () => {
    const requestRouting = conversationRouting as typeof conversationRouting & {
      shouldApplyConversationRequestUpdate?: unknown;
    };

    expect(typeof requestRouting.shouldApplyConversationRequestUpdate).toBe(
      "function",
    );
  });

  test("lets a current background request settle without writing into the visible chat", () => {
    const routeState = activeConversationRouteStateFromUrl(
      "http://localhost:3000/chat?conversation=conversation-b",
    );

    expect(
      shouldApplyConversationRequestUpdate({
        targetConversationId: "conversation-a",
        requestId: "request-a",
        currentRequestId: "request-a",
        scope: "request",
        activeConversationId: "conversation-b",
        currentView: "chat",
        routeState,
      }),
    ).toBe(true);
    expect(
      shouldApplyConversationRequestUpdate({
        targetConversationId: "conversation-a",
        requestId: "request-a",
        currentRequestId: "request-a",
        scope: "visible",
        activeConversationId: "conversation-b",
        currentView: "chat",
        routeState,
      }),
    ).toBe(false);
  });

  test("rejects every callback from a superseded request identity", () => {
    const routeState = activeConversationRouteStateFromUrl(
      "http://localhost:3000/chat?conversation=conversation-a",
    );

    for (const scope of ["request", "visible"] as const) {
      expect(
        shouldApplyConversationRequestUpdate({
          targetConversationId: "conversation-a",
          requestId: "request-old",
          currentRequestId: "request-new",
          scope,
          activeConversationId: "conversation-a",
          currentView: "chat",
          routeState,
        }),
      ).toBe(false);
    }
  });
});
