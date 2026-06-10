import { describe, expect, test } from "bun:test";

import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  DISCOVERY_SEARCH_LIMIT,
  discoveryEnterAction,
  discoveryOptionDomId,
  discoverySectionsForDisplay,
  mergeDiscoveryItems,
  nextDiscoveryItemId,
  shouldHideMentionButton,
} from "../components/chat/ChatInput";
import type { DiscoveryItem } from "../lib/argus-api";

const root = join(import.meta.dir, "..");

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
  test("keeps empty @ discovery as an invitation to provider search", () => {
    const sections = discoverySectionsForDisplay([], "");

    expect(sections).toEqual([]);
  });

  test("keeps typed @ searches in one result section", () => {
    const sections = discoverySectionsForDisplay(defaults, "aa");

    expect(sections).toHaveLength(1);
    expect(sections[0].label).toBe("Search results");
    expect(sections[0].items.map((item) => item.id)).toEqual([
      "asset:AAPL",
      "indicator:rsi",
    ]);
  });

  test("cycles keyboard focus through visible discovery items", () => {
    expect(discoveryOptionDomId("asset:equity:AAPL")).toBe("chat-discovery-option-asset-equity-AAPL");
    expect(nextDiscoveryItemId(defaults, null, 1)).toBe("asset:AAPL");
    expect(nextDiscoveryItemId(defaults, "asset:AAPL", 1)).toBe("indicator:rsi");
    expect(nextDiscoveryItemId(defaults, "indicator:atr", 1)).toBe("asset:AAPL");
    expect(nextDiscoveryItemId(defaults, "asset:AAPL", -1)).toBe("indicator:atr");
    expect(nextDiscoveryItemId(defaults, "missing", 1)).toBe("asset:AAPL");
    expect(nextDiscoveryItemId([], "asset:AAPL", 1)).toBeNull();
  });

  test("merges provider-backed asset and indicator results without tiny catalog caps", () => {
    const assetResults = Array.from({ length: 14 }, (_, index): DiscoveryItem => ({
      id: `asset:equity:MOCK${index}`,
      type: "asset",
      label: `MOCK${index}`,
      symbol: `MOCK${index}`,
      asset_class: "equity",
      description: "Mock provider asset",
      insert_text: `MOCK${index}`,
      provider: "provider",
      support_status: "supported",
    }));
    const indicatorResults = Array.from({ length: 14 }, (_, index): DiscoveryItem => ({
      id: `indicator:mock-${index}`,
      type: "indicator",
      label: `Mock Indicator ${index}`,
      symbol: `mock_${index}`,
      description: "Mock provider indicator",
      insert_text: `MOCK_${index}`,
      provider: "pandas-ta-classic",
      support_status: "supported",
    }));
    const merged = mergeDiscoveryItems(assetResults, indicatorResults, "mock", DISCOVERY_SEARCH_LIMIT);

    expect(DISCOVERY_SEARCH_LIMIT).toBeGreaterThan(8);
    expect(merged).toHaveLength(DISCOVERY_SEARCH_LIMIT);
  });

  test("chat input exposes the discovery picker as a keyboardable listbox", () => {
    const input = readFileSync(join(root, "components/chat/ChatInput.tsx"), "utf-8");

    expect(input).not.toContain("DEFAULT_DISCOVERY_ITEMS");
    expect(input).toContain('id="chat-discovery-listbox"');
    expect(input).toContain('role="combobox"');
    expect(input).toContain('role="listbox"');
    expect(input).toContain('role="option"');
    expect(input).toContain('aria-autocomplete="list"');
    expect(input).toContain("cursor-text items-center rounded-[32px]");
    expect(input).toContain("isMentionButtonHidden ? \"invisible pointer-events-none\"");
    expect(input).toContain('aria-controls={isDiscoveryOpen ? "chat-discovery-listbox" : undefined}');
    expect(input).toContain("aria-activedescendant={isDiscoveryOpen ? activeDiscoveryOptionId : undefined}");
    expect(input).toContain("aria-selected={item.id === activeDiscoveryItemId}");
    expect(input).toContain('data-active-discovery-option={item.id === activeDiscoveryItemId ? "true" : undefined}');
    expect(input).toContain("onMouseDown={(event) => event.preventDefault()}");
    expect(input).toContain('e.key === "ArrowDown"');
    expect(input).toContain('e.key === "ArrowUp"');
    expect(input).toContain('e.key === "Escape"');
    expect(input).toContain("insertDiscoveryItem(activeDiscoveryItem)");
    expect(input).toContain("discoveryEnterAction({");
    expect(input).toContain('aria-haspopup="listbox"');
    expect(input).toContain("aria-expanded={isMentionButtonHidden ? undefined : isDiscoveryOpen}");
    expect(input).toContain('aria-controls={!isMentionButtonHidden && isDiscoveryOpen ? "chat-discovery-listbox" : undefined}');
  });

  test("chat input distinguishes discovery loading, empty, and unavailable states", () => {
    const input = readFileSync(join(root, "components/chat/ChatInput.tsx"), "utf-8");

    expect(input).toContain("const [discoveryStatus, setDiscoveryStatus]");
    expect(input).toContain("discoveryPanelDisplay({");
    expect(input).toContain("aria-busy={discoveryPanel.busy}");
    expect(input).toContain("Promise.allSettled");
    expect(input).not.toContain("searchDiscovery(\"assets\", query, DISCOVERY_SEARCH_LIMIT).catch(() => ({ items: [] }))");
  });

  test("discovery enter behavior does not trap send when no result is active", () => {
    expect(
      discoveryEnterAction({ hasActiveItem: true, hasComposerContent: true }),
    ).toBe("insert");
    expect(
      discoveryEnterAction({ hasActiveItem: false, hasComposerContent: true }),
    ).toBe("submit");
    expect(
      discoveryEnterAction({ hasActiveItem: false, hasComposerContent: false }),
    ).toBe("close");
  });

  test("hides the mention shortcut when a literal mention marker is visible", () => {
    expect(shouldHideMentionButton(false, "")).toBe(false);
    expect(shouldHideMentionButton(false, "Test AAPL")).toBe(false);
    expect(shouldHideMentionButton(true, "")).toBe(false);
    expect(shouldHideMentionButton(false, "@")).toBe(true);
    expect(shouldHideMentionButton(false, "Buy @apple")).toBe(true);
  });

  test("mention button opens discovery without inserting a literal marker", () => {
    const input = readFileSync(join(root, "components/chat/ChatInput.tsx"), "utf-8");
    const openDiscovery = input.slice(
      input.indexOf("const openDiscovery = () => {"),
      input.indexOf("const insertDiscoveryItem ="),
    );

    expect(openDiscovery).not.toContain('insertTextAtOffset(current, cursor, "@")');
  });

  test("places contenteditable focus before restoring the composer caret", () => {
    const input = readFileSync(join(root, "components/chat/ChatInput.tsx"), "utf-8");
    const caretHelper = input.slice(input.indexOf("function setCaretTextOffset"));

    expect(caretHelper.indexOf("root.focus();")).toBeLessThan(
      caretHelper.indexOf("selection.removeAllRanges();"),
    );
  });

  test("hides empty composer placeholder through focus-within CSS", () => {
    const input = readFileSync(join(root, "components/chat/ChatInput.tsx"), "utf-8");

    expect(input).toContain("group relative flex min-h-[64px]");
    expect(input).toContain("group-focus-within:opacity-0");
    expect(input).toContain("group-focus-within:invisible");
  });
});
