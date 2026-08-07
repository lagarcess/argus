import { describe, expect, test } from "bun:test";
import i18next from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  BELOW_DESKTOP_QUERY,
  BELOW_TABLET_QUERY,
  DESKTOP_LAYOUT,
  DESKTOP_MIN_WIDTH_PX,
  TABLET_MIN_WIDTH_PX,
  layoutForWidth,
  layoutsEqual,
} from "../lib/responsive-layout";
import {
  OVERLAY_HISTORY_KEY,
  claimProgrammaticPop,
  overlayHistoryState,
  ownsPushedHistoryEntry,
  recordProgrammaticPop,
  resetProgrammaticPops,
} from "../components/layout/useOverlayBackDismiss";
import { sidebarDrawerDragOutcome } from "../components/sidebar/SidebarDrawer";
import ChatShellMenuTrigger from "../components/chat/ChatShellMenuTrigger";
import SidebarHeader from "../components/sidebar/SidebarHeader";
import SidebarShell from "../components/sidebar/SidebarShell";

const globalsCss = readFileSync(
  join(import.meta.dir, "../app/globals.css"),
  "utf-8",
);
const chatInterface = readFileSync(
  join(import.meta.dir, "../components/chat/ChatInterface.tsx"),
  "utf-8",
);
const commandPalette = readFileSync(
  join(import.meta.dir, "../components/sidebar/ChatCommandPalette.tsx"),
  "utf-8",
);
const chatSidebar = readFileSync(
  join(import.meta.dir, "../components/sidebar/ChatSidebar.tsx"),
  "utf-8",
);

async function render(node: React.ReactElement): Promise<string> {
  const i18n = i18next.createInstance();
  await i18n.init({ lng: "en", fallbackLng: false });
  return renderToStaticMarkup(
    <I18nextProvider i18n={i18n}>{node}</I18nextProvider>,
  );
}

describe("responsive layout thresholds", () => {
  test("matches the two thresholds the spec sets", () => {
    expect(TABLET_MIN_WIDTH_PX).toBe(720);
    expect(DESKTOP_MIN_WIDTH_PX).toBe(1024);
  });

  test("classifies each DESIGN.md band by width", () => {
    expect(layoutForWidth(390)).toEqual({
      isBelowTablet: true,
      isBelowDesktop: true,
    });
    expect(layoutForWidth(719)).toEqual({
      isBelowTablet: true,
      isBelowDesktop: true,
    });
    expect(layoutForWidth(720)).toEqual({
      isBelowTablet: false,
      isBelowDesktop: true,
    });
    expect(layoutForWidth(1023)).toEqual({
      isBelowTablet: false,
      isBelowDesktop: true,
    });
    expect(layoutForWidth(1024)).toEqual(DESKTOP_LAYOUT);
    expect(layoutForWidth(1920)).toEqual(DESKTOP_LAYOUT);
  });

  test("queries stop just below each stop so the boundary width is desktop-side", () => {
    expect(BELOW_TABLET_QUERY).toBe("(max-width: 719.98px)");
    expect(BELOW_DESKTOP_QUERY).toBe("(max-width: 1023.98px)");
  });

  test("server and first client paint agree on the desktop band", () => {
    expect(DESKTOP_LAYOUT).toEqual({
      isBelowTablet: false,
      isBelowDesktop: false,
    });
    expect(layoutsEqual(DESKTOP_LAYOUT, layoutForWidth(1440))).toBe(true);
    expect(layoutsEqual(DESKTOP_LAYOUT, layoutForWidth(390))).toBe(false);
  });

  test("never sniffs the pointer type to choose a layout", () => {
    expect(commandPalette).not.toContain("pointer: coarse");
    expect(chatInterface).not.toContain("pointer: coarse");
  });
});

describe("system back closes overlays", () => {
  test("marks the pushed entry so only its owner pops it", () => {
    const state = overlayHistoryState({ existing: 1 }, "sheet-a");
    expect(state.existing).toBe(1);
    expect(state[OVERLAY_HISTORY_KEY]).toBe("sheet-a");
    expect(ownsPushedHistoryEntry(state, "sheet-a")).toBe(true);
    expect(ownsPushedHistoryEntry(state, "sheet-b")).toBe(false);
    expect(ownsPushedHistoryEntry(null, "sheet-a")).toBe(false);
  });

  test("a programmatic pop is claimed once and never read as a user back", () => {
    resetProgrammaticPops();
    expect(claimProgrammaticPop()).toBe(false);
    recordProgrammaticPop();
    expect(claimProgrammaticPop()).toBe(true);
    expect(claimProgrammaticPop()).toBe(false);
  });

  test("counts pops per document, so a remount cannot dismiss itself", () => {
    // A sheet that mounts, cleans up, and remounts pops its own entry twice.
    resetProgrammaticPops();
    recordProgrammaticPop();
    recordProgrammaticPop();
    expect(claimProgrammaticPop()).toBe(true);
    expect(claimProgrammaticPop()).toBe(true);
    expect(claimProgrammaticPop()).toBe(false);
  });
});

describe("sidebar drawer", () => {
  test("a rightward drag never dismisses", () => {
    expect(
      sidebarDrawerDragOutcome({ deltaX: 120, panelWidth: 320, velocityX: 1 }),
    ).toBe("settle");
  });

  test("a short slow drag settles back", () => {
    expect(
      sidebarDrawerDragOutcome({ deltaX: -40, panelWidth: 320, velocityX: 0.05 }),
    ).toBe("settle");
  });

  test("a drag past a third of the panel dismisses", () => {
    expect(
      sidebarDrawerDragOutcome({ deltaX: -140, panelWidth: 320, velocityX: 0.1 }),
    ).toBe("dismiss");
  });

  test("a flick dismisses before the travel threshold", () => {
    expect(
      sidebarDrawerDragOutcome({ deltaX: -30, panelWidth: 320, velocityX: 0.9 }),
    ).toBe("dismiss");
  });

  test("covers 80 to 85 percent so a strip of chat stays tappable", () => {
    const source = readFileSync(
      join(import.meta.dir, "../components/sidebar/SidebarDrawer.tsx"),
      "utf-8",
    );
    expect(source).toContain("w-[82%]");
    expect(source).toContain("bg-black/35");
  });

  test("only wraps the sidebar below the mobile threshold", async () => {
    const rail = await render(
      <SidebarShell
        isBelowTablet={false}
        isDrawerOpen={false}
        onCloseDrawer={() => undefined}
        label="Navigation"
      >
        <p>rail</p>
      </SidebarShell>,
    );
    expect(rail).toBe("<p>rail</p>");

    const closedDrawer = await render(
      <SidebarShell
        isBelowTablet
        isDrawerOpen={false}
        onCloseDrawer={() => undefined}
        label="Navigation"
      >
        <p>drawer</p>
      </SidebarShell>,
    );
    expect(closedDrawer).toBe("");

    const openDrawer = await render(
      <SidebarShell
        isBelowTablet
        isDrawerOpen
        onCloseDrawer={() => undefined}
        label="Navigation"
      >
        <p>drawer</p>
      </SidebarShell>,
    );
    expect(openDrawer).toContain('role="dialog"');
    expect(openDrawer).toContain('aria-label="Navigation"');
    expect(openDrawer).toContain("drawer");
  });
});

describe("sidebar header", () => {
  test("drawer shows the mark as a static logo and an X as the control", async () => {
    const markup = await render(
      <SidebarHeader
        variant="drawer"
        isOpen
        onToggle={() => undefined}
        onRequestClose={() => undefined}
      />,
    );
    expect(markup).toContain('data-testid="sidebar-drawer-logo"');
    expect(markup).toContain('aria-hidden="true"');
    expect(markup).toContain('data-testid="sidebar-drawer-close"');
    expect(markup).toContain('aria-label="Close sidebar"');
    expect(markup).toContain("h-11 w-11");
  });

  test("the drawer logo is never the dismiss control", async () => {
    const markup = await render(
      <SidebarHeader
        variant="drawer"
        isOpen
        onToggle={() => undefined}
        onRequestClose={() => undefined}
      />,
    );
    const logoIndex = markup.indexOf("sidebar-drawer-logo");
    expect(logoIndex).toBeGreaterThan(-1);
    const before = markup.slice(0, logoIndex);
    const opened = before.split("<button").length - 1;
    const closed = before.split("</button>").length - 1;
    expect(opened).toBe(closed);
  });

  test("web keeps the square-drawer icon it already has", async () => {
    const markup = await render(
      <SidebarHeader variant="rail" isOpen onToggle={() => undefined} />,
    );
    expect(markup).toContain("lucide-panel-left");
    expect(markup).not.toContain("sidebar-drawer-close");
  });
});

describe("mobile top bar", () => {
  test("the trigger is a menu glyph with an accessible name", async () => {
    const markup = await render(
      <ChatShellMenuTrigger onOpen={() => undefined} />,
    );
    expect(markup).toContain('data-testid="chat-shell-menu-trigger"');
    expect(markup).toContain('aria-label="Open sidebar"');
    expect(markup).toContain('aria-haspopup="dialog"');
    // Two bars with the lower one shorter, not an even three-bar hamburger.
    expect(markup).toContain('<line x1="3" y1="9" x2="21" y2="9"></line>');
    expect(markup).toContain('<line x1="3" y1="15" x2="14" y2="15"></line>');
    expect(markup).not.toContain("lucide-menu");
    expect(markup).toContain("h-11 w-11");
  });

  test("activity aggregates onto the trigger", async () => {
    const quiet = await render(
      <ChatShellMenuTrigger onOpen={() => undefined} activityPresentation="none" />,
    );
    expect(quiet).not.toContain("data-conversation-activity");

    const busy = await render(
      <ChatShellMenuTrigger
        onOpen={() => undefined}
        activityPresentation="attention"
      />,
    );
    expect(busy).toContain("data-conversation-activity");
  });

  test("the trigger drops its aggregate once the drawer is open", () => {
    expect(chatInterface).toContain("mobileShell.isDrawerOpen\n                      ? null");
  });

  test("guest keeps Sign up pinned right and loses only the gear", () => {
    expect(chatInterface).toContain("showSettings={!mobileShell.isBelowTablet}");
  });

  test("the drawer carries guest settings at its bottom", () => {
    expect(chatInterface).toContain('placement="drawer"');
    expect(chatSidebar).toContain('data-testid="sidebar-guest-settings"');
  });

  test("the rail preference entry is absent in drawer mode, not greyed", () => {
    expect(chatSidebar).toContain(
      "const sidebarPreferenceHandler = isDrawer ? undefined : onOpenSidebarPreference;",
    );
  });
});

describe("omnisearch below threshold", () => {
  test("is collapsed-only", () => {
    expect(commandPalette).toContain(
      'const effectiveLayoutMode: LayoutMode = isBelowTablet ? "collapsed" : layoutMode;',
    );
  });

  test("hides the layout toggle where the band forces collapsed", () => {
    expect(commandPalette).toContain(
      "onToggleLayout={isBelowTablet ? undefined : toggleLayout}",
    );
  });

  test("a row tap opens the dossier sheet rather than a third pane", () => {
    expect(commandPalette).toContain("setIsDossierSheetOpen(true)");
    expect(commandPalette).toContain(
      '{effectiveLayoutMode === "expanded" && !isBelowDesktop && (',
    );
  });

  test("pins Open conversation inside the sheet", () => {
    expect(commandPalette).toContain(
      'data-testid="dossier-sheet-open-conversation"',
    );
    expect(commandPalette).toContain("commandPaletteOpenLabelKey(selectedPreview)");
  });

  test("row actions are explicit at every width a touch device is likely to use", () => {
    // Hover reveal cannot be the only affordance where hover does not exist, so
    // the whole band below the desktop stop gets the visible menu.
    expect(commandPalette).toContain(
      'const rowActionVariant = isBelowDesktop ? "menu" : "hover";',
    );
  });

  test("the hover cluster stays visible where hover does not exist", () => {
    const rowActions = readFileSync(
      join(
        import.meta.dir,
        "../components/sidebar/command-palette/CommandPaletteRowActions.tsx",
      ),
      "utf-8",
    );
    expect(rowActions).toContain("argus-row-hover-actions");
    const hoverNone = globalsCss.slice(globalsCss.indexOf("@media (hover: none)"));
    expect(hoverNone).toContain(".argus-row-hover-actions");
    expect(hoverNone).toContain("opacity: 1;");
  });

  test("pointer, keyboard, and the search field share one row-open path", () => {
    // A keyboard user must not get a different, more destructive navigation.
    expect(commandPalette).toContain("const openRow = useCallback(");
    expect(commandPalette).not.toContain("activateItem(item)");
    expect(commandPalette).not.toContain(
      "activateItem(selectedPreview, action.openAtLeftOff)",
    );
    const rowKeyDown = commandPalette.slice(
      commandPalette.indexOf("const handleRowKeyDown"),
      commandPalette.indexOf("const handleRowKeyDown") + 700,
    );
    expect(rowKeyDown).toContain("openRow(item, {");
  });

  test("Escape dismisses one level, not the whole of Omnisearch", () => {
    // Both listeners are on document in the capture phase and this one runs
    // first, so stopPropagation in the sheet cannot reach it.
    const escape = commandPalette.slice(
      commandPalette.indexOf('if (event.key === "Escape") {'),
      commandPalette.indexOf('if (event.key === "Escape") {') + 400,
    );
    expect(escape).toContain("if (isDossierSheetOpen) return;");
  });

  test("the row date is a column rather than an overlay", () => {
    // Absolute positioning let a wide chip run underneath the date.
    expect(commandPalette).toContain(
      '? "shrink-0 self-center whitespace-nowrap text-[11px] text-black/30 dark:text-white/30"',
    );
    expect(commandPalette).toContain("max-desktop:min-h-11 max-desktop:pe-12");
  });
});

describe("activity rail and starter pills", () => {
  test("the rail is absent below 720 and present from tablet up", () => {
    const rail = readFileSync(
      join(import.meta.dir, "../components/chat/ConversationActivityRail.tsx"),
      "utf-8",
    );
    expect(rail).toContain("hidden md:block");
    // md aliases the tablet stop, so "hidden md:block" is exactly the 720 rule.
    expect(globalsCss).toContain("--breakpoint-md: 45rem;");
  });

  test("starter pills scroll with a peek on narrow screens", () => {
    const starters = readFileSync(
      join(import.meta.dir, "../components/chat/StarterActions.tsx"),
      "utf-8",
    );
    expect(starters).toContain("argus-starter-peek");
    expect(starters).toContain("overflow-x-auto");
    expect(globalsCss).toContain(".argus-starter-peek");
    expect(starters).not.toContain("dismiss");
  });

  test("pills center while they fit and only then become a carousel", () => {
    const starters = readFileSync(
      join(import.meta.dir, "../components/chat/StarterActions.tsx"),
      "utf-8",
    );
    // `safe center` centers the row but falls back to start on overflow, so the
    // first pill can never end up unreachable off the leading edge.
    expect(starters).toContain("[justify-content:safe_center]");
    // The peek promises more pills, so it is measured rather than assumed.
    expect(starters).toContain("scroller.scrollWidth > scroller.clientWidth");
    expect(starters).toContain("new ResizeObserver(sync)");
    expect(starters).toContain('isOverflowing ? "argus-starter-peek" : ""');
    // Trailing padding inside the scroller would widen scrollWidth and make the
    // overflow measurement depend on its own result.
    expect(starters).not.toContain("pe-6");
  });

  test("pills sit above the composer where a thumb reaches them", () => {
    const surface = readFileSync(
      join(import.meta.dir, "../components/chat/EmptyChatSurface.tsx"),
      "utf-8",
    );
    // One instance, placed by flex order: pills before the composer on narrow,
    // after it from tablet up.
    expect(surface.match(/<StarterActions/g)?.length).toBe(1);
    expect(surface).toContain("order-2 w-full max-w-2xl max-tablet:mb-3 tablet:order-3");
    expect(surface).toContain('className="order-3 w-full max-w-2xl tablet:order-2"');
    expect(surface).toContain('layout={isBelowTablet ? "scroll" : "wrap"}');
  });

  test("the composer and pills settle on the bottom edge below the threshold", () => {
    const surface = readFileSync(
      join(import.meta.dir, "../components/chat/EmptyChatSurface.tsx"),
      "utf-8",
    );
    // The heading absorbs the free space, which pushes the pair to the bottom.
    expect(surface).toContain("max-tablet:flex-1 max-tablet:justify-center");
    // The home indicator must not sit on top of the composer.
    expect(surface).toContain("pb-[max(1rem,env(safe-area-inset-bottom))]");
    // The tall inset is a min-width variant, never a base value a `sm:` rule
    // could win back between 400 and 719px.
    expect(surface).toContain("tablet:pt-[28vh]");
    expect(surface).not.toContain("sm:pt-[28vh]");
    expect(surface).not.toContain("pt-[24vh]");
  });

  test("suggestion rows clamp to two lines, never one", () => {
    expect(globalsCss).toContain(".argus-next-move-text");
    expect(globalsCss).toContain("line-clamp: 2;");
    expect(globalsCss).not.toContain("line-clamp: 1;");
  });
});

describe("confirmation card on narrow screens", () => {
  test("keeps all five actions and meets the 44px tap target", () => {
    const card = readFileSync(
      join(import.meta.dir, "../components/chat/StrategyConfirmationCard.tsx"),
      "utf-8",
    );
    expect(card).toContain("min-h-11");
    expect(card).toContain("tablet:min-h-9");
    expect(card).toContain("flex flex-wrap gap-2");
  });
});
