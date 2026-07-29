import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  commandPaletteGroupsByLedgerState,
  commandPaletteItemFromSearch,
  commandPalettePreviewFields,
  commandPaletteSelectedPreview,
} from "../lib/command-palette-items";
import type { SearchItem } from "../lib/argus-api";

const conversationDossier = {
  type: "conversation",
  id: "conversation-1",
  title: "Gold pullback ideas",
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
  dossier: {
    decision: {
      state: "watching",
      note: "Hold through earnings.\nReview risk first.",
      run_label: "Monthly GLD buys",
    },
    tested: {
      symbols: ["GLD"],
      strategy_families: ["dca"],
      run_count: 2,
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
    left_off: {
      run_label: "Weekly GLD pullback",
      completed_at: "2026-07-29T17:00:00.000Z",
      nudge: "undecided",
    },
  },
} satisfies SearchItem;

describe("command palette conversation dossier", () => {
  test("renders the fixed dossier order and preserves the note newlines", () => {
    const display = commandPaletteItemFromSearch(conversationDossier);

    expect(display).toMatchObject({
      type: "conversation",
      conversationId: "conversation-1",
      snippet: "Hold through earnings.",
      matchCount: 2,
      matchMessageId: "message-7",
      canManageConversation: true,
    });
    expect(commandPalettePreviewFields(display!)).toEqual([
      expect.objectContaining({
        id: "decision",
        value: "Watching · on Monthly GLD buys",
      }),
      expect.objectContaining({
        id: "note",
        value: "Hold through earnings.\nReview risk first.",
      }),
      expect.objectContaining({
        id: "tested",
        value: "GLD · Recurring buys · 2 runs · 2025-01-01–2026-07-29",
      }),
      expect.objectContaining({
        id: "outcome",
        value: "GLD held up better than SPY. · Total return 8.4%",
      }),
      expect.objectContaining({
        id: "left_off",
        value: "Weekly GLD pullback · 2026-07-29 · No decision yet",
      }),
    ]);
  });

  test("ships all dossier labels in English and Spanish", () => {
    const root = process.cwd().endsWith("/web")
      ? process.cwd()
      : join(process.cwd(), "web");
    const en = JSON.parse(
      readFileSync(join(root, "public/locales/en/common.json"), "utf-8"),
    );
    const es = JSON.parse(
      readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
    );

    for (const key of ["decision", "note", "tested", "outcome", "left_off"]) {
      expect(en.command_palette.preview_fields[key]).toBeTruthy();
      expect(es.command_palette.preview_fields[key]).toBeTruthy();
    }
  });

  test("localizes every Spanish dossier value without leaking raw codes", () => {
    const display = commandPaletteItemFromSearch(conversationDossier);
    const fields = commandPalettePreviewFields(display, {
      decisionStateLabel: () => "En observación",
      decisionAttribution: (state, run) => `${state} · en ${run}`,
      runCountLabel: (count) => `${count} ejecuciones`,
      strategyFamilyLabel: () => "Compras periódicas",
      dateLabel: (value) =>
        ({
          "2025-01-01": "1 ene 2025",
          "2026-07-29": "29 jul 2026",
          "2026-07-29T17:00:00.000Z": "29 jul 2026",
        })[value] ?? value,
      nudgeLabel: () => "Sin decisión",
      metricLabel: () => "Retorno total",
    });

    expect(fields.map((field) => field.value)).toEqual([
      "En observación · en Monthly GLD buys",
      "Hold through earnings.\nReview risk first.",
      "GLD · Compras periódicas · 2 ejecuciones · 1 ene 2025–29 jul 2026",
      "GLD held up better than SPY. · Retorno total 8.4%",
      "Weekly GLD pullback · 29 jul 2026 · Sin decisión",
    ]);
    expect(fields.map((field) => field.value).join(" ")).not.toMatch(
      /\bon\b|\bruns?\b|rsi_mean_reversion|undecided|2026-07-29/,
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
      commandPaletteGroupsByLedgerState([watching, promising], [
        { decision_state: "promising", count: 1 },
        { decision_state: "watching", count: 1 },
      ]),
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
});
