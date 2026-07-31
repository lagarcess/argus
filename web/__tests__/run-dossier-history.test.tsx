import { describe, expect, test } from "bun:test";

import type {
  PaginatedRunDossiers,
  RunDossier,
} from "../lib/run-dossier-contract";
import {
  createRunDossierHistoryController,
  type ListRunDossiers,
} from "../lib/run-dossier-history-state";

function dossier(runId: string): RunDossier {
  return {
    run_id: runId,
    run_label: `Run ${runId}`,
    completed_at: `2026-07-${runId.padStart(2, "0")}T12:00:00.000Z`,
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
      run_label: `Run ${runId}`,
      completed_at: `2026-07-${runId.padStart(2, "0")}T12:00:00.000Z`,
      benchmark_symbol: "SPY",
      quick_take: null,
      metrics: [],
    },
    decision: null,
    actions: [],
  };
}

function page(
  runIds: string[],
  nextCursor: string | null,
  totalRuns: number,
  decidedRuns: number,
): PaginatedRunDossiers {
  return {
    items: runIds.map(dossier),
    next_cursor: nextCursor,
    total_runs: totalRuns,
    decided_runs: decidedRuns,
  };
}

function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (reason?: unknown) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("lazy run dossier history state", () => {
  test("does not read before open and starts with an exact limit of 20", async () => {
    const calls: Array<{
      conversationId: string;
      options: { limit?: number; cursor?: string };
    }> = [];
    const list: ListRunDossiers = async (conversationId, options) => {
      calls.push({ conversationId, options });
      return page(["7", "6", "5", "4", "3"], "cursor-1", 7, 5);
    };
    const history = createRunDossierHistoryController({
      conversationId: "conversation-a",
      listRunDossiers: list,
    });

    expect(calls).toEqual([]);
    expect(history.getState()).toEqual({
      items: [],
      nextCursor: null,
      totalRuns: 0,
      decidedRuns: 0,
      status: "idle",
    });

    await history.open();

    expect(calls).toEqual([
      { conversationId: "conversation-a", options: { limit: 20 } },
    ]);
    expect(history.getState().items.map((item) => item.run_id)).toEqual([
      "7",
      "6",
      "5",
      "4",
      "3",
    ]);
  });

  test("loads the server cursor, appends by run id, and replaces totals", async () => {
    const calls: Array<{ limit?: number; cursor?: string }> = [];
    const list: ListRunDossiers = async (_conversationId, options) => {
      calls.push(options);
      if (options.cursor === "cursor-1") {
        return page(["3", "2", "1"], null, 8, 6);
      }
      return page(["7", "6", "5", "4", "3"], "cursor-1", 7, 5);
    };
    const history = createRunDossierHistoryController({
      conversationId: "conversation-a",
      listRunDossiers: list,
    });

    await history.open();
    await history.loadOlder();

    expect(calls).toEqual([{ limit: 20 }, { limit: 20, cursor: "cursor-1" }]);
    expect(history.getState()).toMatchObject({
      nextCursor: null,
      totalRuns: 8,
      decidedRuns: 6,
      status: "ready",
    });
    expect(history.getState().items.map((item) => item.run_id)).toEqual([
      "7",
      "6",
      "5",
      "4",
      "3",
      "2",
      "1",
    ]);
  });

  test("preserves loaded rows on error and retries the failed cursor", async () => {
    let olderAttempts = 0;
    const list: ListRunDossiers = async (_conversationId, options) => {
      if (!options.cursor) {
        return page(["7", "6"], "cursor-1", 7, 5);
      }
      olderAttempts += 1;
      if (olderAttempts === 1) throw new Error("temporary failure");
      return page(["5", "4"], null, 7, 5);
    };
    const history = createRunDossierHistoryController({
      conversationId: "conversation-a",
      listRunDossiers: list,
    });

    await history.open();
    await history.loadOlder();

    expect(history.getState().status).toBe("error");
    expect(history.getState().items.map((item) => item.run_id)).toEqual(["7", "6"]);
    expect(history.getState().nextCursor).toBe("cursor-1");

    await history.retry();

    expect(olderAttempts).toBe(2);
    expect(history.getState().status).toBe("ready");
    expect(history.getState().items.map((item) => item.run_id)).toEqual([
      "7",
      "6",
      "5",
      "4",
    ]);
  });

  test("refreshes only loaded pages with their stable request cursors", async () => {
    const calls: Array<{ limit?: number; cursor?: string }> = [];
    const list: ListRunDossiers = async (_conversationId, options) => {
      calls.push(options);
      switch (calls.length) {
        case 1:
          return page(["7", "6", "5"], "cursor-1", 7, 5);
        case 2:
          return page(["4", "3"], "cursor-2", 7, 5);
        case 3:
          return page(["8", "7", "6"], "new-cursor-1", 8, 6);
        case 4:
          return page(["5", "4"], "new-cursor-2", 8, 6);
        default:
          throw new Error("refresh disclosed another history page");
      }
    };
    const history = createRunDossierHistoryController({
      conversationId: "conversation-a",
      listRunDossiers: list,
    });

    await history.open();
    await history.loadOlder();
    await history.refresh();

    expect(calls).toEqual([
      { limit: 20 },
      { limit: 20, cursor: "cursor-1" },
      { limit: 20 },
      { limit: 20, cursor: "cursor-1" },
    ]);
    expect(history.getState()).toMatchObject({
      nextCursor: "new-cursor-2",
      totalRuns: 8,
      decidedRuns: 6,
      status: "ready",
    });
    expect(history.getState().items.map((item) => item.run_id)).toEqual([
      "8",
      "7",
      "6",
      "5",
      "4",
    ]);
  });

  test("ignores stale responses after refresh and conversation changes", async () => {
    const oldOpen = deferred<PaginatedRunDossiers>();
    const refreshedOpen = deferred<PaginatedRunDossiers>();
    const conversationBOpen = deferred<PaginatedRunDossiers>();
    let callCount = 0;
    const list: ListRunDossiers = (conversationId) => {
      callCount += 1;
      if (conversationId === "conversation-b") return conversationBOpen.promise;
      return callCount === 1 ? oldOpen.promise : refreshedOpen.promise;
    };
    const history = createRunDossierHistoryController({
      conversationId: "conversation-a",
      listRunDossiers: list,
    });

    const firstOpenPromise = history.open();
    const refreshPromise = history.refresh();
    refreshedOpen.resolve(page(["8"], null, 8, 6));
    await refreshPromise;
    oldOpen.resolve(page(["stale-a"], null, 1, 0));
    await firstOpenPromise;

    expect(history.getState().items.map((item) => item.run_id)).toEqual(["8"]);
    expect(history.getState().totalRuns).toBe(8);

    const staleRefresh = deferred<PaginatedRunDossiers>();
    const staleList: ListRunDossiers = () => staleRefresh.promise;
    const conversationHistory = createRunDossierHistoryController({
      conversationId: "conversation-a",
      listRunDossiers: staleList,
    });
    const stalePromise = conversationHistory.open();
    conversationHistory.setConversationId("conversation-b");
    staleRefresh.resolve(page(["stale-conversation"], null, 1, 0));
    await stalePromise;

    expect(conversationHistory.getState()).toEqual({
      items: [],
      nextCursor: null,
      totalRuns: 0,
      decidedRuns: 0,
      status: "idle",
    });

    history.setConversationId("conversation-b");
    const conversationBPromise = history.open();
    conversationBOpen.resolve(page(["9"], null, 1, 0));
    await conversationBPromise;
    expect(history.getState().items.map((item) => item.run_id)).toEqual(["9"]);
  });
});
