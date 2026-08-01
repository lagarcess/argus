import { describe, expect, test } from "bun:test";

import { createConversationActivityRuntime } from "../components/chat/useConversationActivity";
import type { ConversationActivity, HistoryItem } from "../lib/argus-api";
import {
  createChatRequestSessionController,
  type ChatRequestCallbackKind,
  visibleRequestStatus,
} from "../lib/chat-request-session";
import { activeConversationRouteStateFromUrl } from "../lib/chat-conversation-routing";

const idleActivity = (): ConversationActivity => ({
  operation: { status: "idle", kind: null, updated_at: null },
  attention: { status: "none", cursor: null },
});

const chat = (conversationId: string): HistoryItem => ({
  type: "chat",
  id: conversationId,
  conversation_id: conversationId,
  title: conversationId,
  title_source: "ai_generated",
  subtitle: "Recent work",
  pinned: false,
  created_at: "2026-08-01T12:00:00Z",
  activity: idleActivity(),
});

function requestHarness() {
  let visibleConversationId = "conversation-a";
  let currentView = "chat";
  let routeUrl = "http://localhost:3000/chat?conversation=conversation-a";
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
  const requestIds = ["request-a", "request-b", "request-c"];
  const controller = createChatRequestSessionController({
    activity: runtime,
    accountScopeKey: "account-a",
    routeContext: {
      activeConversationId: visibleConversationId,
      currentView,
      routeState: activeConversationRouteStateFromUrl(routeUrl),
    },
    createRequestId: () => requestIds.shift() ?? "request-extra",
  });
  return {
    runtime,
    controller,
    invalidations,
    showConversation(conversationId: string) {
      visibleConversationId = conversationId;
      currentView = "chat";
      routeUrl = `http://localhost:3000/chat?conversation=${conversationId}`;
      runtime.updateActiveConversationId(conversationId);
      controller.updateRouteContext({
        activeConversationId: visibleConversationId,
        currentView,
        routeState: activeConversationRouteStateFromUrl(routeUrl),
      });
    },
    showSettings() {
      currentView = "settings";
      routeUrl = "http://localhost:3000/settings";
      controller.updateRouteContext({
        activeConversationId: visibleConversationId,
        currentView,
        routeState: activeConversationRouteStateFromUrl(routeUrl),
      });
    },
  };
}

describe("production chat request-session ownership", () => {
  test("hides stale transport status as soon as canonical activity unlocks", () => {
    expect(visibleRequestStatus("Checking what completed…", true)).toBe(
      "Checking what completed…",
    );
    expect(visibleRequestStatus("Checking what completed…", false)).toBeNull();
    expect(visibleRequestStatus(null, true)).toBeNull();
  });

  test("routes every callback kind by request and visible conversation ownership", () => {
    const harness = requestHarness();
    const requestA = harness.controller.begin("conversation-a", "chat_turn");
    expect(requestA).not.toBeNull();
    harness.showConversation("conversation-b");
    const requestB = harness.controller.begin("conversation-b", "chat_turn");
    expect(requestB).not.toBeNull();

    const backgroundOwned: ChatRequestCallbackKind[] = [
      "stage",
      "title",
      "done",
      "error",
      "catch",
      "run_replay",
      "ambiguity",
    ];
    const visibleOnly: ChatRequestCallbackKind[] = [
      "token",
      "final",
      "save_cleanup",
      "cancel",
    ];
    for (const kind of backgroundOwned) {
      expect(
        harness.controller.authorize(requestA!, kind, "conversation-a"),
      ).toBe(true);
    }
    for (const kind of visibleOnly) {
      expect(
        harness.controller.authorize(requestA!, kind, "conversation-a"),
      ).toBe(false);
      expect(
        harness.controller.authorize(requestB!, kind, "conversation-b"),
      ).toBe(true);
    }
    expect(
      harness.controller.authorize(requestA!, "title", "conversation-b"),
    ).toBe(false);
    expect(harness.controller.canWriteVisible(requestA!)).toBe(false);
    expect(harness.controller.canWriteVisible(requestB!)).toBe(true);

    harness.showSettings();
    expect(harness.controller.authorize(requestB!, "token")).toBe(false);
    expect(harness.controller.authorize(requestB!, "done")).toBe(true);
  });

  test("transport completion stays checking and is idempotent until canonical idle", () => {
    const harness = requestHarness();
    const requestA = harness.controller.begin("conversation-a", "backtest_job");
    expect(requestA).not.toBeNull();
    harness.showConversation("conversation-b");
    const requestB = harness.controller.begin("conversation-b", "chat_turn");
    expect(requestB).not.toBeNull();

    expect(harness.controller.finishTransport(requestA!)).toBe(true);
    expect(harness.controller.finishTransport(requestA!)).toBe(false);
    expect(harness.runtime.isRequestCurrent("conversation-a", "request-a")).toBe(
      true,
    );
    expect(harness.runtime.getState().byConversationId["conversation-a"]?.request?.status)
      .toBe("checking");
    expect(harness.runtime.isRequestCurrent("conversation-b", "request-b")).toBe(
      true,
    );

    const issuedRevision = requestA!.identity.issuedRevision;
    harness.runtime.updateInputs({
      historyItems: [chat("conversation-a")],
      historyActivityRevision: issuedRevision + 1,
      activeConversationId: "conversation-b",
      accountScopeKey: "account-a",
    });

    expect(harness.controller.authorize(requestA!, "done")).toBe(false);
    expect(harness.runtime.isRequestCurrent("conversation-b", "request-b")).toBe(
      true,
    );
    expect(harness.invalidations).toEqual(["conversation-a"]);
  });

  test("404 transfer retires only the nonexistent owner and keeps the same request id", () => {
    const harness = requestHarness();
    const requestA = harness.controller.begin("conversation-a", "chat_turn");
    expect(requestA).not.toBeNull();

    const transferred = harness.controller.transfer(
      requestA!,
      "conversation-created",
    );

    expect(transferred?.identity.requestId).toBe("request-a");
    expect(transferred?.controller).toBe(requestA?.controller);
    expect(harness.controller.authorize(requestA!, "catch")).toBe(false);
    expect(harness.controller.authorize(transferred!, "catch")).toBe(true);
    expect(harness.runtime.isConversationLocked("conversation-a")).toBe(false);
    expect(harness.runtime.isConversationLocked("conversation-created")).toBe(true);
  });

  test("an old save cleanup cannot mutate a newer same-conversation request", () => {
    const harness = requestHarness();
    const oldSave = harness.controller.begin("conversation-a", "chat_turn");
    expect(oldSave).not.toBeNull();
    const issuedRevision = oldSave!.identity.issuedRevision;
    harness.runtime.updateInputs({
      historyItems: [chat("conversation-a")],
      historyActivityRevision: issuedRevision + 1,
      activeConversationId: "conversation-a",
      accountScopeKey: "account-a",
    });
    const newSave = harness.controller.begin("conversation-a", "chat_turn");

    expect(newSave).not.toBeNull();
    expect(harness.controller.authorize(oldSave!, "save_cleanup")).toBe(false);
    expect(harness.controller.authorize(newSave!, "save_cleanup")).toBe(true);
  });

  test("synchronous account reset aborts A and B and rejects every late callback", () => {
    const harness = requestHarness();
    const requestA = harness.controller.begin("conversation-a", "chat_turn");
    harness.showConversation("conversation-b");
    const requestB = harness.controller.begin("conversation-b", "backtest_job");
    expect(requestA).not.toBeNull();
    expect(requestB).not.toBeNull();

    expect(harness.controller.synchronizeAccountScope(null)).toBe(true);

    expect(requestA?.controller.signal.aborted).toBe(true);
    expect(requestB?.controller.signal.aborted).toBe(true);
    for (const kind of [
      "stage",
      "token",
      "title",
      "final",
      "done",
      "error",
      "catch",
      "save_cleanup",
      "cancel",
      "run_replay",
      "ambiguity",
    ] as const) {
      expect(
        harness.controller.authorize(requestA!, kind, "conversation-a"),
      ).toBe(false);
      expect(
        harness.controller.authorize(requestB!, kind, "conversation-b"),
      ).toBe(false);
    }
    expect(harness.runtime.getState().byConversationId).toEqual({});
  });
});
