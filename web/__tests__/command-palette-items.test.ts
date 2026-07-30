import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  commandPaletteAssetRollupFromSearch,
  commandPaletteGroupsByLedgerState,
  commandPaletteItemFromSearch,
  commandPalettePreviewFields,
  commandPaletteSelectedPreview,
} from "../lib/command-palette-items";
import type { SearchAssetRollupItem, SearchItem } from "../lib/argus-api";

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
  test("renders an asset rollup with involving language and state counts", () => {
    expect(commandPaletteAssetRollupFromSearch(assetRollup)).toEqual({
      heading: "Your history with this asset",
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
  });

  test("localizes the asset rollup fully in Spanish", () => {
    const display = commandPaletteAssetRollupFromSearch(assetRollup, {
      heading: "Tu historial con este activo",
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
      heading: "Tu historial con este activo",
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
      display.runs,
      ...display.decisions.map((decision) => decision.label),
      display.lastTouched,
    ].join(" ");
    expect(visibleText).not.toMatch(
      /Your history|\bruns?\b|\binvolving\b|Last touched|Revisit later/,
    );
  });

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
    expect(en.command_palette.asset_rollup.heading).toBeTruthy();
    expect(en.command_palette.asset_rollup.runs_involving_other).toContain(
      "involving",
    );
    expect(en.command_palette.asset_rollup.last_touched).toBeTruthy();
    expect(es.command_palette.asset_rollup.heading).toBeTruthy();
    expect(es.command_palette.asset_rollup.runs_involving_other).toContain(
      "incluyen",
    );
    expect(es.command_palette.asset_rollup.last_touched).toBeTruthy();
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
