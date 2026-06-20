import { describe, expect, test } from "bun:test";

import {
  commandPaletteItemFromSearch,
  commandPaletteOpenFallback,
  commandPaletteOpenLabelKey,
  commandPalettePreviewFields,
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
      activation: "select_preview",
    });
    expect(display?.preview).not.toHaveProperty("source_run_id");
    expect(commandPalettePreviewFields(display!)).toEqual([
      {
        id: "digest",
        labelKey: "command_palette.preview_fields.digest",
        labelFallback: "Digest",
        value: "AAPL and MSFT beat SPY in this window.",
      },
      {
        id: "assets",
        labelKey: "command_palette.preview_fields.assets",
        labelFallback: "Assets",
        value: "AAPL, MSFT",
      },
    ]);
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
    expect(display?.activation).toBe("open_conversation");
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

  test("builds rich artifact preview fields without raw internals", () => {
    const item: SearchItem = {
      type: "decision",
      id: "decision-1",
      title: "AAPL evidence",
      matched_text: "raw fallback",
      updated_at: "2026-06-19T00:00:00.000Z",
      conversation_id: "conversation-1",
      lifecycle: "decided",
      preview: {
        quick_take: "AAPL beat SPY.",
        digest: "AAPL buy and hold evidence.",
        symbols: ["AAPL"],
        benchmark_symbol: "SPY",
        decision_state: "promising",
        metrics_summary: {
          total_return_pct: 12.34,
          delta_vs_benchmark_pct: 4.56,
          source_run_id: "run-1",
        },
        assumptions: ["No fees", "No slippage"],
        breakdown: {
          summary: "The basket led the benchmark.",
          sections: ["Setup", "Comparison"],
        },
        evidence_artifact_id: "artifact-1",
      },
    };
    const display = commandPaletteItemFromSearch(item, {
      decisionStateLabel: (state) =>
        state === "promising" ? "Promising" : state,
    });

    const fields = commandPalettePreviewFields(display!, {
      decisionStateLabel: (state) =>
        state === "promising" ? "Promising" : state,
    });

    expect(fields.map((field) => field.id)).toEqual([
      "quick_take",
      "digest",
      "assets",
      "benchmark",
      "decision",
      "metrics",
      "assumptions",
      "breakdown",
    ]);
    expect(fields.find((field) => field.id === "decision")?.value).toBe(
      "Promising",
    );
    expect(fields.find((field) => field.id === "metrics")?.value).toBe(
      "Total return 12.3% · Against benchmark 4.6%",
    );
    expect(fields.map((field) => field.value).join(" ")).not.toContain(
      "source_run_id",
    );
    expect(fields.map((field) => field.value).join(" ")).not.toContain(
      "artifact-1",
    );
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
      activation: "open_conversation",
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
      activation: "select_preview",
    } as const;

    expect(commandPaletteSelectedPreview(staleConversation, [evidenceResult])).toBe(
      evidenceResult,
    );
    expect(commandPaletteSelectedPreview(evidenceResult, [evidenceResult])).toBe(
      evidenceResult,
    );
    expect(commandPaletteSelectedPreview(staleConversation, [])).toBeNull();
  });

  test("does not promote unsupported legacy search rows as first-class P1 recall", () => {
    const unsupported: SearchItem = {
      type: "run",
      id: "run-1",
      title: "Internal run",
      matched_text: "Internal run",
      updated_at: "2026-06-19T00:00:00.000Z",
    };

    expect(commandPaletteItemFromSearch(unsupported)).toBeNull();
  });
});
