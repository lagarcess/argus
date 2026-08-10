import { expect, test, type Page } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";

async function openRegisteredChat(page: Page): Promise<void> {
  await installMobileShellFixture(page, { account: "registered" });
  await page.goto("/chat");
  await page.waitForTimeout(1400);
}

async function openRecents(page: Page): Promise<void> {
  await page.getByRole("button", { name: /^recents$/i }).first().click();
  await page.waitForTimeout(400);
}

test("Recents owner actions reveal on hover or focus for a fine pointer", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await openRegisteredChat(page);
  await openRecents(page);
  expect(
    await page.evaluate(
      () =>
        matchMedia("(hover: hover) and (pointer: fine)").matches &&
        !matchMedia("(any-pointer: coarse)").matches,
    ),
  ).toBe(true);

  const row = page.locator('[data-conversation-id="conversation-beta"]');
  const actions = row.locator("[data-actions]");
  await expect(row).toContainText("Weekly Nvidia buys");
  await expect(actions).toHaveCSS("opacity", "0");
  await row.hover();
  await expect(actions).toHaveCSS("opacity", "1");
  await page.mouse.move(0, 0);
  await actions.focus();
  await expect(actions).toHaveCSS("opacity", "1");
});

test("profile edit affordances remain discoverable without a mouse", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1024, height: 800 });
  await openRegisteredChat(page);
  await page.getByRole("button", { name: /^settings$/i }).first().click();
  await page.getByRole("button", { name: /^profile$/i }).first().click();

  await expect(
    page.getByRole("button", { name: "Edit display name" }),
  ).toHaveCSS("opacity", "1");

  const preferredName = page.locator("#argus-profile-preferred-name");
  const preferredNamePencil = preferredName.locator("svg");
  await expect(preferredNamePencil).toHaveCSS("opacity", "0");
  await preferredName.focus();
  await expect(preferredNamePencil).toHaveCSS("opacity", "1");
});

test.describe("wide touch affordances", () => {
  test.use({
    hasTouch: true,
    viewport: { width: 1280, height: 900 },
  });

  test("Omnisearch uses its 44px menu instead of hover-only icons", async ({
    page,
  }) => {
    await openRegisteredChat(page);
    expect(
      await page.evaluate(() => matchMedia("(any-pointer: coarse)").matches),
    ).toBe(true);

    await page.getByRole("button", { name: /^search$/i }).first().click();
    await page.waitForTimeout(700);

    const menu = page.getByTestId("command-palette-row-menu").first();
    await expect(menu).toBeVisible();
    const box = await menu.boundingBox();
    expect(box?.width).toBeGreaterThanOrEqual(44);
    expect(box?.height).toBeGreaterThanOrEqual(44);
    await expect(page.locator(".argus-row-hover-actions").first()).toBeHidden();
  });

  test("Omnisearch keeps the wide-touch menu clear of the date", async ({
    page,
  }) => {
    await openRegisteredChat(page);
    await page.getByRole("button", { name: /^search$/i }).first().click();
    await page.waitForTimeout(700);

    const row = page.locator("[data-palette-row-index]").first();
    const menu = row.getByTestId("command-palette-row-menu");
    const date = row.locator(":scope > span").first();
    const menuBox = await menu.boundingBox();
    const dateBox = await date.boundingBox();

    expect(menuBox).not.toBeNull();
    expect(dateBox).not.toBeNull();
    expect(dateBox!.x + dateBox!.width).toBeLessThanOrEqual(menuBox!.x);
  });

  test("Escape returns focus to the wide-touch row menu trigger", async ({
    page,
  }) => {
    await openRegisteredChat(page);
    await page.getByRole("button", { name: /^search$/i }).first().click();
    await page.waitForTimeout(700);

    const trigger = page.getByTestId("command-palette-row-menu").first();
    await trigger.click();
    const firstItem = page.getByRole("menuitem").first();
    await firstItem.focus();
    await page.keyboard.press("Escape");

    await expect(page.getByRole("menu")).toBeHidden();
    await expect(trigger).toBeFocused();
  });
});

test("desktop row actions never overlap each other", async ({ page }) => {
  // Expanded 44px hit areas on 26px buttons 4px apart overlapped by 14px, and
  // the later sibling won, so the edge of Rename could archive or delete.
  await page.setViewportSize({ width: 1440, height: 900 });
  await openRegisteredChat(page);
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
  await openRegisteredChat(page);
  await page.getByTestId("chat-shell-menu-trigger").click();
  await page.getByRole("button", { name: /^search$/i }).first().click();
  await page.waitForTimeout(700);
  const trigger = page.getByTestId("command-palette-row-menu").first();
  const box = await trigger.boundingBox();
  expect(box!.width).toBeGreaterThanOrEqual(44);
  expect(box!.height).toBeGreaterThanOrEqual(44);
});
