import { expect, test, type Page } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";

/**
 * The two keyboard passes the existing specs did not already cover.
 *
 * Escape was checked on two particular pairs, and one press closing exactly
 * one level is a claim about every stack the shell can build, not those two.
 * The Omnisearch key being inert behind an open surface was checked nowhere at
 * all, which is the half of the layer registry that has no other proof.
 */

const SHEET = "[class*='rounded-t-[28px]']";
const DIALOG = "[role='dialog']";
/** Recents Quick Peek renders its own fixed layer at z-65. */
const QUICK_PEEK = "[class*='z-[65]']";

async function openChat(page: Page, account: "registered" | "guest") {
  await page.setViewportSize({ width: 390, height: 844 });
  await installMobileShellFixture(page, { account });
  await page.goto("/chat");
  await page.waitForTimeout(1400);
}

async function openDrawer(page: Page) {
  await page.getByTestId("chat-shell-menu-trigger").click();
  await page.waitForTimeout(400);
}

async function openPalette(page: Page) {
  await openDrawer(page);
  await page.getByRole("button", { name: /^search$/i }).first().click();
  await page.waitForTimeout(700);
}

test.describe("Escape closes exactly one level", () => {
  test("a sheet over the drawer: the drawer survives", async ({ page }) => {
    await openChat(page, "registered");
    await openDrawer(page);
    await page.getByRole("button", { name: /^settings$/i }).first().click();
    await page.waitForTimeout(600);
    await expect(page.locator(SHEET).first()).toBeVisible();

    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
    await expect(page.locator(SHEET)).toHaveCount(0);
    await expect(page.getByTestId("sidebar-drawer")).toBeVisible();

    // And the level below still answers, rather than having been spent too.
    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
    await expect(page.getByTestId("sidebar-drawer")).toHaveCount(0);
  });

  test("the whole drawer ladder unwinds one press at a time", async ({
    page,
  }) => {
    // Below the desktop stop the settings panel drills inside one sheet rather
    // than stacking sheets, so the deepest state the shell reaches here is
    // drill, sheet, drawer. Each press has to give back exactly one of them.
    await openChat(page, "registered");
    await openDrawer(page);
    await page.getByRole("button", { name: /^settings$/i }).first().click();
    await page.waitForTimeout(600);
    await page.getByRole("button", { name: /preferences/i }).first().click();
    await page.waitForTimeout(500);
    await page.getByRole("button", { name: /appearance/i }).first().click();
    await page.waitForTimeout(500);
    expect(await page.locator(SHEET).count()).toBe(1);
    await expect(page.getByRole("button", { name: /^dark$/i })).toBeVisible();

    // 1: out of the panel and back into the settings sheet, at the level it
    // was opened from rather than at the top of it.
    await page.keyboard.press("Escape");
    await page.waitForTimeout(600);
    expect(await page.locator(SHEET).count()).toBe(1);
    await expect(page.getByRole("button", { name: /^dark$/i })).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: /app language/i }).first(),
    ).toBeVisible();

    // 2: out of the sheet, still in the drawer.
    await page.keyboard.press("Escape");
    await page.waitForTimeout(600);
    await expect(page.locator(SHEET)).toHaveCount(0);
    await expect(page.getByTestId("sidebar-drawer")).toBeVisible();

    // 3: out of the drawer.
    await page.keyboard.press("Escape");
    await page.waitForTimeout(600);
    await expect(page.getByTestId("sidebar-drawer")).toHaveCount(0);
  });

  test("a panel at desktop replaces the menu rather than stacking on it", async ({
    page,
  }) => {
    // The menu is a popover and the panel is modal, so opening one closes the
    // other. Worth pinning: if it ever became a second layer, one Escape would
    // have to leave the menu standing, and today it correctly has nothing to
    // leave standing.
    await page.setViewportSize({ width: 1280, height: 900 });
    await installMobileShellFixture(page, { account: "registered" });
    await page.goto("/chat");
    await page.waitForTimeout(1400);
    await page.getByRole("button", { name: /^settings$/i }).first().click();
    await page.waitForTimeout(500);
    await page.getByRole("button", { name: /preferences/i }).first().click();
    await page.waitForTimeout(500);
    await page.getByRole("button", { name: /appearance/i }).first().click();
    await page.waitForTimeout(500);
    await expect(page.locator(DIALOG).first()).toBeVisible();
    await expect(
      page.getByRole("button", { name: /data controls/i }),
    ).toHaveCount(0);

    await page.keyboard.press("Escape");
    await page.waitForTimeout(600);
    await expect(page.locator(DIALOG)).toHaveCount(0);
    // Nothing orphaned behind it either.
    await expect(
      page.getByRole("button", { name: /data controls/i }),
    ).toHaveCount(0);
  });

  test("a confirmation over a row menu over the palette: both survive", async ({
    page,
  }) => {
    await openChat(page, "registered");
    await openPalette(page);
    await page.getByTestId("command-palette-row-menu").first().click();
    await page.waitForTimeout(400);
    await page.getByRole("menuitem", { name: /delete/i }).first().click();
    await page.waitForTimeout(500);
    await expect(page.locator('[class*="z-[110]"]').first()).toBeVisible();

    await page.keyboard.press("Escape");
    await page.waitForTimeout(500);
    await expect(page.locator('[class*="z-[110]"]')).toHaveCount(0);
    // The palette is what the user came from and must still be there.
    await expect(page.locator("[data-palette-row-index]").first()).toBeVisible();
  });
});

test.describe("focus stays inside a modal with nothing enabled in it", () => {
  test("Tab cannot leave a confirmation while it is busy", async ({ page }) => {
    // A busy confirmation disables both Cancel and Confirm, so the trap has an
    // empty list to cycle. Containment used to be decided by that list being
    // non-empty, which let Tab out of a surface still claiming aria-modal.
    await page.setViewportSize({ width: 390, height: 844 });
    await installMobileShellFixture(page, { account: "registered" });

    let release: () => void = () => undefined;
    const held = new Promise<void>((resolve) => {
      release = resolve;
    });
    await page.route("**/api/v1/conversations/**", async (route) => {
      if (route.request().method() !== "DELETE") return route.fallback();
      await held;
      await route.fulfill({ status: 200, body: "{}" });
    });

    await page.goto("/chat");
    await page.waitForTimeout(1200);
    await openPalette(page);
    await page.getByTestId("command-palette-row-menu").first().click();
    await page.getByRole("menuitem", { name: /delete/i }).first().click();
    const confirm = page.locator('[class*="z-[110]"]').first();
    await expect(confirm).toBeVisible();
    await confirm.getByRole("button", { name: /delete/i }).first().click();
    await page.waitForTimeout(500);

    for (let press = 0; press < 6; press += 1) {
      await page.keyboard.press("Tab");
      await page.waitForTimeout(80);
      const contained = await page.evaluate(() => {
        const panel = document.querySelector('[class*="z-[110]"]');
        if (!panel) return null;
        const active = document.activeElement;
        // Body is acceptable containment only if nothing at all is focusable;
        // anything else outside the panel means Tab escaped.
        return active === document.body || panel.contains(active);
      });
      expect(contained).toBe(true);
    }

    // Specifically: it did not land on the palette underneath.
    const escaped = await page.evaluate(() =>
      Boolean(document.activeElement?.closest("[data-palette-row-index]")),
    );
    expect(escaped).toBe(false);

    release();
    await page.waitForTimeout(1000);
  });
});

test.describe("a panel that opens for typing starts in the field", () => {
  for (const width of [390, 1280]) {
    test(`language search takes focus at ${width}`, async ({ page }) => {
      // AdaptivePanel owns focus now, and both presentations otherwise start on
      // the close control, so the field's own autoFocus was overridden. Enter
      // then closed the panel instead of searching.
      await page.setViewportSize({ width, height: 900 });
      await installMobileShellFixture(page, { account: "registered" });
      await page.goto("/chat");
      await page.waitForTimeout(1400);
      const trigger = page.getByTestId("chat-shell-menu-trigger");
      if (await trigger.count()) {
        await trigger.click();
        await page.waitForTimeout(400);
      }
      await page.getByRole("button", { name: /^settings$/i }).first().click();
      await page.waitForTimeout(500);
      await page.getByRole("button", { name: /preferences/i }).first().click();
      await page.waitForTimeout(500);
      await page.getByRole("button", { name: /app language/i }).first().click();
      await page.waitForTimeout(700);

      const onField = await page.evaluate(
        () => document.activeElement?.tagName === "INPUT",
      );
      expect(onField).toBe(true);

      // And typing reaches it, rather than the panel acting on the key.
      await page.keyboard.type("esp");
      await page.waitForTimeout(300);
      const typed = await page.evaluate(
        () => (document.activeElement as HTMLInputElement | null)?.value,
      );
      expect(typed).toBe("esp");
    });
  }
});

test.describe("no shortcut acts behind a surface at tablet width", () => {
  /*
   * 720 to 1023 is the band where shortcuts are registered and the settings
   * panel is still a sheet. The guard was a named list of surfaces and that
   * sheet was not on it, so Open Recents mounted Quick Peek at z-65 underneath
   * a z-120 sheet: a real dialog holding focus that nobody could see.
   */
  const TABLET = { width: 800, height: 1000 };

  async function openChatAtTablet(page: Page) {
    await page.setViewportSize(TABLET);
    await installMobileShellFixture(page, { account: "registered" });
    await page.goto("/chat");
    await page.waitForTimeout(1400);
  }

  test("Open Recents does nothing while the settings sheet is up", async ({
    page,
  }) => {
    await openChatAtTablet(page);
    const trigger = page.getByTestId("chat-shell-menu-trigger");
    if (await trigger.count()) {
      await trigger.click();
      await page.waitForTimeout(400);
    }
    await page.getByRole("button", { name: /^settings$/i }).first().click();
    await page.waitForTimeout(600);
    await expect(page.locator(SHEET).first()).toBeVisible();

    await page.keyboard.press("ControlOrMeta+Shift+Comma");
    await page.waitForTimeout(700);

    // The claim is that Quick Peek never mounts. Asserting on focus instead
    // let this pass with the guard removed, because the invisible dialog can
    // mount without having taken focus yet.
    await expect(page.locator(QUICK_PEEK)).toHaveCount(0);
    await expect(page.locator(SHEET).first()).toBeVisible();
  });

  test("and still opens at that width with nothing covering it", async ({
    page,
  }) => {
    // The control. Without it the case above passes on a key that never fires,
    // and the whole band could have had no shortcuts at all.
    await openChatAtTablet(page);
    await page.keyboard.press("ControlOrMeta+Shift+Comma");
    await page.waitForTimeout(700);
    await expect(page.locator(QUICK_PEEK)).toHaveCount(1);
  });

  test("the shortcuts sheet can still close itself", async ({ page }) => {
    // Its key toggles, so the surface it opens must never be a reason to
    // refuse it. Consulting the registry naively would have broken exactly this.
    await page.setViewportSize({ width: 1280, height: 900 });
    await installMobileShellFixture(page, { account: "registered" });
    await page.goto("/chat");
    await page.waitForTimeout(1400);

    await page.keyboard.press("ControlOrMeta+/");
    await page.waitForTimeout(600);
    const shortcuts = page.getByRole("heading", { name: /keyboard shortcuts/i });
    await expect(shortcuts).toBeVisible();

    await page.keyboard.press("ControlOrMeta+/");
    await page.waitForTimeout(600);
    await expect(shortcuts).toHaveCount(0);
  });
});

test.describe("the Omnisearch key never reaches a covered surface", () => {
  for (const account of ["registered", "guest"] as const) {
    test(`inert while the drawer is open (${account})`, async ({ page }) => {
      // Below the mobile threshold this width registers no shortcuts at all,
      // so the key is inert whatever is open. The registry check behind it is
      // covered at desktop, where the key is live.
      await openChat(page, account);
      await openDrawer(page);
      await expect(page.getByTestId("sidebar-drawer")).toBeVisible();

      await page.keyboard.press("ControlOrMeta+k");
      await page.waitForTimeout(600);
      await expect(page.locator("[data-palette-row-index]")).toHaveCount(0);
      await expect(page.getByTestId("sidebar-drawer")).toBeVisible();
    });
  }

  test("inert behind an open panel at a width that does have the key", async ({
    page,
  }) => {
    // The registry half of the rule, on the only widths that can reach it: the
    // drawer does not exist at or above 720, so a phone alone cannot prove the
    // palette declines to open underneath something.
    await page.setViewportSize({ width: 1280, height: 900 });
    await installMobileShellFixture(page, { account: "registered" });
    await page.goto("/chat");
    await page.waitForTimeout(1400);

    await page.getByRole("button", { name: /^settings$/i }).first().click();
    await page.waitForTimeout(500);
    await page.getByRole("button", { name: /preferences/i }).first().click();
    await page.waitForTimeout(500);
    await page.getByRole("button", { name: /appearance/i }).first().click();
    await page.waitForTimeout(500);
    await expect(page.locator(DIALOG).first()).toBeVisible();
    const before = await page.locator(DIALOG).count();

    await page.keyboard.press("ControlOrMeta+k");
    await page.waitForTimeout(600);
    await expect(page.locator("[data-palette-row-index]")).toHaveCount(0);
    expect(await page.locator(DIALOG).count()).toBe(before);
  });

  test("and opens normally at that width with nothing covering it", async ({
    page,
  }) => {
    // The control. Without it the three cases above pass on a key that was
    // simply never wired.
    await page.setViewportSize({ width: 1280, height: 900 });
    await installMobileShellFixture(page, { account: "registered" });
    await page.goto("/chat");
    await page.waitForTimeout(1400);

    await page.keyboard.press("ControlOrMeta+k");
    await page.waitForTimeout(800);
    await expect(page.locator("[data-palette-row-index]").first()).toBeVisible();
  });
});
