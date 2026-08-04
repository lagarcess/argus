import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");
const chatMessage = readFileSync(
  join(root, "components/chat/ChatMessage.tsx"),
  "utf-8",
);
const sourcesPanel = readFileSync(
  join(root, "components/chat/DiscoverySourcesPanel.tsx"),
  "utf-8",
);

describe("per-row citation chips (§9.5)", () => {
  test("the chip is the first corroborating source's domain, one per row", () => {
    expect(chatMessage).toContain("candidate.source_indices?.[0]");
    expect(chatMessage).toContain("{chipSource.domain}");
  });

  test("cheap rows stay chipless by shape: no indices, no chip", () => {
    // The chip renders only behind the indexed-source guard; there is no
    // other chip path, so a candidate with empty source_indices renders none.
    expect(chatMessage).toContain(
      "chipIndex === undefined\n                      ? undefined\n                      : message.discovery?.sources[chipIndex]",
    );
    expect(chatMessage).toContain("{chipSource ? (");
  });

  test("chip tap opens the drawer anchored, without firing the row action", () => {
    expect(chatMessage).toContain("event.stopPropagation();");
    expect(chatMessage).toContain("setAnchorSourceIndex(chipIndex ?? null);");
    expect(chatMessage).toContain("setShowSources(true);");
    expect(chatMessage).toContain("anchorIndex={anchorSourceIndex}");
  });

  test("the chip stays non-interactive content inside the row button", () => {
    // A tabIndex or role would make it interactive content, which is invalid
    // inside the row <button>; the "N sources ›" button is the keyboard path.
    const chip = chatMessage.slice(
      chatMessage.indexOf("{chipSource ? ("),
      chatMessage.indexOf("{chipSource.domain}"),
    );
    expect(chip).toContain("<span");
    expect(chip).not.toContain("tabIndex");
    expect(chip).not.toContain("role=");
    expect(chip).not.toContain("<button");
  });

  test("the drawer scrolls to and highlights the anchored source", () => {
    expect(sourcesPanel).toContain("anchorIndex?: number | null");
    expect(sourcesPanel).toContain("data-source-index={index}");
    expect(sourcesPanel).toContain('scrollIntoView({ block: "start" })');
    expect(sourcesPanel).toContain("index === anchorIndex");
  });

  test("closing the drawer clears the anchor for the next open", () => {
    expect(chatMessage).toContain("setAnchorSourceIndex(null);");
  });

  test("the grounded footer is the count button alone: chips carry domains", () => {
    // No respelled domain list and no as-of date — the search date is not
    // the articles' date; the drawer shows each source's own date.
    expect(chatMessage).not.toContain("sources_line");
    expect(chatMessage).not.toContain("discoverySourceDomains");
    expect(chatMessage).not.toContain("discoveryFreshnessDate");
    expect(chatMessage).toContain("chat.discovery_results.unsourced_line");
    expect(chatMessage).toContain("chat.discovery_results.sources_panel_open");
  });
});
