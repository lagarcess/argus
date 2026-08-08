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
