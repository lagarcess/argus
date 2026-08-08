import { expect, test } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";

test("desktop row actions never overlap each other", async ({ page }) => {
  // Expanded 44px hit areas on 26px buttons 4px apart overlapped by 14px, and
  // the later sibling won, so the edge of Rename could archive or delete.
  await page.setViewportSize({ width: 1440, height: 900 });
  await installMobileShellFixture(page, { account: "registered" });
  await page.goto("/chat"); await page.waitForTimeout(1400);
  await page.getByRole("button", { name: /^search$/i }).first().click();
  await page.waitForTimeout(700);
  await page.locator("[data-palette-row-index]").first().hover();
  await page.waitForTimeout(400);

  const boxes = await page.evaluate(() => {
    const cluster = document.querySelector(".argus-row-hover-actions");
    if (!cluster) return null;
    return [...cluster.querySelectorAll("button")].map((b) => {
      const r = b.getBoundingClientRect();
      const after = getComputedStyle(b, "::after");
      const w = parseFloat(after.width) || 0;
      // the effective hit box, pseudo-element included
      const half = Math.max(r.width, w) / 2;
      const cx = r.x + r.width / 2;
      return { left: cx - half, right: cx + half };
    });
  });
  expect(boxes).not.toBeNull();
  for (let i = 1; i < boxes!.length; i += 1) {
    expect(boxes![i].left).toBeGreaterThanOrEqual(boxes![i - 1].right - 0.5);
  }
});

test("below the desktop stop the row menu is 44px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installMobileShellFixture(page, { account: "registered" });
  await page.goto("/chat"); await page.waitForTimeout(1400);
  await page.getByTestId("chat-shell-menu-trigger").click();
  await page.getByRole("button", { name: /^search$/i }).first().click();
  await page.waitForTimeout(700);
  const trigger = page.getByTestId("command-palette-row-menu").first();
  const box = await trigger.boundingBox();
  expect(box!.width).toBeGreaterThanOrEqual(44);
  expect(box!.height).toBeGreaterThanOrEqual(44);
});
