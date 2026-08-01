import { describe, expect, test } from "bun:test";
import { nextSidebarRecentsState } from "../lib/sidebar-shortcuts";

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
