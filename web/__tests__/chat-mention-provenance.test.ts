import { describe, expect, test } from "bun:test";

import {
  composerTokenAtCaret,
  composerMentions,
  serializeComposerSegments,
  type ComposerSegment,
} from "../components/chat/composer-model";
import { hydrateTextMessageFromApi } from "../lib/chat-message-hydration";

const aapl = {
  id: "asset:equity:AAPL",
  type: "asset" as const,
  label: "AAPL · Apple Inc.",
  symbol: "AAPL",
  asset_class: "equity" as const,
  description: "Apple Inc.",
  insert_text: "AAPL",
  provider: "alpaca",
  support_status: "supported" as const,
};

const rsi = {
  id: "indicator:rsi",
  type: "indicator" as const,
  label: "RSI",
  symbol: "rsi",
  description: "Relative Strength Index",
  insert_text: "RSI",
  provider: "pandas-ta-classic",
  support_status: "supported" as const,
};

describe("chat mention display provenance", () => {
  test("records exact selected spans after normalizing duplicate mentions and whitespace", () => {
    const segments: ComposerSegment[] = [
      { type: "text", text: "  Compare  " },
      { type: "token", token: aapl },
      { type: "text", text: "   to  " },
      { type: "token", token: aapl },
      { type: "text", text: "  when  " },
      { type: "token", token: rsi },
      { type: "text", text: "  \n  falls  " },
    ];

    expect(serializeComposerSegments(segments)).toBe("Compare AAPL to AAPL when RSI\nfalls");
    expect(composerMentions(segments)).toEqual([
      {
        id: "asset:equity:AAPL",
        type: "asset",
        label: "AAPL · Apple Inc.",
        symbol: "AAPL",
        asset_class: "equity",
        description: "Apple Inc.",
        insert_text: "AAPL",
        provider: "alpaca",
        message_range: { start: 8, end: 12 },
      },
      {
        id: "asset:equity:AAPL",
        type: "asset",
        label: "AAPL · Apple Inc.",
        symbol: "AAPL",
        asset_class: "equity",
        description: "Apple Inc.",
        insert_text: "AAPL",
        provider: "alpaca",
        message_range: { start: 16, end: 20 },
      },
      {
        id: "indicator:rsi",
        type: "indicator",
        label: "RSI",
        symbol: "rsi",
        description: "Relative Strength Index",
        insert_text: "RSI",
        provider: "pandas-ta-classic",
        message_range: { start: 26, end: 29 },
      },
    ]);
  });

  test("uses browser UTF-16 positions when an emoji precedes a selected ticker", () => {
    const segments: ComposerSegment[] = [
      { type: "text", text: "🚀 Buy " },
      { type: "token", token: aapl },
    ];

    expect(serializeComposerSegments(segments)).toBe("🚀 Buy AAPL");
    expect(composerMentions(segments)[0]?.message_range).toEqual({
      start: 7,
      end: 11,
    });
  });

  test("hydrates valid persisted mention ranges without changing the user message", () => {
    const content = "Compare AAPL to AAPL when RSI falls";
    const hydrated = hydrateTextMessageFromApi({
      id: "user-message-1",
      conversation_id: "conversation-1",
      role: "user",
      content,
      created_at: "2026-08-09T00:00:00Z",
      metadata: {
        mentions: [
          {
            id: "asset:equity:AAPL",
            type: "asset",
            label: "AAPL · Apple Inc.",
            symbol: "AAPL",
            asset_class: "equity",
            description: "Apple Inc.",
            insert_text: "AAPL",
            provider: "alpaca",
            message_range: { start: 8, end: 12 },
          },
          {
            id: "indicator:rsi",
            type: "indicator",
            label: "RSI",
            symbol: "rsi",
            description: "Relative Strength Index",
            insert_text: "RSI",
            provider: "pandas-ta-classic",
            message_range: { start: 26, end: 29 },
          },
        ],
      },
    });

    expect(hydrated.content).toBe(content);
    expect(hydrated.mentions).toEqual([
      {
        id: "asset:equity:AAPL",
        type: "asset",
        label: "AAPL · Apple Inc.",
        symbol: "AAPL",
        asset_class: "equity",
        description: "Apple Inc.",
        insert_text: "AAPL",
        provider: "alpaca",
        message_range: { start: 8, end: 12 },
      },
      {
        id: "indicator:rsi",
        type: "indicator",
        label: "RSI",
        symbol: "rsi",
        description: "Relative Strength Index",
        insert_text: "RSI",
        provider: "pandas-ta-classic",
        message_range: { start: 26, end: 29 },
      },
    ]);
  });

  test("keeps a legacy mention when malformed display metadata is dropped", () => {
    const hydrated = hydrateTextMessageFromApi({
      id: "user-message-2",
      conversation_id: "conversation-1",
      role: "user",
      content: "Compare AAPL to AAPL",
      created_at: "2026-08-09T00:00:00Z",
      metadata: {
        mentions: [
          {
            id: "asset:equity:AAPL",
            type: "asset",
            label: "AAPL · Apple Inc.",
            symbol: "AAPL",
            asset_class: "equity",
            description: "Apple Inc.",
            insert_text: "AAPL",
            provider: "alpaca",
            message_range: { start: "eight", end: 12 },
          },
          { id: "invalid", type: "not-a-mention" },
        ],
      },
    });

    expect(hydrated.mentions).toEqual([
      {
        id: "asset:equity:AAPL",
        type: "asset",
        label: "AAPL · Apple Inc.",
        symbol: "AAPL",
        asset_class: "equity",
        description: "Apple Inc.",
        insert_text: "AAPL",
        provider: "alpaca",
      },
    ]);
  });

  test("finds the token immediately beside a collapsed composer caret", () => {
    const segments: ComposerSegment[] = [
      { type: "text", text: "Buy " },
      { type: "token", token: aapl },
      { type: "text", text: " when " },
      { type: "token", token: rsi },
      { type: "text", text: " falls" },
    ];

    expect(composerTokenAtCaret(segments, 4)?.token.id).toBe("asset:equity:AAPL");
    expect(composerTokenAtCaret(segments, 8)?.token.id).toBe("asset:equity:AAPL");
    expect(composerTokenAtCaret(segments, 14)?.token.id).toBe("indicator:rsi");
    expect(composerTokenAtCaret(segments, 12)).toBeNull();
  });
});
