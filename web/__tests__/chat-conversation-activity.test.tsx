import { describe, expect, test } from "bun:test";

import { createConversationActivityRuntime } from "../components/chat/useConversationActivity";
import type { ConversationActivity } from "../lib/argus-api";
import {
  activeConversationRouteStateFromUrl,
  shouldApplyConversationRequestUpdate,
} from "../lib/chat-conversation-routing";

const idleActivity = (): ConversationActivity => ({
  operation: { status: "idle", kind: null, updated_at: null },
  attention: { status: "none", cursor: null },
});

function requestHarness() {
  const invalidations: string[] = [];
  const runtime = createConversationActivityRuntime({
    historyItems: [],
    activeConversationId: "conversation-a",
    accountScopeKey: "account-a",
    refreshHistory: () => undefined,
    invalidateInactiveTranscript: (conversationId) => {
      invalidations.push(conversationId);
    },
    onMutationNotice: () => undefined,
    patchActivity: async () => idleActivity(),
    effects: {
      schedulePoll: () => () => undefined,
      subscribeWindowFocus: () => () => undefined,
      subscribeVisibilityChange: () => () => undefined,
      isDocumentVisible: () => true,
    },
  });
  return { runtime, invalidations };
}

function callbackGate(
  runtime: ReturnType<typeof createConversationActivityRuntime>,
  identity: Readonly<{ conversationId: string; requestId: string }>,
  visibleConversationId: string,
  scope: "request" | "visible",
): boolean {
  return shouldApplyConversationRequestUpdate({
    targetConversationId: identity.conversationId,
    requestId: identity.requestId,
    currentRequestId:
      runtime.getState().byConversationId[identity.conversationId]?.request
        ?.requestId ?? null,
    scope,
    activeConversationId: visibleConversationId,
    currentView: "chat",
    routeState: activeConversationRouteStateFromUrl(
      `http://localhost:3000/chat?conversation=${visibleConversationId}`,
    ),
  });
}

describe("conversation-scoped ordinary-turn activity", () => {
  test("keeps A working in the background while B owns the visible composer", () => {
    const { runtime } = requestHarness();
    runtime.startRequest("conversation-a", "request-a", "running", "chat_turn");
    runtime.updateActiveConversationId("conversation-b");
    runtime.startRequest("conversation-b", "request-b", "running", "chat_turn");

    expect(runtime.isConversationLocked("conversation-a")).toBe(true);
    expect(runtime.isConversationLocked("conversation-b")).toBe(true);
    expect(callbackGate(runtime, {
      conversationId: "conversation-a",
      requestId: "request-a",
    }, "conversation-b", "visible")).toBe(false);
    expect(callbackGate(runtime, {
      conversationId: "conversation-b",
      requestId: "request-b",
    }, "conversation-b", "visible")).toBe(true);
  });

  test("lets A settle and invalidate in the background without unlocking B", () => {
    const { runtime, invalidations } = requestHarness();
    runtime.startRequest("conversation-a", "request-a", "running", "chat_turn");
    runtime.updateActiveConversationId("conversation-b");
    runtime.startRequest("conversation-b", "request-b", "running", "chat_turn");

    expect(callbackGate(runtime, {
      conversationId: "conversation-a",
      requestId: "request-a",
    }, "conversation-b", "request")).toBe(true);
    runtime.settleRequest("conversation-a", "request-a", {
      invalidateInactiveTranscript: true,
    });

    expect(invalidations).toEqual(["conversation-a"]);
    expect(runtime.isConversationLocked("conversation-a")).toBe(false);
    expect(runtime.isConversationLocked("conversation-b")).toBe(true);
    expect(runtime.isRequestCurrent("conversation-b", "request-b")).toBe(true);
  });

  test("drops late A callbacks instead of overwriting B's transcript", () => {
    const { runtime } = requestHarness();
    runtime.startRequest("conversation-a", "request-a", "running", "chat_turn");
    runtime.updateActiveConversationId("conversation-b");
    runtime.startRequest("conversation-b", "request-b", "running", "chat_turn");
    runtime.settleRequest("conversation-a", "request-a");
    const visibleMessages = ["B existing"];

    if (callbackGate(runtime, {
      conversationId: "conversation-a",
      requestId: "request-a",
    }, "conversation-b", "visible")) {
      visibleMessages.push("late A token");
    }
    if (callbackGate(runtime, {
      conversationId: "conversation-b",
      requestId: "request-b",
    }, "conversation-b", "visible")) {
      visibleMessages.push("B token");
    }

    expect(visibleMessages).toEqual(["B existing", "B token"]);
  });

  test("navigation keeps request transports alive and releases only their own records", () => {
    const { runtime } = requestHarness();
    const controllerA = new AbortController();
    const controllerB = new AbortController();
    runtime.startRequest("conversation-a", "request-a", "queued", "chat_turn");
    runtime.registerTransport("conversation-a", "request-a", controllerA);

    runtime.updateActiveConversationId("conversation-b");
    expect(controllerA.signal.aborted).toBe(false);

    runtime.startRequest("conversation-b", "request-b", "queued", "chat_turn");
    runtime.registerTransport("conversation-b", "request-b", controllerB);
    runtime.releaseTransport("conversation-a", "request-a", controllerA);
    runtime.settleRequest("conversation-a", "request-a", {
      invalidateInactiveTranscript: true,
    });

    expect(controllerA.signal.aborted).toBe(false);
    expect(controllerB.signal.aborted).toBe(false);
    expect(runtime.isRequestCurrent("conversation-b", "request-b")).toBe(true);
  });
});
