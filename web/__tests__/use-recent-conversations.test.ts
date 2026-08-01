import { describe, expect, test } from "bun:test";

import { runHistoryRefreshSafely } from "../components/chat/useRecentConversations";

describe("Recents refresh compatibility", () => {
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
