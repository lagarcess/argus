import { expect, test, type Page } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";

/**
 * The keyboard passes for DESIGN.md section 19.
 *
 * Every defect the layer stack was built for is a keyboard defect: focus
 * escaping a nested dialog, Escape closing two levels, a shortcut firing into a
 * surface nobody can see. Reading the code cannot show any of them, so these
 * drive real keys against the production build.
 */

async function openMobile(page: Page) {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ colorScheme: "dark" });
  await installMobileShellFixture(page, { account: "registered" });
  await page.goto("/chat");
  await page.waitForTimeout(1200);
}

async function openPalette(page: Page) {
  await page.getByTestId("chat-shell-menu-trigger").click();
  await page.getByRole("button", { name: /^search$/i }).first().click();
  await page.waitForTimeout(700);
}

test.describe("keyboard layer behavior", () => {
  test("Enter and Space on the three-dot open the menu, never the row", async ({
    page,
  }) => {
    for (const key of ["Enter", "Space"]) {
      await openMobile(page);
      await openPalette(page);

      await page.getByTestId("command-palette-row-menu").first().focus();
      await page.keyboard.press(key);
      await page.waitForTimeout(400);

      // The menu is the affordance; the dossier sheet is what used to win.
      await expect(
        page.getByRole("menuitem", { name: /rename/i }).first(),
      ).toBeVisible();
      await expect(
        page.getByTestId("dossier-sheet-open-conversation"),
      ).toHaveCount(0);
    }
  });

  test("Escape closes the row menu without taking the palette", async ({
    page,
  }) => {
    await openMobile(page);
    await openPalette(page);

    await page.getByTestId("command-palette-row-menu").first().click();
    await page.waitForTimeout(300);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);

    await expect(page.getByRole("menuitem", { name: /rename/i })).toHaveCount(0);
    // The palette is still open: one press, one level.
    await expect(page.locator("[data-palette-row-index]").first()).toBeVisible();

    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);
    await expect(page.locator("[data-palette-row-index]")).toHaveCount(0);
  });

  test("Escape closes a sheet without taking the palette", async ({ page }) => {
    await openMobile(page);
    await openPalette(page);

    await page.locator("[data-palette-row-index]").first().click();
    await expect(
      page.getByTestId("dossier-sheet-open-conversation"),
    ).toBeVisible();

    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);
    await expect(
      page.getByTestId("dossier-sheet-open-conversation"),
    ).toHaveCount(0);
    await expect(page.locator("[data-palette-row-index]").first()).toBeVisible();
  });

  test("Tab cannot escape a confirmation opened from the drawer", async ({
    page,
  }) => {
    await openMobile(page);
    await openPalette(page);

    await page.getByTestId("command-palette-row-menu").first().click();
    await page.getByRole("menuitem", { name: /delete/i }).first().click();
    await page.waitForTimeout(400);

    const confirm = page.locator('[class*="z-[110]"]').first();
    await expect(confirm).toBeVisible();

    for (let press = 0; press < 10; press += 1) {
      await page.keyboard.press("Tab");
      await page.waitForTimeout(60);
      const contained = await page.evaluate(() => {
        const panel = document.querySelector('[class*="z-[110]"]');
        return panel ? panel.contains(document.activeElement) : null;
      });
      expect(contained).toBe(true);
    }
  });
});
