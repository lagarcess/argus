import { afterEach, describe, expect, test } from "bun:test";

import {
  loadCommandPaletteRecentRecall,
  retainRecalledRecentItems,
} from "../lib/command-palette-recent-recall";
import { searchGlobal } from "../lib/argus-api";
import type {
  SearchConversationItem,
  SearchResponse,
} from "../lib/argus-api";

function conversationItem(id: string): SearchConversationItem {
  return {
    type: "conversation",
    id,
    title: `Conversation ${id}`,
    archived: false,
    matched_text: `Preview ${id}`,
    updated_at: "2026-07-30T12:00:00.000Z",
    conversation_id: id,
    match: {
      layer: "conversation",
      fragment: `Conversation ${id}`,
      count: 1,
      message_id: null,
    },
    decision_states: [],
    dossier: {
      decision: null,
      tested: null,
      outcome: null,
      left_off: null,
    },
    actions: [],
  };
}

function historyItem(id: string) {
  return {
    type: "chat" as const,
    id: `history-${id}`,
    conversation_id: id,
    title: `History ${id}`,
    subtitle: `Preview ${id}`,
    pinned: false,
    created_at: "2026-07-30T12:00:00.000Z",
  };
}

describe("command palette Recent dossier recall", () => {
  const originalFetch = globalThis.fetch;
  const originalMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    if (originalMockAuth === undefined) {
      delete process.env.NEXT_PUBLIC_MOCK_AUTH;
    } else {
      process.env.NEXT_PUBLIC_MOCK_AUTH = originalMockAuth;
    }
  });

  test("serializes visible ids as one repeated-query API read", async () => {
    let requestedUrl = "";
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    globalThis.fetch = ((input) => {
      requestedUrl = String(input);
      return Promise.resolve(
        new Response(
          JSON.stringify({
            items: [],
            next_cursor: null,
            ledger_groups: [],
          }),
          {
            status: 200,
            headers: { "Content-Type": "application/json" },
          },
        ),
      );
    }) as typeof fetch;

    await searchGlobal({
      q: "",
      limit: 2,
      conversationIds: ["conversation-a", "conversation-b"],
      includeLedgerGroups: true,
    });

    const requested = new URL(requestedUrl);
    expect(requested.searchParams.get("limit")).toBe("2");
    expect(requested.searchParams.getAll("conversation_id")).toEqual([
      "conversation-a",
      "conversation-b",
    ]);
    expect(requested.searchParams.get("include_ledger_groups")).toBe("true");
  });

  test("hydrates all visible ids in one bounded request and drops unrelated rows", async () => {
    const requests: Array<Record<string, unknown>> = [];
    const response: SearchResponse = {
      items: [
        conversationItem("archived-distractor"),
        conversationItem("recent-b"),
        conversationItem("recent-a"),
      ],
      next_cursor: "must-not-be-followed",
      ledger_groups: [
        { decision_state: "promising", count: 2 },
        { decision_state: "watching", count: 1 },
        { decision_state: "rejected", count: 0 },
        { decision_state: "revisit_later", count: 0 },
      ],
    };

    const result = await loadCommandPaletteRecentRecall({
      recentItems: [
        historyItem("recent-a"),
        historyItem("recent-b"),
        historyItem("recent-a"),
      ],
      fetchRecall: async (params) => {
        requests.push(params);
        return response;
      },
    });

    expect(requests).toEqual([
      {
        q: "",
        limit: 2,
        conversationIds: ["recent-a", "recent-b"],
        includeLedgerGroups: true,
      },
    ]);
    expect(
      result?.items.map((item) =>
        item.type === "conversation" ? item.conversation_id : item.type,
      ),
    ).toEqual(["recent-a", "recent-b"]);
    expect(result?.next_cursor).toBeNull();
    expect(result?.ledger_groups).toEqual(response.ledger_groups);
  });

  test("keeps exact ledger counts when no active chat is visible", async () => {
    const requests: Array<Record<string, unknown>> = [];

    const result = await loadCommandPaletteRecentRecall({
      recentItems: [],
      fetchRecall: async (params) => {
        requests.push(params);
        return {
          items: [conversationItem("archived-ledger-row")],
          next_cursor: "ignored",
          ledger_groups: [
            { decision_state: "promising", count: 3 },
            { decision_state: "watching", count: 0 },
            { decision_state: "rejected", count: 0 },
            { decision_state: "revisit_later", count: 0 },
          ],
        };
      },
    });

    expect(requests).toEqual([
      { q: "", limit: 1, includeLedgerGroups: true },
    ]);
    expect(result).toEqual({
      items: [],
      next_cursor: null,
      ledger_groups: [
        { decision_state: "promising", count: 3 },
        { decision_state: "watching", count: 0 },
        { decision_state: "rejected", count: 0 },
        { decision_state: "revisit_later", count: 0 },
      ],
      recentItems: [],
      recalledConversationIds: [],
    });
  });

  test("reconciles a concurrently deleted Recent without rejecting surviving dossiers", async () => {
    const result = await loadCommandPaletteRecentRecall({
      recentItems: [
        historyItem("recent-a"),
        historyItem("deleted-in-another-tab"),
        historyItem("recent-b"),
      ],
      fetchRecall: async () => ({
        items: [
          conversationItem("recent-b"),
          conversationItem("recent-a"),
        ],
        next_cursor: null,
        ledger_groups: [],
      }),
    });

    expect(result?.recentItems.map((item) => item.conversation_id)).toEqual([
      "recent-a",
      "recent-b",
    ]);
    expect(
      result?.items.map((item) =>
        item.type === "conversation" ? item.conversation_id : item.type,
      ),
    ).toEqual(["recent-a", "recent-b"]);
  });

  test("reconciles a concurrently archived Recent without hiding it from ordinary search", async () => {
    const archived = {
      ...conversationItem("archived-in-another-tab"),
      archived: true,
    };
    const result = await loadCommandPaletteRecentRecall({
      recentItems: [
        historyItem("recent-a"),
        historyItem("archived-in-another-tab"),
        historyItem("recent-b"),
      ],
      fetchRecall: async () => ({
        items: [
          conversationItem("recent-b"),
          archived,
          conversationItem("recent-a"),
        ],
        next_cursor: null,
        ledger_groups: [
          { decision_state: "watching", count: 1 },
        ],
      }),
    });

    expect(result?.recentItems.map((item) => item.conversation_id)).toEqual([
      "recent-a",
      "recent-b",
    ]);
    expect(
      result?.items.map((item) =>
        item.type === "conversation" ? item.conversation_id : item.type,
      ),
    ).toEqual(["recent-a", "recent-b"]);
    expect(result?.recalledConversationIds).toEqual(["recent-a", "recent-b"]);
    expect(result?.ledger_groups).toEqual([
      { decision_state: "watching", count: 1 },
    ]);
  });

  test("decision refresh retains current rows instead of restoring a locally removed row", () => {
    const renamedCurrent = {
      ...historyItem("recent-b"),
      title: "Renamed while refresh was pending",
    };

    expect(
      retainRecalledRecentItems(
        [renamedCurrent],
        ["recent-a", "recent-b"],
      ),
    ).toEqual([renamedCurrent]);
  });

  test("ignores a late response after Recents loses request ownership", async () => {
    let current = true;

    const result = await loadCommandPaletteRecentRecall({
      recentItems: [historyItem("recent-a")],
      fetchRecall: async () => {
        current = false;
        return {
          items: [conversationItem("recent-a")],
          next_cursor: null,
          ledger_groups: [],
        };
      },
      isCurrent: () => current,
    });

    expect(result).toBeNull();
  });

  test("enforces the visible History bound before making a request", async () => {
    const recentItems = Array.from(
      { length: 51 },
      (_, index) => historyItem(`recent-${index}`),
    );
    let called = false;

    expect(
      loadCommandPaletteRecentRecall({
        recentItems,
        fetchRecall: async () => {
          called = true;
          return { items: [], next_cursor: null, ledger_groups: [] };
        },
      }),
    ).rejects.toThrow("at most 50");
    expect(called).toBeFalse();
  });
});
