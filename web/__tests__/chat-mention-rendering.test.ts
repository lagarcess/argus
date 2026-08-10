import { describe, expect, test } from "bun:test";

import { entityTokenClassName } from "../components/chat/entity-token";
import { messageMentionPieces } from "../components/chat/mention-rendering";
import type { ChatMention } from "../components/chat/types";

const aapl: ChatMention = {
  id: "asset:equity:AAPL",
  type: "asset",
  label: "AAPL · Apple Inc.",
  symbol: "AAPL",
  asset_class: "equity",
  description: "Apple Inc.",
  insert_text: "AAPL",
  provider: "alpaca",
};

const rsi: ChatMention = {
  id: "indicator:rsi",
  type: "indicator",
  label: "RSI",
  symbol: "rsi",
  description: "Relative Strength Index",
  insert_text: "RSI",
  provider: "pandas-ta-classic",
};

describe("persisted mention rendering", () => {
  test("uses exact ranges so a repeated ticker only badges the selected occurrence", () => {
    const pieces = messageMentionPieces("Compare AAPL to AAPL when RSI falls", [
      { ...aapl, message_range: { start: 8, end: 12 } },
      { ...rsi, message_range: { start: 26, end: 29 } },
    ]);

    expect(pieces).toEqual([
      { kind: "text", text: "Compare " },
      {
        kind: "mention",
        mention: { ...aapl, message_range: { start: 8, end: 12 } },
        text: "AAPL",
      },
      { kind: "text", text: " to AAPL when " },
      {
        kind: "mention",
        mention: { ...rsi, message_range: { start: 26, end: 29 } },
        text: "RSI",
      },
      { kind: "text", text: " falls" },
    ]);
  });

  test("falls back safely to legacy matching when any stored range is absent or stale", () => {
    expect(messageMentionPieces("Compare AAPL to AAPL", [aapl])).toEqual([
      { kind: "text", text: "Compare " },
      {
        kind: "mention",
        mention: aapl,
        text: "AAPL",
      },
      { kind: "text", text: " to AAPL" },
    ]);

    expect(
      messageMentionPieces("Compare AAPL to AAPL", [
        { ...aapl, message_range: { start: 8, end: 12 } },
        { ...rsi, message_range: { start: 16, end: 19 } },
      ]),
    ).toEqual([
      { kind: "text", text: "Compare " },
      {
        kind: "mention",
        mention: { ...aapl, message_range: { start: 8, end: 12 } },
        text: "AAPL",
      },
      { kind: "text", text: " to AAPL" },
    ]);
  });

  test("keeps semantic color and focus treatment inside the shared entity token", () => {
    const assetTranscript = entityTokenClassName("asset", "transcript");
    const indicatorTranscript = entityTokenClassName("indicator", "transcript");

    expect(assetTranscript).toContain("border-[#c9c9cd]");
    expect(assetTranscript).toContain("text-[#505a63]");
    expect(indicatorTranscript).toContain("border-[#494fdf]/35");
    expect(indicatorTranscript).toContain("text-[#494fdf]");
    expect(entityTokenClassName("asset", "composer", true)).toContain("ring-1");
    expect(entityTokenClassName("asset", "transcript", true)).not.toContain("ring-1");
    expect(entityTokenClassName("asset", "card")).toContain("border-[#c9c9cd]");
  });
});
