import { expect, test } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";

/**
 * One way to open the conversation from a dossier, never two.
 *
 * The body is shared between the desktop pane and the mobile sheet, and only
 * the sheet pins the action in a footer, so below 1024 both appeared.
 */
const openDossier = async (page: import("@playwright/test").Page) => {
  const trigger = page.getByTestId("chat-shell-menu-trigger");
  if (await trigger.count()) await trigger.click();
  await page.getByRole("button", { name: /^search$/i }).first().click();
  await page.waitForTimeout(700);
  await page.locator("[data-palette-row-index]").first().click();
  await page.waitForTimeout(600);
};

test("the sheet pins the action and drops the row", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installMobileShellFixture(page, { account: "registered" });
  await page.goto("/chat");
  await page.waitForTimeout(1200);
  await openDossier(page);

  await expect(page.getByTestId("dossier-sheet-open-conversation")).toBeVisible();
  await expect(
    page.getByRole("button", { name: /open in conversation/i }),
  ).toHaveCount(0);
});

test("the pane keeps the row, since nothing else offers it", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await installMobileShellFixture(page, { account: "registered" });
  await page.goto("/chat");
  await page.waitForTimeout(1200);

  // At desktop a row click navigates; the pane follows selection instead.
  await page.getByRole("button", { name: /^search$/i }).first().click();
  await page.waitForTimeout(800);
  await page.keyboard.press("ArrowDown");
  await page.waitForTimeout(900);
  await expect(page.locator("[data-dossier-pane]")).toBeVisible();

  await expect(page.getByTestId("dossier-sheet-open-conversation")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: /open in conversation/i }).first(),
  ).toBeVisible();
});
