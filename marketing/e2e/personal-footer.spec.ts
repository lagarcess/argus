import { expect, test, type Page } from "@playwright/test";

const footer = (page: Page) => page.locator("[data-footer-peek]");
const artisan = (page: Page) => footer(page).locator('img[src*="footer-artisan"]');
const opacity = (page: Page) => artisan(page).evaluate((image) => Number(getComputedStyle(image).opacity));
const reveal = (page: Page) => footer(page).evaluate((frame) =>
  frame.getBoundingClientRect().bottom -
  frame.querySelector("img")!.parentElement!.getBoundingClientRect().top,
);

async function openFooter(page: Page, path: string) {
  await page.goto(path);
  await page.evaluate(() => document.fonts.ready);
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await expect.poll(() => page.evaluate(() =>
    document.documentElement.scrollHeight - innerHeight - scrollY,
  )).toBeLessThanOrEqual(2);
  for (const image of await footer(page).locator("img").all()) {
    await expect.poll(() => image.evaluate((node: HTMLImageElement) =>
      node.complete && node.naturalWidth > 0,
    )).toBe(true);
  }
  await expect.poll(() => reveal(page)).toBeLessThanOrEqual(0.5);
  await expect(footer(page).getByRole("button")).toHaveCount(0);
}

async function holdReveal(page: Page) {
  return footer(page).evaluate((target) => {
    const touch = (clientY: number) => new Touch({ identifier: 1, target, clientX: 100, clientY });
    target.dispatchEvent(new TouchEvent("touchstart", { bubbles: true, touches: [touch(700)] }));
    target.dispatchEvent(new TouchEvent("touchmove", { bubbles: true, touches: [touch(500)] }));
    return Number(getComputedStyle(target.querySelector('img[src*="footer-artisan"]')!).opacity);
  });
}

for (const path of ["/personal", "/en/personal"]) {
  test(`${path} changes photos once while held, keeps the last photo through return, then starts fresh`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await openFooter(page, path);
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    const images = await footer(page).locator("img").evaluateAll((nodes) => nodes.map((node) => {
      const rect = node.getBoundingClientRect();
      return { left: rect.left, width: rect.width };
    }));
    expect(images[0]).toEqual(images[1]);
    expect(images[0].width).toBe(await footer(page).evaluate((node) => node.clientWidth));
    expect(await holdReveal(page)).toBe(0);
    await expect.poll(() => reveal(page), { intervals: [20] }).toBeGreaterThan(100);
    await expect.poll(() => opacity(page), { intervals: [20] }).toBe(1);
    await page.waitForTimeout(650);
    expect(await opacity(page)).toBe(1);
    expect(await holdReveal(page)).toBe(1);
    await footer(page).dispatchEvent("touchend", { touches: [] });
    expect(await opacity(page)).toBe(1);
    await expect.poll(() => reveal(page)).toBeLessThanOrEqual(0.5);
    await expect.poll(() => opacity(page)).toBe(0);
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBe(height);
    expect(await holdReveal(page)).toBe(0);
    await expect.poll(() => opacity(page), { intervals: [20] }).toBe(1);
    await footer(page).dispatchEvent("touchend", { touches: [] });
  });

  test(`${path} responds to gentle wheel input without extending the page`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await openFooter(page, path);
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    await footer(page).evaluate((target) => {
      for (let step = 0; step < 10; step++) {
        target.dispatchEvent(new WheelEvent("wheel", { bubbles: true, deltaY: 8 }));
      }
    });
    await expect.poll(() => reveal(page), { intervals: [20] }).toBeGreaterThan(50);
    await expect.poll(() => opacity(page), { intervals: [20] }).toBe(1);
    await expect.poll(() => reveal(page)).toBeLessThanOrEqual(0.5);
    await expect.poll(() => opacity(page)).toBe(0);
    expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBe(height);
  });

  test(`${path} keeps photos hidden with reduced motion and resets an active reveal`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await openFooter(page, path);
    await holdReveal(page);
    await expect.poll(() => opacity(page), { intervals: [20] }).toBe(1);
    await page.emulateMedia({ reducedMotion: "reduce" });
    await expect.poll(() => reveal(page)).toBeLessThanOrEqual(0.5);
    expect(await opacity(page)).toBe(0);
    await holdReveal(page);
    await page.waitForTimeout(400);
    expect(await reveal(page)).toBeLessThanOrEqual(0.5);
    expect(await opacity(page)).toBe(0);
  });
}

for (const path of ["/", "/en"]) {
  test(`${path} retains two side-by-side still photos`, async ({ page }) => {
    await page.emulateMedia({ reducedMotion: "no-preference" });
    await openFooter(page, path);
    await holdReveal(page);
    await expect.poll(() => reveal(page), { intervals: [20] }).toBeGreaterThan(100);
    const images = await footer(page).locator("img").evaluateAll((nodes) => nodes.map((node) => {
      const rect = node.getBoundingClientRect();
      return { left: rect.left, right: rect.right, width: rect.width, opacity: getComputedStyle(node).opacity };
    }));
    expect(images[0].right).toBeCloseTo(images[1].left, 0);
    expect(images[0].width).toBeCloseTo(images[1].width, 0);
    expect(images.map((image) => image.opacity)).toEqual(["1", "1"]);
    await page.waitForTimeout(650);
    expect(await opacity(page)).toBe(1);
    await footer(page).dispatchEvent("touchend", { touches: [] });
    await expect.poll(() => reveal(page)).toBeLessThanOrEqual(0.5);
  });
}
