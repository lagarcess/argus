import { describe, expect, test } from "bun:test";

import { discoverySectionsForDisplay } from "../components/chat/ChatInput";
import type { DiscoveryItem } from "../lib/argus-api";

const defaults: DiscoveryItem[] = [
  {
    id: "asset:AAPL",
    type: "asset",
    label: "AAPL",
    symbol: "AAPL",
    description: "Apple",
    insert_text: "AAPL",
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
  {
    id: "indicator:atr",
    type: "indicator",
    label: "ATR",
    symbol: "atr",
    description: "Average true range",
    insert_text: "ATR",
    provider: "pandas-ta-classic",
    support_status: "draft_only",
  },
];

describe("chat composer display helpers", () => {
  test("groups empty @ discovery into useful discovery sections", () => {
    const sections = discoverySectionsForDisplay(defaults, "");

    expect(sections.map((section) => section.label)).toEqual([
      "Popular assets",
      "Runnable indicators",
      "Draft-only indicators",
    ]);
    expect(sections[0].items.map((item) => item.id)).toEqual(["asset:AAPL"]);
    expect(sections[1].items.map((item) => item.id)).toEqual(["indicator:rsi"]);
    expect(sections[2].items.map((item) => item.id)).toEqual(["indicator:atr"]);
  });

  test("keeps typed @ searches in one result section", () => {
    const sections = discoverySectionsForDisplay(defaults, "aa");

    expect(sections).toHaveLength(1);
    expect(sections[0].label).toBe("Search results");
    expect(sections[0].items).toHaveLength(3);
  });
});
