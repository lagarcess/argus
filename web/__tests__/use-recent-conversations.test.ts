import { describe, expect, test } from "bun:test";

import {
  applyRecentHistoryActivityUpdate,
  runHistoryRefreshSafely,
} from "../components/chat/useRecentConversations";

describe("Recents refresh compatibility", () => {
  test("stores response rows and their issuance revision atomically", () => {
    const updated = applyRecentHistoryActivityUpdate(
      { historyItems: [], historyActivityRevision: 0 },
      [
        {
          type: "chat",
          id: "conversation-a",
          title: "Conversation A",
          title_source: "ai_generated",
          subtitle: "Recent work",
          pinned: false,
          created_at: "2026-08-01T12:00:00Z",
          conversation_id: "conversation-a",
        },
      ],
      7,
    );

    expect(updated.historyItems.map((item) => item.id)).toEqual([
      "conversation-a",
    ]);
    expect(updated.historyActivityRevision).toBe(7);
  });

  test("contains a rejected result for legacy fire-and-forget callers", async () => {
    let calls = 0;

    runHistoryRefreshSafely(async () => {
      calls += 1;
      throw new Error("recents unavailable");
    });
    await Promise.resolve();
    await Promise.resolve();

    expect(calls).toBe(1);
  });
});
