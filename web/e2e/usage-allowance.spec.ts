import { expect, test, type Page } from "@playwright/test";

type UsageShellOptions = {
  language?: "en" | "es-419";
  locale?: "en-US" | "es-419";
  messages?: {
    limit: number;
    used: number;
    remaining: number;
    period_end: string;
  };
};

async function mockUsageShell(
  page: Page,
  { language = "en", locale = "en-US", messages }: UsageShellOptions = {},
) {
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
          language,
          locale,
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
    messages
      ? route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({
            allowances: {
              messages,
            },
          }),
        })
      : route.fulfill({
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

async function openUsageDialog(
  page: Page,
  labels: { settings: string; data: string; usage: string },
) {
  const settingsTrigger = page.getByRole("button", { name: labels.settings });
  await settingsTrigger.focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: labels.data }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: labels.usage }).focus();
  await page.keyboard.press("Enter");
  return settingsTrigger;
}

test("Usage dialog traps focus and restores the Settings trigger", async ({
  page,
}) => {
  await mockUsageShell(page);
  await page.goto("/chat", { waitUntil: "networkidle" });

  const settingsTrigger = await openUsageDialog(page, {
    settings: "Settings",
    data: "Data Controls",
    usage: "Usage",
  });

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

test("Usage renders the English zero state and backend reset", async ({
  page,
}) => {
  const periodEnd = "2026-07-18T00:00:00Z";
  await mockUsageShell(page, {
    messages: { limit: 50, used: 0, remaining: 50, period_end: periodEnd },
  });
  await page.goto("/chat", { waitUntil: "networkidle" });
  await openUsageDialog(page, {
    settings: "Settings",
    data: "Data Controls",
    usage: "Usage",
  });

  const dialog = page.getByRole("dialog", { name: "Usage" });
  await expect(dialog).toContainText(
    "Your current message allowance. Simulation usage is temporarily unavailable.",
  );
  await expect(dialog.getByRole("heading", { name: "Messages" })).toBeVisible();
  await expect(dialog).toContainText("0 of 50 used");
  await expect(dialog).toContainText("No usage yet");
  await expect(dialog).toContainText("Resets");
  await expect(dialog.locator(`time[datetime="${periodEnd}"]`)).not.toBeEmpty();
  await expect(dialog.getByText("Simulations", { exact: true })).toHaveCount(0);
});

test("Usage renders the Spanish exhausted state and backend reset", async ({
  page,
}) => {
  const periodEnd = "2026-07-18T00:00:00Z";
  await mockUsageShell(page, {
    language: "es-419",
    locale: "es-419",
    messages: { limit: 50, used: 50, remaining: 0, period_end: periodEnd },
  });
  await page.goto("/chat", { waitUntil: "networkidle" });
  await openUsageDialog(page, {
    settings: "Ajustes",
    data: "Controles de datos",
    usage: "Uso",
  });

  const dialog = page.getByRole("dialog", { name: "Uso" });
  await expect(dialog).toContainText(
    "Tu cupo actual de mensajes. El uso de simulaciones no está disponible temporalmente.",
  );
  await expect(dialog.getByRole("heading", { name: "Mensajes" })).toBeVisible();
  await expect(dialog).toContainText("50 de 50 usados");
  await expect(dialog).toContainText("Cupo agotado para este periodo");
  await expect(dialog).toContainText("Se restablece");
  await expect(dialog.locator(`time[datetime="${periodEnd}"]`)).not.toBeEmpty();
  await expect(dialog.getByText("Simulaciones", { exact: true })).toHaveCount(
    0,
  );
});
