import { expect, test } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";

/** Below 1024 every panel is a sheet; above it, the dialog it always was. */
const isSheet = (page: import("@playwright/test").Page) =>
  page.evaluate(() => !!document.querySelector("[class*='rounded-t-[28px]']"));

for (const [w, band] of [[390, "phone"], [768, "tablet"], [1440, "desktop"]] as [number, string][]) {
  test(`panels obey the rule at ${band}`, async ({ page }) => {
    await page.setViewportSize({ width: w, height: 900 });
    await installMobileShellFixture(page, { account: "registered" });
    await page.goto("/chat");
    await page.waitForTimeout(1400);
    const wantSheet = w < 1024;

    // settings
    const trigger = page.getByTestId("chat-shell-menu-trigger");
    if (await trigger.count()) await trigger.click();
    await page.waitForTimeout(300);
    await page.getByRole("button", { name: /^settings$/i }).first().click();
    await page.waitForTimeout(500);
    expect(await isSheet(page)).toBe(wantSheet);
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);

    // chat header menu
    const kebab = page.getByRole("button", { name: /chat options/i }).first();
    if (await kebab.count()) {
      await kebab.click();
      await page.waitForTimeout(400);
      expect(await isSheet(page)).toBe(wantSheet);
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
    }
  });
}
