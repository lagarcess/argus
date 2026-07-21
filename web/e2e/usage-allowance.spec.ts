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
  // Matches real backend derivation: at equal usage the hourly window has
  // the smaller remaining capacity, so it is the most restrictive window.
  return {
    hour: {
      limit: hourLimit,
      used: 0,
      remaining: hourLimit,
      period_end: hourEnd,
    },
    day: { limit: dayLimit, used: 0, remaining: dayLimit, period_end: dayEnd },
    available_now: true,
    limiting_window: "hour",
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

test("Usage renders the quiet remaining-first gauge with one disclosure", async ({
  page,
}) => {
  const hourEnd = "2026-07-17T15:00:00Z";
  const dayEnd = "2026-07-18T00:00:00Z";
  let usageRequests = 0;
  page.on("request", (request) => {
    if (request.url().includes("/api/v1/me/usage")) usageRequests += 1;
  });
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
    "Your private-alpha allowances reset automatically.",
  );
  await expect(dialog).toContainText("200 left today");
  await expect(dialog).toContainText("50 left today");
  await expect(dialog).toContainText("60 available this hour");
  await expect(dialog).toContainText("10 available this hour");
  await expect(dialog).toContainText("Resets");
  await expect(
    dialog.locator(`time[datetime="${dayEnd}"]`).first(),
  ).not.toBeEmpty();
  // Neutral zero state: no usage badges and no warning tint anywhere.
  await expect(dialog).not.toContainText("No usage yet");
  await expect(dialog.locator('.text-\\[\\#b94c55\\]')).toHaveCount(0);

  // One What counts? disclosure owns both counting rules and its toggle
  // never mutates usage or issues another request.
  const requestsBeforeToggle = usageRequests;
  const disclosure = dialog.getByRole("button", { name: "What counts?" });
  await expect(disclosure).toHaveAttribute("aria-expanded", "false");
  await expect(dialog).not.toContainText("Failed or interrupted turns");
  await disclosure.click();
  await expect(disclosure).toHaveAttribute("aria-expanded", "true");
  await expect(dialog).toContainText(
    "Each chat response Argus completes uses one message.",
  );
  await expect(dialog).toContainText(
    "Each unique simulation you start uses one simulation",
  );
  await disclosure.click();
  await expect(disclosure).toHaveAttribute("aria-expanded", "false");
  expect(usageRequests).toBe(requestsBeforeToggle);

  const bars = dialog.getByRole("progressbar");
  await expect(bars).toHaveCount(2);
  await expect(bars.first()).toHaveAttribute("aria-valuenow", "0");
  await expect(bars.first()).toHaveAttribute("aria-valuemax", "200");
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
  await expect(dialog).toContainText("110 left today");
  await expect(dialog).toContainText("0 available this hour");
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
    "Tus cupos de alfa privada se restablecen automáticamente.",
  );
  await expect(dialog).toContainText("Quedan 0 hoy");
  await expect(dialog).toContainText("Quedan 50 hoy");
  await expect(dialog).toContainText("Se restablece");
  await expect(
    dialog.getByRole("button", { name: "¿Qué cuenta?" }),
  ).toBeVisible();
  await expect(
    dialog.locator(`time[datetime="${dayEnd}"]`).first(),
  ).not.toBeEmpty();
});
