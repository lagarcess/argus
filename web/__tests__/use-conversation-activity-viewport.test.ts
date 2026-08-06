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
  listenerCounts: () => Readonly<{ focus: number; blur: number; visibility: number; observer: number }>;
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
    listenerCounts: () => ({
      focus: focusCallback ? 1 : 0,
      blur: blurCallback ? 1 : 0,
      visibility: visibilityCallback ? 1 : 0,
      observer: intersectionCallback ? 1 : 0,
    }),
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

const canonicalProofContext = {
  accountScopeKey: "account-a",
  transcriptGeneration: 1,
  transcriptCanonicalReady: true,
  scrollRestorationComplete: true,
} as const;

describe("conversation activity viewport read proof", () => {
  test("blocks a pre-final cursor until an authorized final earns fresh sentinel proof", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;
    for (const initiallyHydrated of [true, false]) {
      const conversationId = initiallyHydrated ? "conversation-a" : "conversation-new";
      const effects = controlledEffects();
      const readiness = viewport.createConversationActivityTranscriptReadiness();
      if (initiallyHydrated) readiness.stageCanonical(conversationId);
      const readyRef = { current: initiallyHydrated ? conversationId : null };
      const root = transcriptRoot(conversationId);
      const latest = sentinel();
      const reads: string[] = [];
      const inputs = (attentionCursor: string | null) => {
        const snapshot = readiness.snapshot(conversationId);
        return {
          accountScopeKey: "account-a",
          activeRouteConversationId: conversationId,
          activeConversationId: conversationId,
          activeConversationIdRef: conversationId,
          readyTranscriptConversationId: readyRef.current,
          transcriptRoot: root,
          sentinel: latest,
          transcriptGeneration: snapshot.generation,
          transcriptCanonicalReady: snapshot.canonicalReady,
          scrollRestorationComplete: true,
          hydrationComplete: true,
          attentionCursor,
          manualUnreadGuard: false,
          markReadPending: false,
        };
      };
      const owner = viewport.createConversationActivityViewportRuntime({
        inputs: inputs(null),
        effects: effects.effects,
        markRead: async (_conversationId, cursor) => reads.push(cursor),
        resetViewEpoch: () => undefined,
      });
      owner.start();
      const oldObserver = effects.snapshotIntersectionCallback();
      oldObserver?.(true);

      readiness.stageCached(conversationId);
      owner.updateInputs(inputs("cursor-before-final"));
      const requestObserver = effects.snapshotIntersectionCallback();
      oldObserver?.(true);
      requestObserver?.(true);
      await drainMicrotasks();
      expect(reads).toEqual([]);

      expect(viewport.promoteVisibleConversationActivityTerminal({
        conversationId,
        identityAuthorized: true,
        finalPayload: { assistant_response: "Done" },
        requestKind: "chat_turn",
        activeConversationIdRef: { current: conversationId },
        currentViewRef: { current: "chat" },
        readyTranscriptConversationIdRef: readyRef,
        transcriptReadiness: readiness,
      })).toBe(true);
      owner.updateInputs(inputs("cursor-before-final"));
      const finalObserver = effects.snapshotIntersectionCallback();
      expect(finalObserver).not.toBe(requestObserver);
      requestObserver?.(true);
      await drainMicrotasks();
      expect(reads).toEqual([]);

      finalObserver?.(true);
      finalObserver?.(true);
      await drainMicrotasks();
      expect(reads).toEqual(["cursor-before-final"]);
      owner.dispose();
    }
  });

  test("requires fresh intersection after reused-DOM ownership and restoration changes", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;
    const effects = controlledEffects();
    const reads: Array<[string, string]> = [];
    const root = transcriptRoot("conversation-a");
    const latest = sentinel();
    const owner = viewport.createConversationActivityViewportRuntime({
      inputs: {
        accountScopeKey: "account-a",
        activeRouteConversationId: "conversation-a",
        activeConversationId: "conversation-a",
        activeConversationIdRef: "conversation-a",
        readyTranscriptConversationId: "conversation-a",
        transcriptRoot: root,
        sentinel: latest,
        transcriptGeneration: 1,
        transcriptCanonicalReady: true,
        scrollRestorationComplete: true,
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
    const observerA = effects.snapshotIntersectionCallback();
    effects.intersect(true);
    await drainMicrotasks();
    expect(reads).toEqual([["conversation-a", "cursor-a"]]);

    root.dataset.conversationId = "conversation-b";
    owner.updateInputs({
      accountScopeKey: "account-a",
      activeRouteConversationId: "conversation-b",
      activeConversationId: "conversation-b",
      activeConversationIdRef: "conversation-b",
      readyTranscriptConversationId: "conversation-b",
      transcriptRoot: root,
      sentinel: latest,
      transcriptGeneration: 2,
      transcriptCanonicalReady: true,
      scrollRestorationComplete: false,
      hydrationComplete: true,
      attentionCursor: "cursor-b",
      manualUnreadGuard: false,
      markReadPending: false,
    });
    const observerBPending = effects.snapshotIntersectionCallback();
    expect(observerBPending).not.toBe(observerA);
    expect(reads).toHaveLength(1);
    observerA?.(true);
    observerBPending?.(true);
    await drainMicrotasks();
    expect(reads).toHaveLength(1);

    owner.updateInputs({
      accountScopeKey: "account-a",
      activeRouteConversationId: "conversation-b",
      activeConversationId: "conversation-b",
      activeConversationIdRef: "conversation-b",
      readyTranscriptConversationId: "conversation-b",
      transcriptRoot: root,
      sentinel: latest,
      transcriptGeneration: 3,
      transcriptCanonicalReady: true,
      scrollRestorationComplete: true,
      hydrationComplete: true,
      attentionCursor: "cursor-b",
      manualUnreadGuard: false,
      markReadPending: false,
    });
    const observerBReady = effects.snapshotIntersectionCallback();
    expect(observerBReady).not.toBe(observerBPending);
    expect(reads).toHaveLength(1);
    observerBPending?.(true);
    await drainMicrotasks();
    expect(reads).toHaveLength(1);
    observerBReady?.(true);
    await drainMicrotasks();
    expect(reads).toEqual([
      ["conversation-a", "cursor-a"],
      ["conversation-b", "cursor-b"],
    ]);
    owner.dispose();
  });

  test("keeps cached refreshes unread until a canonical generation is restored", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;
    const readiness = viewport.createConversationActivityTranscriptReadiness();

    readiness.stageCached("conversation-a");
    const cached = readiness.snapshot("conversation-a");
    expect(cached.canonicalReady).toBe(false);

    readiness.stageCanonical("conversation-a");
    const canonical = readiness.snapshot("conversation-a");
    expect(canonical.canonicalReady).toBe(true);
    expect(canonical.generation).toBeGreaterThan(cached.generation);
    readiness.clear();
    expect(readiness.snapshot("conversation-a").canonicalReady).toBe(false);
  });

  test("restarts cleanly after StrictMode setup cleanup setup", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;
    const effects = controlledEffects();
    const reads: string[] = [];
    const owner = viewport.createConversationActivityViewportRuntime({
      inputs: {
        accountScopeKey: "account-a",
        activeRouteConversationId: "conversation-a",
        activeConversationId: "conversation-a",
        activeConversationIdRef: "conversation-a",
        readyTranscriptConversationId: "conversation-a",
        transcriptRoot: transcriptRoot("conversation-a"),
        sentinel: sentinel(),
        transcriptGeneration: 1,
        transcriptCanonicalReady: true,
        scrollRestorationComplete: true,
        hydrationComplete: true,
        attentionCursor: "cursor-a",
        manualUnreadGuard: false,
        markReadPending: false,
      },
      effects: effects.effects,
      markRead: async (_conversationId, cursor) => reads.push(cursor),
      resetViewEpoch: () => undefined,
    });

    owner.start();
    expect(effects.listenerCounts()).toEqual({ focus: 1, blur: 1, visibility: 1, observer: 1 });
    owner.dispose();
    expect(effects.listenerCounts()).toEqual({ focus: 0, blur: 0, visibility: 0, observer: 0 });
    owner.start();
    expect(effects.listenerCounts()).toEqual({ focus: 1, blur: 1, visibility: 1, observer: 1 });
    effects.intersect(true);
    await drainMicrotasks();
    expect(reads).toEqual(["cursor-a"]);
    owner.dispose();
  });

  test("rebases dedupe and callbacks when account scope changes", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;
    const effects = controlledEffects();
    const reads: string[] = [];
    let resolveFirst: (() => void) | null = null;
    let resolveSecond: (() => void) | null = null;
    const first = new Promise<void>((resolve) => {
      resolveFirst = resolve;
    });
    const second = new Promise<void>((resolve) => {
      resolveSecond = resolve;
    });
    const root = transcriptRoot("conversation-a");
    const latest = sentinel();
    const base = {
      activeRouteConversationId: "conversation-a",
      activeConversationId: "conversation-a",
      activeConversationIdRef: "conversation-a",
      readyTranscriptConversationId: "conversation-a",
      transcriptRoot: root,
      sentinel: latest,
      transcriptGeneration: 1,
      transcriptCanonicalReady: true,
      scrollRestorationComplete: true,
      hydrationComplete: true,
      attentionCursor: "cursor-a",
      manualUnreadGuard: false,
      markReadPending: false,
    } as const;
    const owner = viewport.createConversationActivityViewportRuntime({
      inputs: { ...base, accountScopeKey: "account-a" },
      effects: effects.effects,
      markRead: async () => {
        reads.push(reads.length === 0 ? "account-a" : "account-b");
        if (reads.length === 1) await first;
        if (reads.length === 2) await second;
      },
      resetViewEpoch: () => undefined,
    });
    owner.start();
    const observerA = effects.snapshotIntersectionCallback();
    observerA?.(true);
    await drainMicrotasks();
    expect(reads).toEqual(["account-a"]);

    owner.updateInputs({ ...base, accountScopeKey: "account-b", transcriptGeneration: 2 });
    const observerB = effects.snapshotIntersectionCallback();
    expect(observerB).not.toBe(observerA);
    observerA?.(true);
    observerB?.(true);
    await drainMicrotasks();
    expect(reads).toEqual(["account-a", "account-b"]);
    resolveFirst?.();
    await drainMicrotasks();
    effects.blur();
    effects.focus();
    await drainMicrotasks();
    expect(reads).toEqual(["account-a", "account-b"]);
    resolveSecond?.();
    await drainMicrotasks();
    owner.dispose();
  });

  test("synchronizes conversation view refs before action-owned work", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;
    const active = { current: "conversation-a" as string | null };
    const view = { current: "settings" };

    viewport.synchronizeConversationViewRefs(active, view, "conversation-b", "chat");

    expect(active.current).toBe("conversation-b");
    expect(view.current).toBe("chat");
  });

  test("wires canonical readiness after anchor restoration and synchronous ref ownership", () => {
    const chat = readFileSync(
      join(import.meta.dir, "../components/chat/ChatInterface.tsx"),
      "utf8",
    );
    const refSync = chat.indexOf(
      "useLayoutEffect(() => {\n    synchronizeConversationViewRefs(",
    );
    const anchorHook = chat.indexOf("useTranscriptTurnAnchor({");
    const viewportHook = chat.indexOf("useConversationActivityViewport({");
    const refreshing = chat.indexOf('state.phase === "refreshing"');
    const canonical = chat.indexOf('state.phase === "ready"');
    const finalAuthorization = chat.indexOf(
      'requestSessions.authorize(requestSession, "final")',
    );
    const visibleTerminalPromotion = chat.indexOf(
      "terminalReadiness.accept(",
      finalAuthorization,
    );

    expect(refSync).toBeGreaterThan(-1);
    expect(anchorHook).toBeGreaterThan(refSync);
    expect(viewportHook).toBeGreaterThan(anchorHook);
    expect(chat.slice(refreshing, canonical)).toContain("stageCached");
    expect(chat.slice(canonical, canonical + 900)).toContain("stageCanonical");
    expect(chat).toContain("accountScopeKey: account?.user.id ?? null");
    expect(chat).toContain("pendingScrollRestoreRef");
    expect(chat).toContain("pendingMessageAnchorRef");
    expect(finalAuthorization).toBeGreaterThan(-1);
    expect(visibleTerminalPromotion).toBeGreaterThan(finalAuthorization);
    expect(chat.slice(finalAuthorization, visibleTerminalPromotion + 600)).toContain(
      "identityAuthorized",
    );
    expect(
      chat.match(/beginConversationActivityTerminalReadiness\(/g),
    ).toHaveLength(3);
    expect(chat.match(/terminalReadiness\.accept\(/g)).toHaveLength(3);
    expect(chat.match(/terminalReadiness\.finish\(/g)?.length ?? 0).toBeGreaterThanOrEqual(6);
    expect(chat).toContain("promoteCanonicalConversationActivityTranscript({");

    const sendActionStart = chat.indexOf("const handleSend");
    const sendAction = chat.slice(
      sendActionStart,
      chat.indexOf("useGuestSendBridge", sendActionStart),
    );
    const cancelAction = chat.slice(
      chat.indexOf("const handleCancelConfirmationAction"),
      chat.indexOf("const handleAction"),
    );
    expect(cancelAction).toContain("synchronizeConversationViewRefs(");
    for (const owner of [sendAction, cancelAction]) {
      expect(owner).toContain("beginConversationActivityTerminalReadiness(");
      expect(owner).toContain("terminalReadiness.accept(");
      expect(owner).toContain("terminalReadiness.finish(");
    }
  });

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
          ...canonicalProofContext,
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

  test("classifies sentinel-proven reads as automatic", async () => {
    const viewport = await loadViewportModule();
    expect(viewport).not.toBeNull();
    if (!viewport) return;
    const effects = controlledEffects();
    const reads: Array<
      [string, string, Readonly<{ notifySuccess?: boolean }> | undefined]
    > = [];
    const owner = viewport.createConversationActivityViewportRuntime({
      inputs: {
        ...canonicalProofContext,
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
      markRead: async (conversationId, cursor, options) => {
        reads.push([conversationId, cursor, options]);
      },
      resetViewEpoch: () => undefined,
    });

    owner.start();
    effects.intersect(true);
    await drainMicrotasks();

    expect(reads).toEqual([
      ["conversation-a", "cursor-a", { notifySuccess: false }],
    ]);
    owner.dispose();
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
      ...canonicalProofContext,
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
          ...canonicalProofContext,
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
      ...canonicalProofContext,
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
      ...canonicalProofContext,
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
      ...canonicalProofContext,
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
        ...canonicalProofContext,
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
      ...canonicalProofContext,
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
