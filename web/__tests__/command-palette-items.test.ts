import { describe, expect, test } from "bun:test";

import {
  commandPaletteAssetRollupFromSearch,
  commandPaletteCanonicalRecallLimit,
  commandPaletteConversationNavigationDisabled,
  commandPaletteDecisionVerb,
  commandPaletteDigitSelectionIndex,
  commandPaletteGroupsByLedgerState,
  commandPaletteItemFromSearch,
  commandPaletteItemsFromHistory,
  commandPaletteItemsInRenderedOrder,
  commandPaletteKeyboardAction,
  commandPaletteOpenMessageId,
  commandPaletteRequestIsCurrent,
  commandPaletteSelectedRenderedPreview,
  commandPaletteSelectedPreview,
} from "../lib/command-palette-items";
import type {
  HistoryItem,
  SearchAssetRollupItem,
  SearchItem,
} from "../lib/argus-api";

const conversationDossier = {
  type: "conversation",
  id: "conversation-1",
  title: "Gold pullback ideas",
  archived: false,
  matched_text: "Hold through earnings.",
  updated_at: "2026-07-29T18:00:00.000Z",
  conversation_id: "conversation-1",
  match: {
    layer: "message",
    fragment: "Hold through earnings.",
    count: 2,
    message_id: "message-7",
  },
  decision_states: ["watching"],
  total_runs: 2,
  decided_runs: 1,
  dossier: {
    run_id: "run-2",
    run_label: "Weekly GLD pullback",
    completed_at: "2026-07-29T17:00:00.000Z",
    result_message_id: "message-7",
    decision: {
      state: "watching",
      note: "Hold through earnings.\nReview risk first.",
      run_label: "Weekly GLD pullback",
    },
    tested: {
      symbols: ["GLD"],
      strategy_family: "buy_and_hold",
      cadence: null,
      timeframe: "1D",
      start_date: "2025-01-01",
      end_date: "2026-07-29",
    },
    outcome: {
      run_label: "Weekly GLD pullback",
      completed_at: "2026-07-29T17:00:00.000Z",
      benchmark_symbol: "SPY",
      quick_take: "GLD held up better than SPY.",
      metrics: [{ name: "total_return_pct", value: 8.4 }],
    },
    actions: [
      {
        type: "retest_run",
        source_run_id: "run-2",
        run_label: "Weekly GLD pullback",
        window_policy: "preserve_start_ending_latest_available",
        contract_version: "argus_retest_run/v2",
      },
      {
        type: "decision",
        evidence_artifact_id: "evidence-2",
        decision_state: null,
        note: null,
        run_label: "Weekly GLD pullback",
      },
    ],
  },
} satisfies SearchItem;

const assetRollup = {
  type: "asset_rollup",
  symbol: "TSLA",
  run_count: 2,
  decision_counts: {
    promising: 1,
    watching: 1,
    rejected: 0,
    revisit_later: 0,
  },
  last_touched_at: "2026-07-29T18:00:00.000Z",
} satisfies SearchAssetRollupItem;

describe("command palette conversation dossier", () => {
  test("keeps all Recents dossiers available after a canonical refresh", () => {
    expect(commandPaletteCanonicalRecallLimit("", false)).toBe(100);
    expect(commandPaletteCanonicalRecallLimit("gold", false)).toBe(30);
    expect(commandPaletteCanonicalRecallLimit("", true)).toBe(100);
  });

  test("keeps Recents rows lightweight while reusing their canonical dossier", () => {
    const recents = [
      {
        type: "chat",
        id: "history-row-1",
        title: "Gold in my long-term mix",
        subtitle: "The last thing I said in this conversation.",
        pinned: false,
        created_at: "2026-07-30T09:00:00.000Z",
        conversation_id: "conversation-1",
      },
      {
        type: "chat",
        id: "history-row-2",
        title: "Unmatched recent conversation",
        subtitle: "This row still has a useful preview.",
        pinned: false,
        created_at: "2026-07-29T09:00:00.000Z",
        conversation_id: "conversation-2",
      },
    ] satisfies HistoryItem[];

    const display = commandPaletteItemsFromHistory(recents, [
      conversationDossier,
    ]);

    expect(display[0]).toMatchObject({
      id: "history-row-1",
      type: "chat",
      conversationId: "conversation-1",
      title: "Gold in my long-term mix",
      snippet: "The last thing I said in this conversation.",
      matchCount: 1,
      matchMessageId: null,
      updatedAt: "2026-07-30T09:00:00.000Z",
      source: "recent",
      decisionState: "watching",
      decisionStates: ["watching"],
      dossier: conversationDossier.dossier,
      totalRuns: 2,
      decidedRuns: 1,
    });
    expect(display[0].snippet).not.toBe(conversationDossier.matched_text);
    expect(display[1]).toMatchObject({
      id: "history-row-2",
      source: "recent",
      dossier: null,
      totalRuns: 0,
      decidedRuns: 0,
    });
  });

  test("renders an asset rollup with involving language and state counts", () => {
    expect(commandPaletteAssetRollupFromSearch(assetRollup)).toEqual({
      heading: "Your Argus history",
      scope: "Across your conversations",
      symbol: "TSLA",
      runs: "2 runs involving TSLA",
      decisions: [
        { state: "promising", count: 1, label: "Promising 1" },
        { state: "watching", count: 1, label: "Watching 1" },
        { state: "rejected", count: 0, label: "Rejected 0" },
        { state: "revisit_later", count: 0, label: "Revisit later 0" },
      ],
      lastTouched: "Last touched 2026-07-29",
    });
    expect("actions" in assetRollup).toBe(false);
  });

  test("localizes the asset rollup fully in Spanish", () => {
    const display = commandPaletteAssetRollupFromSearch(assetRollup, {
      heading: "Tu historial de Argus",
      scope: "En todas tus conversaciones",
      runsInvolving: (count, symbol) =>
        `${count} ejecuciones que incluyen ${symbol}`,
      decisionStateLabel: (state) =>
        ({
          promising: "Prometedoras",
          watching: "En observación",
          rejected: "Rechazadas",
          revisit_later: "Revisar después",
        })[state] ?? state,
      dateLabel: () => "29 jul 2026",
      lastTouched: (date) => `Última actividad: ${date}`,
    });

    expect(display).toEqual({
      heading: "Tu historial de Argus",
      scope: "En todas tus conversaciones",
      symbol: "TSLA",
      runs: "2 ejecuciones que incluyen TSLA",
      decisions: [
        { state: "promising", count: 1, label: "Prometedoras 1" },
        { state: "watching", count: 1, label: "En observación 1" },
        { state: "rejected", count: 0, label: "Rechazadas 0" },
        {
          state: "revisit_later",
          count: 0,
          label: "Revisar después 0",
        },
      ],
      lastTouched: "Última actividad: 29 jul 2026",
    });
    const visibleText = [
      display.heading,
      display.scope,
      display.runs,
      ...display.decisions.map((decision) => decision.label),
      display.lastTouched,
    ].join(" ");
    expect(visibleText).not.toMatch(
      /Your history|\bruns?\b|\binvolving\b|Last touched|Revisit later/,
    );
  });

  test("maps the exact selected-run dossier, counts, and anchored actions", () => {
    const display = commandPaletteItemFromSearch(conversationDossier);

    expect(display).toMatchObject({
      type: "conversation",
      conversationId: "conversation-1",
      snippet: "Hold through earnings.",
      matchCount: 2,
      matchMessageId: "message-7",
      canManageConversation: true,
      dossier: conversationDossier.dossier,
      totalRuns: 2,
      decidedRuns: 1,
    });
    expect(display.dossier?.decision?.note).toBe(
      "Hold through earnings.\nReview risk first.",
    );
  });

  test("keeps ledger grouping and selected-preview fallback behavior", () => {
    const watching = commandPaletteItemFromSearch(conversationDossier);
    const promising = {
      ...watching,
      id: "conversation-2",
      conversationId: "conversation-2",
      decisionState: "promising" as const,
      decisionStates: ["promising" as const],
    };

    expect(
      commandPaletteGroupsByLedgerState(
        [watching, promising],
        [
          { decision_state: "promising", count: 1 },
          { decision_state: "watching", count: 1 },
        ],
      ),
    ).toEqual([
      expect.objectContaining({
        decisionState: "promising",
        count: 1,
        items: [promising],
      }),
      expect.objectContaining({
        decisionState: "watching",
        count: 1,
        items: [watching],
      }),
    ]);
    expect(commandPaletteSelectedPreview(promising, [watching])).toBe(watching);
  });

  test("flattens ledger rows in their rendered order for digit shortcuts", () => {
    const watching = commandPaletteItemFromSearch(conversationDossier);
    const multiState = {
      ...watching,
      decisionStates: ["watching", "rejected"] as const,
    };
    const promising = {
      ...watching,
      id: "conversation-2",
      conversationId: "conversation-2",
      decisionState: "promising" as const,
      decisionStates: ["promising" as const],
    };
    const groups = commandPaletteGroupsByLedgerState(
      [multiState, promising],
      [
        { decision_state: "promising", count: 1 },
        { decision_state: "watching", count: 1 },
        { decision_state: "rejected", count: 1 },
      ],
    );

    expect(commandPaletteItemsInRenderedOrder(groups)).toEqual([
      promising,
      multiState,
      multiState,
    ]);
  });

  test("defaults the preview to the first row visible in a filtered ledger", () => {
    const watching = commandPaletteItemFromSearch(conversationDossier);
    const multiState = {
      ...watching,
      id: "conversation-2",
      conversationId: "conversation-2",
      decisionStates: ["watching", "promising"] as const,
    };
    const promising = {
      ...watching,
      id: "conversation-3",
      conversationId: "conversation-3",
      decisionState: "promising" as const,
      decisionStates: ["promising"] as const,
    };
    const promisingGroup = commandPaletteGroupsByLedgerState(
      [watching, multiState, promising],
      [{ decision_state: "promising", count: 2 }],
    );

    expect(
      commandPaletteSelectedRenderedPreview(null, promisingGroup),
    ).toBe(multiState);
  });

  test("rebinds the selected dossier to the canonical refreshed object", () => {
    const before = commandPaletteItemFromSearch(conversationDossier);
    const after = {
      ...before,
      decisionState: "promising" as const,
      decisionStates: ["promising" as const],
      dossier: {
        ...before.dossier!,
        decision: {
          state: "promising" as const,
          note: "Updated after refetch.",
          run_label: "Weekly GLD pullback",
        },
      },
    };

    expect(commandPaletteSelectedPreview(before, [after])).toBe(after);
  });

  test("keeps keyboard navigation deterministic and editable inputs safe", () => {
    const display = commandPaletteItemFromSearch(conversationDossier);
    expect(commandPaletteOpenMessageId(display, false)).toBe("message-7");
    expect(commandPaletteOpenMessageId(display, true)).toBeNull();
    expect(commandPaletteDigitSelectionIndex("1", 3, false)).toBe(0);
    expect(commandPaletteDigitSelectionIndex("3", 3, false)).toBe(2);
    expect(commandPaletteDigitSelectionIndex("4", 3, false)).toBeNull();
    expect(commandPaletteDigitSelectionIndex("1", 3, true)).toBeNull();
  });

  test("blocks only stream-owning conversation navigation", () => {
    expect(
      commandPaletteConversationNavigationDisabled({
        turnInFlight: true,
        activeConversationId: "conversation-a",
        targetConversationId: "conversation-a",
      }),
    ).toBe(true);
    expect(
      commandPaletteConversationNavigationDisabled({
        turnInFlight: true,
        activeConversationId: "conversation-a",
        targetConversationId: "conversation-b",
      }),
    ).toBe(false);
    expect(
      commandPaletteConversationNavigationDisabled({
        turnInFlight: false,
        activeConversationId: "conversation-a",
        targetConversationId: "conversation-a",
      }),
    ).toBe(false);
    expect(
      commandPaletteConversationNavigationDisabled({
        turnInFlight: true,
        activeConversationId: null,
        targetConversationId: "conversation-a",
      }),
    ).toBe(false);
    expect(
      commandPaletteConversationNavigationDisabled({
        turnInFlight: true,
        activeConversationId: "conversation-a",
        targetConversationId: null,
      }),
    ).toBe(false);
  });

  test("opens from the focused search input but suppresses numeric and editable shortcuts", () => {
    expect(
      commandPaletteKeyboardAction({
        key: "Enter",
        itemCount: 3,
        hasSelection: true,
        targetIsEditable: true,
        targetIsSearchInput: true,
        isEditing: false,
        metaKey: false,
        ctrlKey: false,
      }),
    ).toEqual({ type: "open", openAtLeftOff: false });
    expect(
      commandPaletteKeyboardAction({
        key: "Enter",
        itemCount: 3,
        hasSelection: true,
        targetIsEditable: true,
        targetIsSearchInput: true,
        isEditing: false,
        metaKey: true,
        ctrlKey: false,
      }),
    ).toEqual({ type: "open", openAtLeftOff: true });
    expect(
      commandPaletteKeyboardAction({
        key: "Enter",
        itemCount: 3,
        hasSelection: true,
        targetIsEditable: true,
        targetIsSearchInput: true,
        isEditing: false,
        metaKey: false,
        ctrlKey: true,
      }),
    ).toEqual({ type: "open", openAtLeftOff: true });
    expect(
      commandPaletteKeyboardAction({
        key: "2",
        itemCount: 3,
        hasSelection: true,
        targetIsEditable: true,
        targetIsSearchInput: true,
        isEditing: false,
        metaKey: false,
        ctrlKey: false,
      }),
    ).toEqual({ type: "none" });
    for (const target of ["rename", "note", "other-editable"]) {
      expect(
        commandPaletteKeyboardAction({
          key: "Enter",
          itemCount: 3,
          hasSelection: true,
          targetIsEditable: true,
          targetIsSearchInput: false,
          isEditing: target === "rename",
          metaKey: true,
          ctrlKey: false,
        }),
      ).toEqual({ type: "none" });
    }
  });

  test("rejects deferred More pages after query or decision-chip changes", async () => {
    for (const nextSignature of [
      JSON.stringify(["new query", false, null]),
      JSON.stringify(["", true, "promising"]),
    ]) {
      let currentSignature = JSON.stringify(["old query", false, null]);
      let currentRequestId = 7;
      const capturedSignature = currentSignature;
      const capturedRequestId = currentRequestId;
      let resolvePage: (() => void) | null = null;
      const page = new Promise<void>((resolve) => {
        resolvePage = resolve;
      });
      const applied = page.then(() =>
        commandPaletteRequestIsCurrent({
          capturedSignature,
          capturedRequestId,
          currentSignature,
          currentRequestId,
        }),
      );

      currentSignature = nextSignature;
      currentRequestId += 1;
      resolvePage?.();

      expect(await applied).toBe(false);
    }
  });

  test("releases deferred More loading when a same-query decision refresh takes ownership", async () => {
    const signature = JSON.stringify(["old query", false, null]);
    let currentRequestId = 7;
    let isLoadingMore = true;
    let rows = ["old-row"];
    let cursor: string | null = "old-next";
    const capturedRequestId = currentRequestId;
    let resolvePage: (() => void) | null = null;
    const page = new Promise<void>((resolve) => {
      resolvePage = resolve;
    });
    const stalePage = page.then(() => {
      if (
        commandPaletteRequestIsCurrent({
          capturedSignature: signature,
          capturedRequestId,
          currentSignature: signature,
          currentRequestId,
        })
      ) {
        rows = [...rows, "stale-row"];
        cursor = "stale-next";
        isLoadingMore = false;
      }
    });

    // The same-query decision refresh synchronously releases and invalidates
    // pagination before publishing its canonical rows and cursor.
    isLoadingMore = false;
    currentRequestId += 1;
    rows = ["refreshed-row"];
    cursor = "refreshed-next";
    resolvePage?.();
    await stalePage;

    expect(rows).toEqual(["refreshed-row"]);
    expect(cursor).toBe("refreshed-next");
    expect(isLoadingMore).toBe(false);
  });

  test("blocks a second More request while the same-query decision refresh is pending", async () => {
    const signature = JSON.stringify(["old query", false, null]);
    let currentRequestId = 7;
    let isSavingDecision = true;
    let isLoadingMore = true;
    let rows = ["old-row"];
    let cursor: string | null = "old-next";
    const staleMoreRequestId = currentRequestId;
    let resolveStalePage: (() => void) | null = null;
    const stalePage = new Promise<void>((resolve) => {
      resolveStalePage = resolve;
    }).then(() => {
      if (
        commandPaletteRequestIsCurrent({
          capturedSignature: signature,
          capturedRequestId: staleMoreRequestId,
          currentSignature: signature,
          currentRequestId,
        })
      ) {
        rows = [...rows, "stale-row"];
        cursor = "stale-next";
      }
    });

    isLoadingMore = false;
    const refreshRequestId = ++currentRequestId;
    const tryStartMore = () => {
      if (isSavingDecision || isLoadingMore) return false;
      currentRequestId += 1;
      return true;
    };

    expect(tryStartMore()).toBe(false);
    expect(currentRequestId).toBe(refreshRequestId);
    rows = ["refreshed-row"];
    cursor = "refreshed-next";
    isSavingDecision = false;
    resolveStalePage?.();
    await stalePage;

    expect(rows).toEqual(["refreshed-row"]);
    expect(cursor).toBe("refreshed-next");
  });

  test("names add versus change from the anchored action state", () => {
    const display = commandPaletteItemFromSearch(conversationDossier);
    const decision = display.dossier?.actions.find(
      (action) => action.type === "decision",
    );
    expect(decision?.type).toBe("decision");
    expect(commandPaletteDecisionVerb(decision!)).toBe("add");
    expect(
      commandPaletteDecisionVerb({
        ...decision!,
        decision_state: "watching",
      }),
    ).toBe("change");
  });
});
