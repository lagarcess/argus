import { describe, expect, test } from "bun:test";

import {
  deleteTokenBeforeOffset,
  findMentionAtOffset,
  insertTextAtOffset,
  isComposerEmpty,
  replaceRangeWithToken,
  rangeForDiscoveryItem,
  serializeComposerSegments,
  type ComposerSegment,
} from "../components/chat/composer-model";

const goog = {
  id: "asset:GOOG",
  type: "asset" as const,
  label: "GOOG",
  symbol: "GOOG",
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

  test("clicking a result after a partial search offset still replaces the full typed asset word", () => {
    const segments: ComposerSegment[] = [{ type: "text", text: "Buy @google over the last year" }];
    const staleOffset = "Buy @goog".length;
    const range = rangeForDiscoveryItem(segments, staleOffset, goog);
    const next = replaceRangeWithToken(segments, range!, goog);

    expect(serializeComposerSegments(next)).toBe("Buy GOOG over the last year");
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
