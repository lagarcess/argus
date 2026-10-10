import { expect, test } from "@playwright/test";

for (const path of ["/personal", "/en/personal"]) {
  test(`${path} ends at the cropped wordmark without a photo reveal`, async ({ page }) => {
    await page.goto(path);
    await page.evaluate(() => document.fonts.ready);
    const footer = page.locator("footer");
    await expect(footer.locator("img")).toHaveCount(0);
    await expect(page.locator("[data-footer-peek]")).toHaveCount(0);
    const crop = footer.locator(':scope > div[aria-hidden="true"]');
    await expect(crop).toHaveText("cuadrao");
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await expect.poll(() => crop.evaluate((node) =>
      Math.abs(node.getBoundingClientRect().bottom - innerHeight),
    )).toBeLessThanOrEqual(1);
    expect(await crop.evaluate((node) =>
      getComputedStyle(node).overflow === "hidden" &&
      node.firstElementChild!.getBoundingClientRect().bottom > node.getBoundingClientRect().bottom,
    )).toBe(true);
    const ending = await page.evaluate(() => ({ height: document.documentElement.scrollHeight, scroll: scrollY }));
    await page.mouse.wheel(0, 600);
    await page.waitForTimeout(600);
    expect(await page.evaluate(() => ({ height: document.documentElement.scrollHeight, scroll: scrollY }))).toEqual(ending);
    await expect(footer.locator("img")).toHaveCount(0);
  });
}
