import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import { formattedSourceDate } from "../components/chat/DiscoverySourcesPanel";

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

  test("persistent discovery rows obey the same in-flight lock as the composer", () => {
    // Discovery rows deliberately survive on older messages, so the per-message
    // streaming flag does not cover them. Without the shared lock they would be
    // a way to fire turns while one is already running.
    expect(chat).toContain("const turnInFlight =");
    expect(chat).toContain("turnInFlight={turnInFlight}");
    expect(message).toContain("disabled={turnInFlight}");
    expect(row).toContain("disabled={disabled}");
    // Disabled rows stay readable: they are evidence, not just an affordance.
    expect(row).toContain("disabled:opacity-55");
    expect(row).not.toContain("disabled:hidden");
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

  test("both panel controls carry a 44px tap target despite compact visuals", () => {
    // The trigger is a 12px text line and the close button is a 16px icon.
    // Neither may rely on its visual box for touch: the trigger extends its hit
    // area with a pseudo-element so the baseline-aligned sources row is
    // unchanged, and the close button gets a real 44px box pulled into its
    // padding so the header layout is unchanged.
    const trigger = message.slice(
      message.indexOf("sources_panel_open") - 600,
      message.indexOf("sources_panel_open"),
    );
    expect(trigger).toContain("after:h-11");
    expect(trigger).toContain("after:min-w-11");
    expect(trigger).toContain("relative");

    const close = panel.slice(
      panel.indexOf("sources_panel_close") - 400,
      panel.indexOf("sources_panel_close") + 400,
    );
    expect(close).toContain("min-h-11");
    expect(close).toContain("min-w-11");
  });

  test("is a dismissible modal with restored focus", () => {
    expect(panel).toContain('role="dialog"');
    expect(panel).toContain('aria-modal="true"');
    expect(panel).toContain('event.key === "Escape"');
    expect(panel).toContain("restoreFocusRef.current?.focus?.()");
    expect(panel).toContain("onClick={onClose}");
  });

  test("a publisher's calendar date is never shifted by the viewer's timezone", () => {
    // A bare source_date is a calendar date, not an instant. Parsed as UTC
    // midnight and formatted locally, it would read a day early west of UTC.
    expect(formattedSourceDate("2026-07-20", "en-US")).toBe("Jul 20, 2026");
    expect(formattedSourceDate("2026-01-01", "en-US")).toBe("Jan 1, 2026");
  });

  test("absent or unparseable source dates render as nothing, never as an error", () => {
    expect(formattedSourceDate(null, "en-US")).toBe("");
    expect(formattedSourceDate(undefined, "en-US")).toBe("");
    expect(formattedSourceDate("not-a-date", "en-US")).toBe("");
  });

  test("framing is descriptive rather than endorsing", () => {
    expect(en.chat.discovery_results.sources_panel_note).toContain(
      "Not recommended reading",
    );
  });
});

describe("locale parity for the new surface", () => {
  test.each([
    "sources_panel_open_one",
    "sources_panel_open_other",
    "sources_panel_title",
    "sources_panel_note",
    "sources_panel_close",
  ])("%s exists in both catalogs", (key) => {
    expect(typeof en.chat.discovery_results[key]).toBe("string");
    expect(typeof es.chat.discovery_results[key]).toBe("string");
    expect(en.chat.discovery_results[key].length).toBeGreaterThan(0);
    expect(es.chat.discovery_results[key].length).toBeGreaterThan(0);
  });

  test("a single source reads as one source, not '1 sources'", () => {
    for (const catalog of [en, es]) {
      const singular = catalog.chat.discovery_results.sources_panel_open_one;
      const plural = catalog.chat.discovery_results.sources_panel_open_other;
      expect(singular).toContain("{{count}}");
      expect(plural).toContain("{{count}}");
      expect(singular).not.toBe(plural);
    }
    expect(en.chat.discovery_results.sources_panel_open_one).toContain("source ");
    expect(en.chat.discovery_results.sources_panel_open_other).toContain("sources ");
  });
});
