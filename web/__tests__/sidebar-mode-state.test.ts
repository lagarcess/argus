import { describe, expect, test } from "bun:test";

import { sidebarOpenAfterTransientNavigation } from "../lib/sidebar-mode-state";

describe("sidebar mode state", () => {
  test("keeps explicit expanded sidebars open across chat navigation", () => {
    expect(
      sidebarOpenAfterTransientNavigation({
        currentOpen: true,
        mode: "expanded",
      }),
    ).toBe(true);
  });

  test("closes temporary collapsed or hover sidebars after navigation", () => {
    expect(
      sidebarOpenAfterTransientNavigation({
        currentOpen: true,
        mode: "collapsed",
      }),
    ).toBe(false);
    expect(
      sidebarOpenAfterTransientNavigation({
        currentOpen: true,
        mode: "hover",
      }),
    ).toBe(false);
  });
});
