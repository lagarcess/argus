import { describe, expect, test } from "bun:test";

import {
  commandPaletteItemFromSearch,
  commandPaletteOpenFallback,
  commandPaletteOpenLabelKey,
  commandPaletteSelectedPreview,
  commandPaletteTypeFallback,
} from "../lib/command-palette-items";
import type { SearchItem } from "../lib/argus-api";

describe("command palette items", () => {
  test("keeps typed evidence recall attached to source conversation provenance", () => {
    const item: SearchItem = {
      type: "evidence",
      id: "artifact-1",
      title: "AAPL MSFT evidence",
      matched_text: "Raw fallback text",
      updated_at: "2026-06-19T00:00:00.000Z",
      conversation_id: "conversation-1",
      lifecycle: "captured",
      preview: {
        digest: "AAPL and MSFT beat SPY in this window.",
        source_run_id: "run-1",
        symbols: ["AAPL", "MSFT"],
      },
    };

    const display = commandPaletteItemFromSearch(item);

    expect(display).toMatchObject({
      type: "evidence",
      conversationId: "conversation-1",
      snippet: "AAPL and MSFT beat SPY in this window.",
      canManageConversation: false,
    });
    expect(commandPaletteOpenLabelKey(display!)).toBe(
      "command_palette.open_source_conversation",
    );
    expect(commandPaletteOpenFallback(display!)).toBe(
      "Open source conversation",
    );
    expect(commandPaletteTypeFallback(display!.type)).toBe("Evidence");
  });

  test("keeps conversation results manageable but does not promote non-chat actions", () => {
    const item: SearchItem = {
      type: "chat",
      id: "conversation-1",
      title: "AAPL chat",
      matched_text: "Discussed AAPL",
      updated_at: "2026-06-19T00:00:00.000Z",
    };

    const display = commandPaletteItemFromSearch(item);

    expect(display?.conversationId).toBe("conversation-1");
    expect(display?.canManageConversation).toBe(true);
    expect(commandPaletteOpenLabelKey(display!)).toBe(
      "command_palette.open_conversation",
    );
  });

  test("formats decision recall from typed state instead of raw enum text", () => {
    const item: SearchItem = {
      type: "decision",
      id: "decision-1",
      title: "AAPL evidence",
      matched_text: "promising raw fallback",
      updated_at: "2026-06-19T00:00:00.000Z",
      conversation_id: "conversation-1",
      lifecycle: "decided",
      preview: {
        digest: "AAPL beat SPY in this window.",
        decision_state: "promising",
        evidence_artifact_id: "artifact-1",
      },
    };

    const display = commandPaletteItemFromSearch(item, {
      decisionStateLabel: (state) =>
        state === "promising" ? "Promising" : state,
    });

    expect(display).toMatchObject({
      type: "decision",
      conversationId: "conversation-1",
      snippet: "Promising · AAPL beat SPY in this window.",
      canManageConversation: false,
    });
    expect(display?.snippet).not.toContain("promising raw fallback");
  });

  test("falls back to the first visible result when preview selection is stale", () => {
    const staleConversation = {
      id: "conversation-1",
      type: "chat",
      conversationId: "conversation-1",
      title: "Old conversation",
      snippet: "Old preview",
      updatedAt: "2026-06-18T00:00:00.000Z",
      source: "recent",
      lifecycle: null,
      preview: null,
      canManageConversation: true,
    } as const;
    const evidenceResult = {
      id: "artifact-1",
      type: "evidence",
      conversationId: "conversation-2",
      title: "AAPL evidence",
      snippet: "AAPL backtest evidence",
      updatedAt: "2026-06-19T00:00:00.000Z",
      source: "search",
      lifecycle: "captured",
      preview: { digest: "AAPL backtest evidence" },
      canManageConversation: false,
    } as const;

    expect(commandPaletteSelectedPreview(staleConversation, [evidenceResult])).toBe(
      evidenceResult,
    );
    expect(commandPaletteSelectedPreview(evidenceResult, [evidenceResult])).toBe(
      evidenceResult,
    );
    expect(commandPaletteSelectedPreview(staleConversation, [])).toBeNull();
  });
});
