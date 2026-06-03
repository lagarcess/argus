import { describe, expect, test } from "bun:test";

import { normalizeAssistantDisplayText } from "../lib/chat-display-text";

describe("chat message display helpers", () => {
  test("normalizes legacy raw data caveats in hydrated assistant prose", () => {
    const content =
      "Keep in mind: 1D bars only. Recurring entries use the first available bar in each cadence window.";

    const normalized = normalizeAssistantDisplayText(content);

    expect(normalized).toContain("Daily data only.");
    expect(normalized).toContain(
      "Recurring entries use the first available daily price in each cadence window.",
    );
    expect(normalized).not.toContain("1D bars only");
    expect(normalized).not.toContain("first available bar");
  });
});
