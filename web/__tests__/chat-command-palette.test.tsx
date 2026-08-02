import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";

import {
  commitDossierDecision,
  dossierCountsForHistory,
  dossierPaneKeyboardAction,
  dossierPaneTransition,
  openSelectedDossierConversation,
  selectedDossierForPane,
  type DossierPaneState,
} from "../lib/command-palette-dossier-integration";
import type {
  RunDossier,
  SearchDecisionAction,
  SearchRetestAction,
} from "../lib/run-dossier-contract";
import type { RunDossierHistoryState } from "../lib/run-dossier-history-state";

const decisionAction = (
  evidenceArtifactId: string,
  runLabel: string,
): SearchDecisionAction => ({
  type: "decision",
  evidence_artifact_id: evidenceArtifactId,
  decision_state: "watching",
  note: `${runLabel} note`,
  run_label: runLabel,
});

const retestAction = (
  sourceRunId: string,
  runLabel: string,
): SearchRetestAction => ({
  type: "retest_run",
  source_run_id: sourceRunId,
  run_label: runLabel,
  window_policy: "preserve_start_ending_latest_available",
  contract_version: "argus_retest_run/v2",
});

function dossier(runId: string, metric: number): RunDossier {
  const runLabel = `Run ${runId}`;
  return {
    run_id: runId,
    run_label: runLabel,
    completed_at: "2026-07-31T14:30:00.000Z",
    result_message_id: `message-${runId}`,
    tested: {
      symbols: ["GLD"],
      strategy_family: "buy_and_hold",
      cadence: null,
      timeframe: "1D",
      start_date: "2025-01-01",
      end_date: "2025-12-31",
    },
    outcome: {
      run_label: runLabel,
      completed_at: "2026-07-31T14:30:00.000Z",
      benchmark_symbol: "SPY",
      quick_take: `${runLabel} quick take`,
      metrics: [{ name: "total_return_pct", value: metric }],
    },
    decision: {
      state: "watching",
      note: `${runLabel} note`,
      run_label: runLabel,
    },
    actions: [
      retestAction(runId, runLabel),
      decisionAction(`evidence-${runId}`, runLabel),
    ],
  };
}

const latest = dossier("latest", 8.4);
const historical = dossier("historical", -3.2);

function readyHistory(items: RunDossier[]): RunDossierHistoryState {
  return {
    items,
    nextCursor: null,
    totalRuns: items.length,
    decidedRuns: items.length,
    hasLoadedData: true,
    status: "ready",
  };
}

describe("command palette dossier integration", () => {
  test("history selection anchors every visible action and fact to that exact run", () => {
    const state = dossierPaneTransition(
      { view: "history", historicalRunId: null },
      { type: "select_run", runId: historical.run_id },
    );
    const selected = selectedDossierForPane({
      latestDossier: latest,
      historyItems: [latest, historical],
      state,
    });

    expect(state).toEqual({
      view: "dossier",
      historicalRunId: "historical",
    });
    expect(selected).toBe(historical);
    expect(selected.outcome.metrics).toEqual([
      { name: "total_return_pct", value: -3.2 },
    ]);
    expect(
      selected.actions.find((action) => action.type === "decision"),
    ).toMatchObject({ evidence_artifact_id: "evidence-historical" });
    expect(
      selected.actions.find((action) => action.type === "retest_run"),
    ).toMatchObject({ source_run_id: "historical" });
    expect(selected.result_message_id).toBe("message-historical");
  });

  test("selection, query, and conversation resets restore the latest dossier", () => {
    const anchored: DossierPaneState = {
      view: "dossier",
      historicalRunId: historical.run_id,
    };

    for (const reason of ["selection", "query", "conversation"] as const) {
      const reset = dossierPaneTransition(anchored, {
        type: "reset",
        reason,
      });
      expect(reset).toEqual({ view: "dossier", historicalRunId: null });
      expect(
        selectedDossierForPane({
          latestDossier: latest,
          historyItems: [historical],
          state: reset,
        }),
      ).toBe(latest);
    }

    expect(
      dossierPaneTransition(anchored, { type: "restore_latest" }),
    ).toEqual({ view: "dossier", historicalRunId: null });
  });

  test("a missing historical run falls back to the latest canonical dossier", () => {
    expect(
      selectedDossierForPane({
        latestDossier: latest,
        historyItems: [],
        state: { view: "dossier", historicalRunId: "removed-run" },
      }),
    ).toBe(latest);
  });

  test("only explicit open routes once at the selected result message", () => {
    const routeCalls: Array<[string, string]> = [];
    let closeCalls = 0;
    const opened = openSelectedDossierConversation({
      conversationId: "conversation-7",
      dossier: historical,
      navigationDisabled: false,
      onOpenConversation: (conversationId, messageId) => {
        routeCalls.push([conversationId, messageId]);
      },
      onClose: () => {
        closeCalls += 1;
      },
    });

    expect(opened).toBe(true);
    expect(routeCalls).toEqual([
      ["conversation-7", "message-historical"],
    ]);
    expect(closeCalls).toBe(1);

    const missingAnchorOpened = openSelectedDossierConversation({
      conversationId: "conversation-7",
      dossier: { ...historical, result_message_id: null },
      navigationDisabled: false,
      onOpenConversation: (conversationId, messageId) => {
        routeCalls.push([conversationId, messageId]);
      },
      onClose: () => {
        closeCalls += 1;
      },
    });
    expect(missingAnchorOpened).toBe(false);
    expect(routeCalls).toHaveLength(1);
    expect(closeCalls).toBe(1);
  });

  test("decision save waits for both canonical refreshes and rebinds by run id", async () => {
    const events: string[] = [];
    let releaseSearch!: () => void;
    let releaseHistory!: () => void;
    const searchRefresh = new Promise<void>((resolve) => {
      releaseSearch = resolve;
    });
    const historyRefresh = new Promise<RunDossierHistoryState>((resolve) => {
      releaseHistory = () =>
        resolve(
          readyHistory([
            latest,
            {
              ...historical,
              decision: {
                ...historical.decision!,
                state: "promising",
                note: "Canonical refreshed note",
              },
            },
          ]),
        );
    });

    let settled = false;
    const resultPromise = commitDossierDecision({
      selectedRunId: historical.run_id,
      mutate: async () => {
        events.push("mutation");
      },
      refreshCanonicalSearch: async () => {
        events.push("search:start");
        await searchRefresh;
        events.push("search:end");
      },
      refreshLoadedHistory: async () => {
        events.push("history:start");
        const state = await historyRefresh;
        events.push("history:end");
        return state;
      },
    }).then((value) => {
      settled = true;
      return value;
    });

    await Promise.resolve();
    expect(events).toEqual(["mutation", "search:start", "history:start"]);
    expect(settled).toBe(false);
    releaseSearch();
    await Promise.resolve();
    expect(settled).toBe(false);
    releaseHistory();

    const rebound = await resultPromise;
    expect(rebound?.run_id).toBe("historical");
    expect(rebound?.decision?.note).toBe("Canonical refreshed note");
  });

  test("history refresh error rejects save and preserves the stale selection", async () => {
    const staleHistory: RunDossierHistoryState = {
      ...readyHistory([latest, historical]),
      status: "error",
    };

    await expect(
      commitDossierDecision({
        selectedRunId: historical.run_id,
        mutate: async () => {},
        refreshCanonicalSearch: async () => {},
        refreshLoadedHistory: async () => staleHistory,
      }),
    ).rejects.toThrow("decision history refresh failed");
    expect(staleHistory.items[1]).toBe(historical);
  });

  test("history-owned keyboard state suppresses global navigation", () => {
    for (const state of [
      { view: "history", historicalRunId: null },
      { view: "dossier", historicalRunId: "historical" },
    ] satisfies DossierPaneState[]) {
      expect(
        dossierPaneKeyboardAction({
          key: "Enter",
          metaKey: false,
          ctrlKey: false,
          state,
        }),
      ).toBe("suppress_navigation");
      expect(
        dossierPaneKeyboardAction({
          key: "Enter",
          metaKey: true,
          ctrlKey: false,
          state,
        }),
      ).toBe("suppress_navigation");
      expect(
        dossierPaneKeyboardAction({
          key: "Enter",
          metaKey: false,
          ctrlKey: true,
          state,
        }),
      ).toBe("suppress_navigation");
      expect(
        dossierPaneKeyboardAction({
          key: "Escape",
          metaKey: false,
          ctrlKey: false,
          state,
        }),
      ).toBe("restore_latest");
    }

    for (const key of ["ArrowUp", "ArrowDown"] as const) {
      expect(
        dossierPaneKeyboardAction({
          key,
          metaKey: false,
          ctrlKey: false,
          state: { view: "history", historicalRunId: null },
        }),
      ).toBe("suppress_navigation");
      expect(
        dossierPaneKeyboardAction({
          key,
          metaKey: false,
          ctrlKey: false,
          state: { view: "dossier", historicalRunId: "historical" },
        }),
      ).toBe("delegate");
    }

    expect(
      dossierPaneKeyboardAction({
        key: "Enter",
        metaKey: true,
        ctrlKey: false,
        state: { view: "dossier", historicalRunId: null },
      }),
    ).toBe("delegate");

    expect(
      dossierPaneKeyboardAction({
        key: "Enter",
        metaKey: false,
        ctrlKey: false,
        targetIsDossierControl: true,
        state: { view: "dossier", historicalRunId: "historical" },
      }),
    ).toBe("allow_control");
  });

  test("history-owned digit shortcuts never select a left palette row", () => {
    for (const state of [
      { view: "history", historicalRunId: null },
      { view: "dossier", historicalRunId: "historical" },
    ] satisfies DossierPaneState[]) {
      expect(
        dossierPaneKeyboardAction({
          key: "1",
          metaKey: false,
          ctrlKey: false,
          state,
        }),
      ).toBe("suppress_navigation");
      expect(
        dossierPaneKeyboardAction({
          key: "1",
          metaKey: false,
          ctrlKey: false,
          targetIsDossierControl: true,
          targetIsEditable: true,
          state,
        }),
      ).toBe("allow_control");
    }
  });

  test("history totals require successful canonical history provenance", () => {
    expect(
      dossierCountsForHistory({
        history: { totalRuns: 0, decidedRuns: 0, hasLoadedData: false },
        fallbackTotalRuns: 7,
        fallbackDecidedRuns: 5,
      }),
    ).toEqual({ totalRuns: 7, decidedRuns: 5 });
    expect(
      dossierCountsForHistory({
        history: { totalRuns: 8, decidedRuns: 6, hasLoadedData: true },
        fallbackTotalRuns: 7,
        fallbackDecidedRuns: 5,
      }),
    ).toEqual({ totalRuns: 8, decidedRuns: 6 });
  });

  test("the palette wires lazy history activation instead of opening on render", () => {
    const source = readFileSync(
      new URL(
        "../components/sidebar/ChatCommandPalette.tsx",
        import.meta.url,
      ),
      "utf8",
    );

    expect(source).toContain("useRunDossierHistory");
    expect(source).toContain("<DecisionHistoryView");
    expect(source).toMatch(/onOpenHistory=\{[^}]*history\.open/s);
    expect(source.match(/history\.open\(\)/g)).toHaveLength(1);
    expect(source.indexOf("history.open()")).toBeGreaterThan(
      source.indexOf("onOpenHistory="),
    );
  });

  test("mobile history reserves a scrollable pane while keeping the conversation list", async () => {
    const paletteModule = await import(
      "../components/sidebar/ChatCommandPalette"
    );
    const panelClassName = Reflect.get(
      paletteModule,
      "commandPaletteDossierPanelClassName",
    );

    expect(typeof panelClassName).toBe("function");
    if (typeof panelClassName !== "function") return;

    const historyClasses = String(panelClassName("history")).split(/\s+/);
    expect(historyClasses).toContain("h-[68%]");
    expect(historyClasses).toContain("max-h-[68%]");
    expect(historyClasses).toContain("overflow-hidden");
    expect(historyClasses).toContain("md:h-auto");
    expect(historyClasses).toContain("md:max-h-none");
    expect(historyClasses).toContain("md:overflow-visible");
    expect(historyClasses).not.toContain("max-h-[42%]");

    const dossierClasses = String(panelClassName("dossier")).split(/\s+/);
    expect(dossierClasses).toContain("max-h-[42%]");
    expect(dossierClasses).toContain("overflow-y-auto");
    expect(dossierClasses).not.toContain("h-[68%]");
  });
});
