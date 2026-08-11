import { expect, test } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";

test("Shift+Tab from the search field never lands on the backdrop", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installMobileShellFixture(page, { account: "registered" });
  await page.goto("/chat"); await page.waitForTimeout(1400);
  await page.getByTestId("chat-shell-menu-trigger").click();
  await page.getByRole("button", { name: /^search$/i }).first().click();
  await page.waitForTimeout(700);
  for (let i = 0; i < 4; i += 1) {
    await page.keyboard.press("Shift+Tab");
    await page.waitForTimeout(150);
    const onBackdrop = await page.evaluate(() =>
      (document.activeElement?.className || "").startsWith("absolute inset-0"));
    expect(onBackdrop).toBe(false);
  }
  await expect(page.locator("[data-palette-row-index]").first()).toBeVisible();
});

test("closing the settings sheet leaves exactly one level spent", async ({ page }) => {
  // Two owners meant two history.back() calls for one entry, so the press
  // after it was swallowed.
  await page.setViewportSize({ width: 390, height: 844 });
  await installMobileShellFixture(page, { account: "registered" });
  await page.goto("/"); await page.waitForTimeout(400);
  await page.goto("/chat"); await page.waitForTimeout(1400);

  await page.getByTestId("chat-shell-menu-trigger").click();
  await page.waitForTimeout(400);
  await page.getByRole("button", { name: /^settings$/i }).first().click();
  await page.waitForTimeout(600);
  await expect(page.locator("[class*='rounded-t-[28px]']").first()).toBeVisible();

  // back closes the sheet and leaves the drawer
  await page.goBack(); await page.waitForTimeout(700);
  await expect(page.locator("[class*='rounded-t-[28px]']")).toHaveCount(0);
  await expect(page.getByTestId("sidebar-drawer")).toBeVisible();

  // and the next press closes the drawer rather than being swallowed
  await page.goBack(); await page.waitForTimeout(700);
  await expect(page.getByTestId("sidebar-drawer")).toHaveCount(0);
  expect(new URL(page.url()).pathname).toBe("/chat");
});
