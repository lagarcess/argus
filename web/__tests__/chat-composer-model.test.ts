import { describe, expect, test } from "bun:test";

import {
  composerMentions,
  deleteTokenBeforeOffset,
  findMentionAtOffset,
  insertTextAtOffset,
  isComposerEmpty,
  rangeForButtonDiscoveryQuery,
  rawComposerText,
  replaceRangeWithToken,
  rangeForDiscoveryItem,
  serializeComposerSegments,
  type ComposerSegment,
} from "../components/chat/composer-model";
import type { DiscoveryItem } from "../lib/argus-api";

const goog = {
  id: "asset:equity:GOOG",
  type: "asset" as const,
  label: "GOOG",
  symbol: "GOOG",
  asset_class: "equity" as const,
  description: "Alphabet Class C",
  insert_text: "GOOG",
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

const btc = {
  id: "asset:crypto:BTC",
  type: "asset" as const,
  label: "BTC · Bitcoin",
  symbol: "BTC",
  asset_class: "crypto" as const,
  description: "Crypto",
  insert_text: "BTC",
  provider: "kraken",
  support_status: "supported" as const,
};

const eurusd = {
  id: "asset:currency_pair:EURUSD",
  type: "asset" as const,
  label: "EURUSD · EUR/USD",
  symbol: "EURUSD",
  asset_class: "currency_pair" as const,
  description: "Currency Pair",
  insert_text: "EURUSD",
  provider: "kraken",
  support_status: "supported" as const,
};

describe("chat composer model", () => {
  test("replaces an @ query with an inline token and serializes natural text", () => {
    const segments: ComposerSegment[] = [{ type: "text", text: "Buy @google when it dips" }];
    const mention = findMentionAtOffset(segments, "Buy @google".length);

    expect(mention).toEqual({ start: 4, end: 11, query: "google" });

    const next = replaceRangeWithToken(segments, mention!, goog);

    expect(next).toEqual([
      { type: "text", text: "Buy " },
      { type: "token", token: goog },
      { type: "text", text: " when it dips" },
    ]);
    expect(serializeComposerSegments(next)).toBe("Buy GOOG when it dips");
    expect(composerMentions(next)).toEqual([
      {
        id: "asset:equity:GOOG",
        type: "asset",
        label: "GOOG",
        symbol: "GOOG",
        asset_class: "equity",
        description: "Alphabet Class C",
        insert_text: "GOOG",
        provider: "alpaca",
        support_status: "supported",
      },
    ]);
  });

  test("replacing a leading @ query does not insert a leading spacer", () => {
    const next = replaceRangeWithToken(
      [{ type: "text", text: "@google" }],
      { start: 0, end: "@google".length, query: "google" },
      goog,
    );

    expect(next).toEqual([
      { type: "token", token: goog },
      { type: "text", text: " " },
    ]);
    expect(serializeComposerSegments(next)).toBe("GOOG");
  });

  test("composer mentions preserve canonical metadata for chat request context", () => {
    const segments: ComposerSegment[] = [
      { type: "text", text: "Buy " },
      { type: "token", token: goog },
      { type: "text", text: " when " },
      { type: "token", token: rsi },
      { type: "text", text: " falls" },
    ];

    expect(composerMentions(segments)).toEqual([
      {
        id: "asset:equity:GOOG",
        type: "asset",
        label: "GOOG",
        symbol: "GOOG",
        asset_class: "equity",
        description: "Alphabet Class C",
        insert_text: "GOOG",
        provider: "alpaca",
        support_status: "supported",
      },
      {
        id: "indicator:rsi",
        type: "indicator",
        label: "RSI",
        symbol: "rsi",
        description: "Relative Strength Index",
        insert_text: "RSI",
        provider: "pandas-ta-classic",
        support_status: "supported",
      },
    ]);
  });

  test("inserting another token does not replace previous inline tokens", () => {
    const withAsset = replaceRangeWithToken(
      [{ type: "text", text: "Buy @google when @relative strength index drops" }],
      { start: 4, end: 11, query: "google" },
      goog,
    );
    const mention = findMentionAtOffset(withAsset, serializeComposerSegments(withAsset).indexOf("@relative") + "@relative strength index".length);
    const next = replaceRangeWithToken(withAsset, mention!, rsi);

    expect(serializeComposerSegments(next)).toBe("Buy GOOG when RSI drops");
    expect(next.filter((segment) => segment.type === "token")).toHaveLength(2);
  });

  test("inserts token at the requested cursor position", () => {
    const inserted = replaceRangeWithToken(
      [{ type: "text", text: "Buy  when RSI drops" }],
      { start: 4, end: 4, query: "" },
      goog,
    );

    expect(serializeComposerSegments(inserted)).toBe("Buy GOOG when RSI drops");
  });

  test("selecting a discovered indicator preserves trailing natural language", () => {
    const segments: ComposerSegment[] = [
      { type: "text", text: "Buy @relative strength index drops below 30" },
    ];
    const range = rangeForDiscoveryItem(segments, "Buy @relative strength index drops below 30".length, rsi);
    const next = replaceRangeWithToken(segments, range!, rsi);

    expect(serializeComposerSegments(next)).toBe("Buy RSI drops below 30");
  });

  test("selecting a crypto pair alias replaces the full multi-word discovery phrase", () => {
    const segments: ComposerSegment[] = [
      { type: "text", text: "Buy @bitcoin usd over the last year" },
    ];
    const range = rangeForDiscoveryItem(segments, "Buy @bitcoin usd".length, btc);
    const next = replaceRangeWithToken(segments, range!, btc);

    expect(serializeComposerSegments(next)).toBe("Buy BTC over the last year");
  });

  test("selecting a currency pair slash alias replaces the full discovery phrase", () => {
    const segments: ComposerSegment[] = [
      { type: "text", text: "Compare @eur/usd against cash" },
    ];
    const range = rangeForDiscoveryItem(segments, "Compare @eur/usd".length, eurusd);
    const next = replaceRangeWithToken(segments, range!, eurusd);

    expect(serializeComposerSegments(next)).toBe("Compare EURUSD against cash");
  });

  test("malformed discovery payloads do not crash range matching", () => {
    const malformed = {
      id: "asset:crypto:ETH",
      type: "asset",
      label: null,
      symbol: null,
      asset_class: "crypto",
      description: null,
      insert_text: undefined,
      provider: "kraken",
      support_status: "supported",
    } as unknown as DiscoveryItem;

    const range = rangeForDiscoveryItem(
      [{ type: "text", text: "Buy @ethereum now" }],
      "Buy @ethereum".length,
      malformed,
    );

    expect(range).toEqual({ start: 4, end: "Buy @ethereum".length, query: "ethereum" });
  });

  test("clicking a result after a partial search offset still replaces the full typed asset word", () => {
    const segments: ComposerSegment[] = [{ type: "text", text: "Buy @google over the last year" }];
    const staleOffset = "Buy @goog".length;
    const range = rangeForDiscoveryItem(segments, staleOffset, goog);
    const next = replaceRangeWithToken(segments, range!, goog);

    expect(serializeComposerSegments(next)).toBe("Buy GOOG over the last year");
  });

  test("button-open discovery replaces only the typed query range", () => {
    const segments: ComposerSegment[] = [{ type: "text", text: "Buy google when it dips" }];
    const range = rangeForButtonDiscoveryQuery(
      rawComposerText(segments),
      "Buy ".length,
      "Buy google".length,
    );
    const next = replaceRangeWithToken(segments, range!, goog);

    expect(range).toEqual({ start: 4, end: 10, query: "google" });
    expect(serializeComposerSegments(next)).toBe("Buy GOOG when it dips");
  });

  test("button-open discovery range closes when the cursor leaves the query", () => {
    expect(rangeForButtonDiscoveryQuery("Buy apple", "Buy apple".length, "Buy ".length)).toBeNull();
    expect(rangeForButtonDiscoveryQuery("Buy apple.", "Buy ".length, "Buy apple.".length)).toBeNull();
    expect(rangeForButtonDiscoveryQuery("Buy apple\nnow", "Buy ".length, "Buy apple\n".length)).toBeNull();
  });

  test("selecting a result after whitespace after @ preserves surrounding text", () => {
    const segments: ComposerSegment[] = [{ type: "text", text: "Buy @ apple now" }];
    const range = rangeForDiscoveryItem(segments, "Buy @ apple".length, goog);
    const next = replaceRangeWithToken(segments, range!, goog);

    expect(serializeComposerSegments(next)).toBe("Buy GOOG now");
  });

  test("deletes the token before the cursor without corrupting surrounding text", () => {
    const segments: ComposerSegment[] = [
      { type: "text", text: "Buy " },
      { type: "token", token: goog },
      { type: "text", text: " when " },
      { type: "token", token: rsi },
      { type: "text", text: " drops" },
    ];

    const next = deleteTokenBeforeOffset(segments, "Buy GOOG when RSI".length);

    expect(serializeComposerSegments(next.segments)).toBe("Buy GOOG when drops");
    expect(next.offset).toBe("Buy GOOG when ".length);
  });

  test("inserts plain text at the cursor and detects empty composers", () => {
    const segments = insertTextAtOffset([{ type: "text", text: "Buy " }], 4, "@");

    expect(serializeComposerSegments(segments)).toBe("Buy @");
    expect(isComposerEmpty([{ type: "text", text: "  \n " }])).toBe(true);
    expect(isComposerEmpty(segments)).toBe(false);
  });
});
