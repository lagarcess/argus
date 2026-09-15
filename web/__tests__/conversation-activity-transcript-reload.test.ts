import { describe, expect, test } from "bun:test";
import type { HistoryItem } from "../lib/argus-api";
import { chat, deferred, drainMicrotasks, idleActivity, runtimeHarness, workingActivity } from "./fixtures/conversation-activity-runtime";

describe("remote completion transcript reload", () => {
  for (const status of ["queued", "running", "checking"] as const) {
    for (const source of ["history", "mutation"] as const) {
      test(`${source} reloads the open transcript once after ${status} settles, even if already read`, async () => {
        const harness = runtimeHarness({
          activeConversationId: "conversation-a",
          historyItems: [chat("conversation-a", workingActivity(status))],
          patchActivity: async () => idleActivity(),
        });
        harness.runtime.start();
        await drainMicrotasks();
        const update = () => harness.runtime.updateInputs({
          activeConversationId: "conversation-a", accountScopeKey: "account-a",
          historyItems: [chat("conversation-a", idleActivity())],
        });
        if (source === "mutation") await harness.runtime.markRead("conversation-a", null);
        else update();
        update();
        expect(harness.reloads).toEqual(["conversation-a"]);
        expect(harness.invalidations).toEqual([]);
        harness.runtime.dispose();
      });
    }
  }

  test("ignores a rejected stale idle projection and reloads only when canonical work settles", () => {
    const harness = runtimeHarness({
      activeConversationId: "conversation-a",
      historyItems: [chat("conversation-a", workingActivity("running"))],
      historyActivityRevision: 10,
    });
    const update = (revision: number) => harness.runtime.updateInputs({
      activeConversationId: "conversation-a", accountScopeKey: "account-a",
      historyItems: [chat("conversation-a", idleActivity())], historyActivityRevision: revision,
    });
    update(9);
    expect(harness.reloads).toEqual([]);
    update(11);
    expect(harness.reloads).toEqual(["conversation-a"]);
  });

  for (const finished of [false, true]) {
    test(`leaves the sender's transcript alone when its transport is ${finished ? "finished" : "running"}`, async () => {
      const harness = runtimeHarness({
        activeConversationId: "conversation-a",
        historyItems: [chat("conversation-a", workingActivity("running"))],
      });
      harness.runtime.startRequest("conversation-a", "local-turn", "running", "chat_turn");
      if (finished) harness.runtime.finishTransport("conversation-a", "local-turn");
      harness.runtime.updateInputs({
        activeConversationId: "conversation-a", accountScopeKey: "account-a",
        historyItems: [chat("conversation-a", idleActivity("new_activity", "terminal"))],
      });
      await drainMicrotasks();
      expect(harness.reloads).toEqual([]);
      expect(harness.invalidations).toEqual([]);
    });
  }

  test("navigation invalidates the inactive transcript instead of reopening it", () => {
    const harness = runtimeHarness({
      activeConversationId: "conversation-a",
      historyItems: [chat("conversation-a", workingActivity("running"))],
    });
    harness.runtime.updateActiveConversationId("conversation-b");
    harness.runtime.updateInputs({
      activeConversationId: "conversation-b", accountScopeKey: "account-a",
      historyItems: [chat("conversation-a", idleActivity())],
    });
    expect(harness.reloads).toEqual([]);
    expect(harness.invalidations).toEqual(["conversation-a"]);
  });

  test("does not reload from a previous account's late history response", async () => {
    const response = deferred<readonly HistoryItem[]>();
    const harness = runtimeHarness({
      activeConversationId: "conversation-a",
      historyItems: [chat("conversation-a", workingActivity("running"))],
      refreshHistory: () => response.promise,
    });
    harness.runtime.start();
    harness.runtime.synchronizeAccountScope(null);
    response.resolve([chat("conversation-a", idleActivity())]);
    await drainMicrotasks();
    expect(harness.reloads).toEqual([]);
    harness.runtime.dispose();
  });
});
