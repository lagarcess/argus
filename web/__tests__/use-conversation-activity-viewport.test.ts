import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

type ViewportModule = typeof import(
  "../components/chat/useConversationActivityViewport"
);

const loadViewportModule = async (): Promise<ViewportModule | null> =>
  import("../components/chat/useConversationActivityViewport").catch(() => null);

const drainMicrotasks = async (): Promise<void> => {
  await Promise.resolve();
  await Promise.resolve();
};

type ControlledEffects = {
  effects: ViewportModule["ConversationActivityViewportEffectsAdapter"];
  intersect: (intersecting: boolean) => void;
  snapshotIntersectionCallback: () => ((intersecting: boolean) => void) | null;
  focus: () => void;
  blur: () => void;
  setVisible: (visible: boolean) => void;
};

const controlledEffects = (): ControlledEffects => {
  let intersectionCallback: ((intersecting: boolean) => void) | null = null;
  let focusCallback: (() => void) | null = null;
  let blurCallback: (() => void) | null = null;
  let visibilityCallback: (() => void) | null = null;
  let focused = true;
  let visible = true;

  return {
    effects: {
      observeLatestActivity: ({ onIntersectionChange }) => {
        intersectionCallback = onIntersectionChange;
        return () => {
          if (intersectionCallback === onIntersectionChange) {
            intersectionCallback = null;
          }
        };
      },
      subscribeWindowFocus: (callback) => {
        focusCallback = callback;
        return () => {
          if (focusCallback === callback) focusCallback = null;
        };
      },
      subscribeWindowBlur: (callback) => {
        blurCallback = callback;
        return () => {
          if (blurCallback === callback) blurCallback = null;
        };
      },
      subscribeVisibilityChange: (callback) => {
        visibilityCallback = callback;
        return () => {
          if (visibilityCallback === callback) visibilityCallback = null;
        };
      },
      isDocumentVisible: () => visible,
      isWindowFocused: () => focused,
    },
    intersect: (intersecting) => intersectionCallback?.(intersecting),
    snapshotIntersectionCallback: () => intersectionCallback,
    focus: () => {
      focused = true;
      focusCallback?.();
    },
    blur: () => {
      focused = false;
      blurCallback?.();
    },
    setVisible: (nextVisible) => {
      visible = nextVisible;
      visibilityCallback?.();
    },
  };
};

const transcriptRoot = (conversationId: string): HTMLElement =>
  ({ dataset: { conversationId } }) as unknown as HTMLElement;

const sentinel = (): HTMLElement => ({}) as HTMLElement;

describe("conversation activity viewport read proof", () => {
  test("wires one sentinel after rendered activity and before bottom padding", () => {
    const chat = readFileSync(
      join(import.meta.dir, "../components/chat/ChatInterface.tsx"),
      "utf8",
    );
    const status = chat.indexOf("{showStreamStatus && (");
    const sentinel = chat.indexOf('data-testid="latest-activity-sentinel"');
    const padding = chat.indexOf('ref={bottomRef} className="h-28"');

    expect(chat).toContain("useConversationActivityViewport({");
    expect(status).toBeGreaterThan(-1);
    expect(sentinel).toBeGreaterThan(status);
    expect(padding).toBeGreaterThan(sentinel);
    expect(chat.match(/data-testid="latest-activity-sentinel"/g)).toHaveLength(1);
  });

  test("exports the dedicated viewport owner before exercising its contract", async () => {
    expect(await loadViewportModule()).not.toBeNull();
  });

  test("opening alone never marks read and every ownership condition is required", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;

    const mismatches: Array<
      Partial<ViewportModule["ConversationActivityViewportInputs"]>
    > = [
      { activeRouteConversationId: "conversation-b" },
      { activeConversationId: "conversation-b" },
      { activeConversationIdRef: "conversation-b" },
      { readyTranscriptConversationId: "conversation-b" },
      { transcriptRoot: transcriptRoot("conversation-b") },
      { hydrationComplete: false },
      { attentionCursor: null },
      { manualUnreadGuard: true },
      { markReadPending: true },
    ];

    for (const mismatch of mismatches) {
      const effects = controlledEffects();
      const reads: Array<[string, string]> = [];
      const owner = viewport.createConversationActivityViewportRuntime({
        inputs: {
          activeRouteConversationId: "conversation-a",
          activeConversationId: "conversation-a",
          activeConversationIdRef: "conversation-a",
          readyTranscriptConversationId: "conversation-a",
          transcriptRoot: transcriptRoot("conversation-a"),
          sentinel: sentinel(),
          hydrationComplete: true,
          attentionCursor: "cursor-a",
          manualUnreadGuard: false,
          markReadPending: false,
          ...mismatch,
        },
        effects: effects.effects,
        markRead: async (conversationId, cursor) => {
          reads.push([conversationId, cursor]);
        },
        resetViewEpoch: () => undefined,
      });
      owner.start();
      expect(reads).toEqual([]);
      effects.intersect(true);
      await drainMicrotasks();
      expect(reads).toEqual([]);
      owner.dispose();
    }
  });

  test("requires visible focused sentinel proof and acknowledges each cursor once", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;
    const effects = controlledEffects();
    const reads: Array<[string, string]> = [];
    const root = transcriptRoot("conversation-a");
    const latest = sentinel();
    const inputs: ViewportModule["ConversationActivityViewportInputs"] = {
      activeRouteConversationId: "conversation-a",
      activeConversationId: "conversation-a",
      activeConversationIdRef: "conversation-a",
      readyTranscriptConversationId: "conversation-a",
      transcriptRoot: root,
      sentinel: latest,
      hydrationComplete: true,
      attentionCursor: "cursor-a",
      manualUnreadGuard: false,
      markReadPending: false,
    };
    const owner = viewport.createConversationActivityViewportRuntime({
      inputs,
      effects: effects.effects,
      markRead: async (conversationId, cursor) => {
        reads.push([conversationId, cursor]);
      },
      resetViewEpoch: () => undefined,
    });

    owner.start();
    expect(reads).toEqual([]);
    effects.intersect(true);
    effects.intersect(true);
    owner.updateInputs({ ...inputs });
    await drainMicrotasks();
    expect(reads).toEqual([["conversation-a", "cursor-a"]]);

    owner.updateInputs({ ...inputs, attentionCursor: "cursor-b" });
    await drainMicrotasks();
    expect(reads).toEqual([
      ["conversation-a", "cursor-a"],
      ["conversation-a", "cursor-b"],
    ]);
    owner.dispose();
  });

  test("blur and hidden-document transitions block reads until focus or visibility resumes", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;

    for (const blockedBy of ["blur", "hidden"] as const) {
      const effects = controlledEffects();
      const reads: string[] = [];
      const owner = viewport.createConversationActivityViewportRuntime({
        inputs: {
          activeRouteConversationId: "conversation-a",
          activeConversationId: "conversation-a",
          activeConversationIdRef: "conversation-a",
          readyTranscriptConversationId: "conversation-a",
          transcriptRoot: transcriptRoot("conversation-a"),
          sentinel: sentinel(),
          hydrationComplete: true,
          attentionCursor: `cursor-${blockedBy}`,
          manualUnreadGuard: false,
          markReadPending: false,
        },
        effects: effects.effects,
        markRead: async (_conversationId, cursor) => {
          reads.push(cursor);
        },
        resetViewEpoch: () => undefined,
      });
      owner.start();
      if (blockedBy === "blur") effects.blur();
      else effects.setVisible(false);
      effects.intersect(true);
      await drainMicrotasks();
      expect(reads).toEqual([]);

      if (blockedBy === "blur") effects.focus();
      else effects.setVisible(true);
      await drainMicrotasks();
      expect(reads).toEqual([`cursor-${blockedBy}`]);
      owner.dispose();
    }
  });

  test("same-view manual unread stays guarded until deliberate leave and re-entry", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;
    const effects = controlledEffects();
    const reads: string[] = [];
    const resets: string[] = [];
    const rootA = transcriptRoot("conversation-a");
    const latestA = sentinel();
    const activeA: ViewportModule["ConversationActivityViewportInputs"] = {
      activeRouteConversationId: "conversation-a",
      activeConversationId: "conversation-a",
      activeConversationIdRef: "conversation-a",
      readyTranscriptConversationId: "conversation-a",
      transcriptRoot: rootA,
      sentinel: latestA,
      hydrationComplete: true,
      attentionCursor: "cursor-a",
      manualUnreadGuard: true,
      markReadPending: false,
    };
    const owner = viewport.createConversationActivityViewportRuntime({
      inputs: activeA,
      effects: effects.effects,
      markRead: async (_conversationId, cursor) => reads.push(cursor),
      resetViewEpoch: (conversationId) => resets.push(conversationId),
    });
    owner.start();
    effects.intersect(true);
    owner.updateInputs({ ...activeA, manualUnreadGuard: true });
    await drainMicrotasks();
    expect(reads).toEqual([]);
    expect(resets).toEqual([]);

    const rootB = transcriptRoot("conversation-b");
    owner.updateInputs({
      ...activeA,
      activeRouteConversationId: "conversation-b",
      activeConversationId: "conversation-b",
      activeConversationIdRef: "conversation-b",
      readyTranscriptConversationId: "conversation-b",
      transcriptRoot: rootB,
      sentinel: sentinel(),
      attentionCursor: null,
      manualUnreadGuard: false,
    });
    expect(resets).toEqual(["conversation-a"]);

    owner.updateInputs({ ...activeA, manualUnreadGuard: false });
    effects.intersect(true);
    await drainMicrotasks();
    expect(reads).toEqual(["cursor-a"]);
    owner.dispose();
  });

  test("a failed automatic read waits for a later meaningful trigger before retrying", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;
    const effects = controlledEffects();
    let attempts = 0;
    const inputs: ViewportModule["ConversationActivityViewportInputs"] = {
      activeRouteConversationId: "conversation-a",
      activeConversationId: "conversation-a",
      activeConversationIdRef: "conversation-a",
      readyTranscriptConversationId: "conversation-a",
      transcriptRoot: transcriptRoot("conversation-a"),
      sentinel: sentinel(),
      hydrationComplete: true,
      attentionCursor: "cursor-a",
      manualUnreadGuard: false,
      markReadPending: false,
    };
    const owner = viewport.createConversationActivityViewportRuntime({
      inputs,
      effects: effects.effects,
      markRead: async () => {
        attempts += 1;
        if (attempts === 1) throw new Error("offline");
      },
      resetViewEpoch: () => undefined,
    });
    owner.start();
    effects.intersect(true);
    await drainMicrotasks();
    expect(attempts).toBe(1);

    owner.updateInputs({ ...inputs });
    effects.intersect(true);
    await drainMicrotasks();
    expect(attempts).toBe(1);

    effects.blur();
    effects.focus();
    await drainMicrotasks();
    expect(attempts).toBe(2);
    owner.dispose();
  });

  test("a handled transport failure with the same canonical cursor does not render-loop", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;
    const effects = controlledEffects();
    let attempts = 0;
    const inputs: ViewportModule["ConversationActivityViewportInputs"] = {
      activeRouteConversationId: "conversation-a",
      activeConversationId: "conversation-a",
      activeConversationIdRef: "conversation-a",
      readyTranscriptConversationId: "conversation-a",
      transcriptRoot: transcriptRoot("conversation-a"),
      sentinel: sentinel(),
      hydrationComplete: true,
      attentionCursor: "cursor-a",
      manualUnreadGuard: false,
      markReadPending: false,
    };
    const owner = viewport.createConversationActivityViewportRuntime({
      inputs,
      effects: effects.effects,
      // The activity runtime handles transport errors after rolling back, so
      // its public mutation promise resolves while the canonical cursor stays.
      markRead: async () => {
        attempts += 1;
      },
      resetViewEpoch: () => undefined,
    });
    owner.start();
    effects.intersect(true);
    await drainMicrotasks();
    owner.updateInputs({ ...inputs, markReadPending: false });
    owner.updateInputs({ ...inputs, markReadPending: false });
    await drainMicrotasks();
    expect(attempts).toBe(1);

    effects.blur();
    effects.focus();
    await drainMicrotasks();
    expect(attempts).toBe(2);
    owner.dispose();
  });

  test("stale observer callbacks and disposed owners cannot read another conversation", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;
    const effects = controlledEffects();
    const reads: Array<[string, string]> = [];
    const owner = viewport.createConversationActivityViewportRuntime({
      inputs: {
        activeRouteConversationId: "conversation-a",
        activeConversationId: "conversation-a",
        activeConversationIdRef: "conversation-a",
        readyTranscriptConversationId: "conversation-a",
        transcriptRoot: transcriptRoot("conversation-a"),
        sentinel: sentinel(),
        hydrationComplete: true,
        attentionCursor: "cursor-a",
        manualUnreadGuard: false,
        markReadPending: false,
      },
      effects: effects.effects,
      markRead: async (conversationId, cursor) => reads.push([conversationId, cursor]),
      resetViewEpoch: () => undefined,
    });
    owner.start();
    const firstCallback = effects.snapshotIntersectionCallback();
    owner.updateInputs({
      activeRouteConversationId: "conversation-b",
      activeConversationId: "conversation-b",
      activeConversationIdRef: "conversation-b",
      readyTranscriptConversationId: "conversation-b",
      transcriptRoot: transcriptRoot("conversation-b"),
      sentinel: sentinel(),
      hydrationComplete: true,
      attentionCursor: "cursor-b",
      manualUnreadGuard: false,
      markReadPending: false,
    });
    firstCallback?.(true);
    await drainMicrotasks();
    expect(reads).toEqual([]);

    effects.intersect(true);
    await drainMicrotasks();
    expect(reads).toEqual([["conversation-b", "cursor-b"]]);
    owner.dispose();
    effects.intersect(true);
    await drainMicrotasks();
    expect(reads).toEqual([["conversation-b", "cursor-b"]]);
  });
});
