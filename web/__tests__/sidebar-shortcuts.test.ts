import { describe, expect, test } from "bun:test";
import {
  nextSidebarRecentsState,
  sidebarShortcutHintsVisible,
} from "../lib/sidebar-shortcuts";

describe("sidebar shortcut hints", () => {
  test("the drawer never badges a chord, since that width has no shortcuts", () => {
    expect(
      sidebarShortcutHintsVisible({
        modifierHeld: true,
        suppressed: false,
        variant: "drawer",
      }),
    ).toBe(false);
  });

  test("the rail badges while the modifier is held and nothing suppresses it", () => {
    expect(
      sidebarShortcutHintsVisible({
        modifierHeld: true,
        suppressed: false,
        variant: "rail",
      }),
    ).toBe(true);
    expect(
      sidebarShortcutHintsVisible({
        modifierHeld: false,
        suppressed: false,
        variant: "rail",
      }),
    ).toBe(false);
    expect(
      sidebarShortcutHintsVisible({
        modifierHeld: true,
        suppressed: true,
        variant: "rail",
      }),
    ).toBe(false);
  });
});

describe("sidebar and Recents shortcut", () => {
  test("closes both surfaces when they are already open", () => {
    expect(nextSidebarRecentsState(true, true)).toEqual({
      sidebarOpen: false,
      recentsExpanded: false,
    });
  });

  test("opens and expands both surfaces from any other state", () => {
    expect(nextSidebarRecentsState(false, false)).toEqual({
      sidebarOpen: true,
      recentsExpanded: true,
    });
    expect(nextSidebarRecentsState(true, false)).toEqual({
      sidebarOpen: true,
      recentsExpanded: true,
    });
  });
});
