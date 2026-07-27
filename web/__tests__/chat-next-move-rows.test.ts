import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

const row = readFileSync(join(root, "components/chat/NextMoveRow.tsx"), "utf-8");
const message = readFileSync(
  join(root, "components/chat/ChatMessage.tsx"),
  "utf-8",
);
const panel = readFileSync(
  join(root, "components/chat/DiscoverySourcesPanel.tsx"),
  "utf-8",
);
const chat = readFileSync(
  join(root, "components/chat/ChatInterface.tsx"),
  "utf-8",
);
const en = JSON.parse(
  readFileSync(join(root, "public/locales/en/common.json"), "utf-8"),
);
const es = JSON.parse(
  readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
);

describe("next-move row anatomy", () => {
  test("rest state is borderless and the wash only appears on hover or press", () => {
    expect(row).toContain("border-transparent");
    expect(row).toContain("group-hover/next-move:border-black/12");
    expect(row).toContain("group-active/next-move:border-black/12");
    expect(row).toContain("group-hover/next-move:bg-black/5");
    expect(row).toContain("group-active/next-move:bg-black/5");
  });

  test("hit area spans the column and stays tappable regardless of the visible box", () => {
    expect(row).toContain("min-h-11");
    expect(row).toContain("w-full");
    expect(row).toContain("text-start");
  });

  test("the affordance glyph is decorative and mirrors for RTL locales", () => {
    expect(row).toContain('aria-hidden="true"');
    expect(row).toContain("rtl:-scale-x-100");
  });

  test("text wraps instead of clipping, including scripts without spaces", () => {
    expect(row).toContain("[overflow-wrap:anywhere]");
    expect(row).not.toContain("truncate");
    expect(row).not.toContain("whitespace-nowrap");
  });
});

describe("discovery candidates render as rows", () => {
  test("reason text is visible rather than hidden in a hover tooltip", () => {
    expect(message).toContain("<NextMoveDetail>{candidate.reason_text}</NextMoveDetail>");
    expect(message).not.toContain("title={candidate.reason_text");
  });

  test("separators are their own nodes so locales can restyle them", () => {
    expect(message).toContain("<NextMoveSeparator>·</NextMoveSeparator>");
    expect(message).toContain("<NextMoveSeparator>—</NextMoveSeparator>");
  });

  test("the tap payload is unchanged by the presentation swap", () => {
    expect(message).toContain('type: "select_discovery_candidate"');
    expect(message).toContain('labelKey: "chat.discovery_results.test_candidate"');
    expect(message).toContain("symbol: candidate.symbol");
    expect(message).toContain("name: candidate.name");
  });
});

describe("next moves answer the newest question only", () => {
  test("rows require the latest message and the conversation-level gate", () => {
    const gate = message.slice(
      message.indexOf("const showNextMoveRows ="),
      message.indexOf("const displayContent"),
    );
    expect(gate).toContain("Boolean(isLatest)");
    expect(gate).toContain("nextMovesEnabled");
  });

  test("card-scoped actions never become conversational rows", () => {
    expect(message).toContain("!actionHasCardScopedOwnership(action)");
  });

  test("the floating composer strip is gone and its gating survives", () => {
    expect(chat).not.toContain("const composerActions =");
    expect(chat).toContain("const nextMovesEnabled =");
    expect(chat).toContain("!hasActiveArtifactActionSet(messages)");
  });

  test("older footer options no longer reappear on hover", () => {
    // The hover reveal survives for the feedback controls only. Option rows are
    // gated on isLatest instead, because touch devices never hover.
    expect(message).toContain("footerVisibilityClass");
    const rowBlock = message.slice(
      message.indexOf("{showNextMoveRows && ("),
      message.indexOf("{shouldShowAssistantFooter && ("),
    );
    expect(rowBlock).toContain("<NextMoveRow");
    expect(rowBlock).not.toContain("footerVisibilityClass");
    expect(rowBlock).not.toContain("group-hover:opacity-100");
  });
});

describe("sources panel", () => {
  test("renders persisted sidecar evidence without re-querying", () => {
    expect(panel).toContain("sidecar.sources.map");
    expect(panel).not.toContain("fetch(");
    expect(panel).not.toContain("useEffect(() => {\n    void load");
  });

  test("links open in a new tab with no opener handle or referrer", () => {
    expect(panel).toContain('target="_blank"');
    expect(panel).toContain('rel="noopener noreferrer"');
  });

  test("the visible domain comes from the href being opened, not the provider title", () => {
    const link = panel.slice(
      panel.indexOf("href={source.url}"),
      panel.indexOf("</a>"),
    );
    expect(link).toContain("{source.domain}");
    // A title may be absent or misleading; the domain always renders.
    expect(link.indexOf("{source.domain}")).toBeGreaterThan(0);
  });

  test("is a dismissible modal with restored focus", () => {
    expect(panel).toContain('role="dialog"');
    expect(panel).toContain('aria-modal="true"');
    expect(panel).toContain('event.key === "Escape"');
    expect(panel).toContain("restoreFocusRef.current?.focus?.()");
    expect(panel).toContain("onClick={onClose}");
  });

  test("framing is descriptive rather than endorsing", () => {
    expect(en.chat.discovery_results.sources_panel_note).toContain(
      "Not recommended reading",
    );
  });
});

describe("locale parity for the new surface", () => {
  test.each([
    "sources_panel_open",
    "sources_panel_title",
    "sources_panel_note",
    "sources_panel_close",
  ])("%s exists in both catalogs", (key) => {
    expect(typeof en.chat.discovery_results[key]).toBe("string");
    expect(typeof es.chat.discovery_results[key]).toBe("string");
    expect(en.chat.discovery_results[key].length).toBeGreaterThan(0);
    expect(es.chat.discovery_results[key].length).toBeGreaterThan(0);
  });

  test("the source count interpolates the same variable in both catalogs", () => {
    expect(en.chat.discovery_results.sources_panel_open).toContain("{{total}}");
    expect(es.chat.discovery_results.sources_panel_open).toContain("{{total}}");
  });
});
