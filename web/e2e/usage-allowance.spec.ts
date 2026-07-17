import { expect, test, type Page } from "@playwright/test";

async function mockUsageShell(page: Page) {
  await page.route("**/api/v1/me", async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: {
          id: "usage-user",
          email: "usage@example.com",
          username: "usage-user",
          display_name: "Usage User",
          language: "en",
          locale: "en-US",
          onboarding: {
            completed: true,
            stage: "completed",
            language_confirmed: true,
            primary_goal: "test_stock_idea",
          },
        },
      }),
    }),
  );
  await page.route("**/api/v1/me/usage", async (route) =>
    route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({
        code: "usage_read_failed",
        detail: "Current allowance information is unavailable.",
      }),
    }),
  );
  await page.route("**/api/v1/history**", async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], next_cursor: null }),
    }),
  );
  await page.route("**/api/v1/conversations", async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], next_cursor: null }),
    }),
  );
  await page.route("**/api/v1/chat/starter-prompts", async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ prompts: [] }),
    }),
  );
  await page.route("**/api/v1/search**", async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], next_cursor: null }),
    }),
  );
}

test("Usage dialog traps focus and restores the Settings trigger", async ({
  page,
}) => {
  await mockUsageShell(page);
  await page.goto("/chat", { waitUntil: "networkidle" });

  const settingsTrigger = page.getByRole("button", { name: "Settings" });
  await settingsTrigger.focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Data Controls" }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Usage" }).focus();
  await page.keyboard.press("Enter");

  const dialog = page.getByRole("dialog", { name: "Usage" });
  const close = dialog.getByRole("button", { name: "Close usage" });
  const retry = dialog.getByRole("button", { name: "Try again" });
  await expect(dialog).toBeVisible();
  await expect(retry).toBeVisible();
  await expect(close).toBeFocused();

  await page.keyboard.press("Shift+Tab");
  await expect(retry).toBeFocused();
  await page.keyboard.press("Tab");
  await expect(close).toBeFocused();

  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(settingsTrigger).toBeFocused();
});
