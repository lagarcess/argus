import { expect, test } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";

/**
 * Back during a delete must not spend the confirmation's history entry.
 *
 * Refusing inside the dismissal is too late: the entry is claimed first, so the
 * dialog stayed open owning an id it had already spent, no later press could
 * close it, and while it was still topmost it blocked its parents too.
 */
test("a busy confirmation refuses back and still closes once it settles", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await installMobileShellFixture(page, { account: "registered" });

  let release: () => void = () => undefined;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await page.route("**/api/v1/conversations/**", async (route) => {
    if (route.request().method() !== "DELETE") return route.fallback();
    await held;
    await route.fulfill({ status: 200, body: "{}" });
  });

  // A prior entry, so over-popping shows up as leaving /chat rather than as
  // running off the end of a one-entry history.
  await page.goto("/");
  await page.waitForTimeout(400);
  await page.goto("/chat");
  await page.waitForTimeout(1200);
  await page.getByTestId("chat-shell-menu-trigger").click();
  await page.getByRole("button", { name: /^search$/i }).first().click();
  await page.waitForTimeout(700);
  await page.getByTestId("command-palette-row-menu").first().click();
  await page.getByRole("menuitem", { name: /delete/i }).first().click();

  const confirm = page.locator('[class*="z-[110]"]').first();
  await expect(confirm).toBeVisible();
  await confirm.getByRole("button", { name: /delete/i }).first().click();
  await page.waitForTimeout(500);

  // Back while the request is in flight is refused, and nothing beneath moves.
  await page.goBack();
  await page.waitForTimeout(600);
  await expect(confirm).toBeVisible();
  await expect(page.locator("[data-palette-row-index]").first()).toBeVisible();

  release();
  await page.waitForTimeout(1200);

  // The refusal must not have spent the entry. If it had, the stack would be
  // one short and the next press would walk past the palette and off /chat
  // instead of closing it.
  await page.goBack();
  await page.waitForTimeout(800);
  // Still in the app: the refused press did not consume a level.
  expect(new URL(page.url()).pathname).toBe("/chat");
});
