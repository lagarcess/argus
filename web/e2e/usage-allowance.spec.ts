import { expect, test, type Page } from "@playwright/test";

type UsageWindow = {
  limit: number;
  used: number;
  remaining: number;
  period_end: string;
};

type UsageAllowance = {
  hour: UsageWindow;
  day: UsageWindow;
  available_now: boolean;
  limiting_window: "hour" | "day";
};

type UsageShellOptions = {
  language?: "en" | "es-419";
  locale?: "en-US" | "es-419";
  allowances?: {
    messages: UsageAllowance;
    backtests: UsageAllowance;
  };
};

function zeroAllowance(
  hourLimit: number,
  dayLimit: number,
  hourEnd: string,
  dayEnd: string,
): UsageAllowance {
  return {
    hour: {
      limit: hourLimit,
      used: 0,
      remaining: hourLimit,
      period_end: hourEnd,
    },
    day: { limit: dayLimit, used: 0, remaining: dayLimit, period_end: dayEnd },
    available_now: true,
    limiting_window: "day",
  };
}

async function mockUsageShell(
  page: Page,
  { language = "en", locale = "en-US", allowances }: UsageShellOptions = {},
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
    allowances
      ? route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ allowances }),
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

test("Usage renders English message and simulation truth with backend resets", async ({
  page,
}) => {
  const hourEnd = "2026-07-17T15:00:00Z";
  const dayEnd = "2026-07-18T00:00:00Z";
  await mockUsageShell(page, {
    allowances: {
      messages: zeroAllowance(60, 200, hourEnd, dayEnd),
      backtests: zeroAllowance(10, 50, hourEnd, dayEnd),
    },
  });
  await page.goto("/chat", { waitUntil: "networkidle" });
  await openUsageDialog(page, {
    settings: "Settings",
    data: "Data Controls",
    usage: "Usage",
  });

  const dialog = page.getByRole("dialog", { name: "Usage" });
  await expect(dialog).toContainText(
    "Your current message and simulation allowances.",
  );
  await expect(dialog.getByRole("heading", { name: "Messages" })).toBeVisible();
  await expect(
    dialog.getByRole("heading", { name: "Simulations" }),
  ).toBeVisible();
  await expect(dialog).toContainText("0 of 200 used today");
  await expect(dialog).toContainText("0 of 50 used today");
  await expect(dialog).toContainText("No usage yet");
  await expect(dialog).toContainText("Resets");
  await expect(
    dialog.locator(`time[datetime="${dayEnd}"]`).first(),
  ).not.toBeEmpty();
  // Fully available: the hourly window stays out of the story.
  await expect(dialog.locator(`time[datetime="${hourEnd}"]`)).toHaveCount(0);
});

test("Usage reveals the hourly window when the backend marks it limiting", async ({
  page,
}) => {
  const hourEnd = "2026-07-17T15:00:00Z";
  const dayEnd = "2026-07-18T00:00:00Z";
  await mockUsageShell(page, {
    allowances: {
      messages: {
        hour: { limit: 60, used: 60, remaining: 0, period_end: hourEnd },
        day: { limit: 200, used: 90, remaining: 110, period_end: dayEnd },
        available_now: false,
        limiting_window: "hour",
      },
      backtests: zeroAllowance(10, 50, hourEnd, dayEnd),
    },
  });
  await page.goto("/chat", { waitUntil: "networkidle" });
  await openUsageDialog(page, {
    settings: "Settings",
    data: "Data Controls",
    usage: "Usage",
  });

  const dialog = page.getByRole("dialog", { name: "Usage" });
  await expect(dialog).toContainText("90 of 200 used today");
  await expect(dialog).toContainText("Hourly limit reached");
  await expect(dialog).toContainText("60 of 60 used this hour");
  await expect(
    dialog.locator(`time[datetime="${hourEnd}"]`).first(),
  ).not.toBeEmpty();
});

test("Usage renders the Spanish daily-exhausted state and backend reset", async ({
  page,
}) => {
  const hourEnd = "2026-07-17T15:00:00Z";
  const dayEnd = "2026-07-18T00:00:00Z";
  await mockUsageShell(page, {
    language: "es-419",
    locale: "es-419",
    allowances: {
      messages: {
        hour: { limit: 60, used: 0, remaining: 60, period_end: hourEnd },
        day: { limit: 200, used: 200, remaining: 0, period_end: dayEnd },
        available_now: false,
        limiting_window: "day",
      },
      backtests: zeroAllowance(10, 50, hourEnd, dayEnd),
    },
  });
  await page.goto("/chat", { waitUntil: "networkidle" });
  await openUsageDialog(page, {
    settings: "Ajustes",
    data: "Controles de datos",
    usage: "Uso",
  });

  const dialog = page.getByRole("dialog", { name: "Uso" });
  await expect(dialog).toContainText(
    "Tus cupos actuales de mensajes y simulaciones.",
  );
  await expect(dialog.getByRole("heading", { name: "Mensajes" })).toBeVisible();
  await expect(
    dialog.getByRole("heading", { name: "Simulaciones" }),
  ).toBeVisible();
  await expect(dialog).toContainText("200 de 200 usados hoy");
  await expect(dialog).toContainText("Cupo diario agotado");
  await expect(dialog).toContainText("Se restablece");
  await expect(
    dialog.locator(`time[datetime="${dayEnd}"]`).first(),
  ).not.toBeEmpty();
});
