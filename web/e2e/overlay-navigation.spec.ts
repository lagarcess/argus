import { expect, test } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";

/**
 * Two rules the whole overlay layer depends on, checked where they can be seen.
 *
 * Both had been fixed one call site at a time before, which is why each of
 * them came back somewhere else.
 */

test("opening a conversation from Omnisearch keeps the URL it navigated to", async ({
  page,
}) => {
  // The palette owns a history entry now. Navigating rewrites the URL onto that
  // entry, so popping it on teardown would put the previous conversation back
  // in the address bar while the new one is on screen, and a reload would
  // return to the wrong one.
  await page.setViewportSize({ width: 1280, height: 900 });
  await installMobileShellFixture(page, { account: "registered" });
  await page.goto("/chat");
  await page.waitForTimeout(1200);

  await page.getByRole("button", { name: /^search$/i }).first().click();
  await page.waitForTimeout(700);
  await page.locator("[data-palette-row-index]").first().click();
  await page.waitForTimeout(1200);

  const opened = new URL(page.url()).searchParams.get("conversation");
  expect(opened).toBeTruthy();

  // The teardown pop, if any, lands after this.
  await page.waitForTimeout(600);
  expect(new URL(page.url()).searchParams.get("conversation")).toBe(opened);
});

test("no overlay hands its first tab stop to a backdrop", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installMobileShellFixture(page, { account: "registered" });
  await page.goto("/chat");
  await page.waitForTimeout(1200);

  await page.getByTestId("chat-shell-menu-trigger").click();
  await page.getByRole("button", { name: /^search$/i }).first().click();
  await page.waitForTimeout(700);

  // Shift+Tab from the search field used to land on the invisible dismiss
  // control, where Enter closed Omnisearch without explaining itself.
  await page.keyboard.press("Shift+Tab");
  await page.waitForTimeout(200);
  const onBackdrop = await page.evaluate(
    () => document.activeElement?.className === "absolute inset-0",
  );
  expect(onBackdrop).toBe(false);
  await expect(page.locator("[data-palette-row-index]").first()).toBeVisible();
});
