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
  guest_session: null;
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

type ThresholdCase = {
  tone: "teal" | "warning" | "danger";
  expectedColor: string;
  messageDay: UsageWindow;
  backtestDay: UsageWindow;
};

const thresholdHourEnd = "2026-08-07T15:00:00Z";
const thresholdDayEnd = "2026-08-08T00:00:00Z";
const thresholdCases: ThresholdCase[] = [
  {
    tone: "teal",
    expectedColor: "rgb(91, 168, 151)",
    messageDay: {
      limit: 200,
      used: 140,
      remaining: 60,
      period_end: thresholdDayEnd,
    },
    backtestDay: {
      limit: 50,
      used: 35,
      remaining: 15,
      period_end: thresholdDayEnd,
    },
  },
  {
    tone: "warning",
    expectedColor: "rgb(194, 164, 77)",
    messageDay: {
      limit: 200,
      used: 142,
      remaining: 58,
      period_end: thresholdDayEnd,
    },
    backtestDay: {
      limit: 50,
      used: 36,
      remaining: 14,
      period_end: thresholdDayEnd,
    },
  },
  {
    tone: "danger",
    expectedColor: "rgb(214, 109, 117)",
    messageDay: {
      limit: 200,
      used: 180,
      remaining: 20,
      period_end: thresholdDayEnd,
    },
    backtestDay: {
      limit: 50,
      used: 45,
      remaining: 5,
      period_end: thresholdDayEnd,
    },
  },
];

function thresholdAllowance(day: UsageWindow, hourLimit: number): UsageAllowance {
  return {
    hour: {
      limit: hourLimit,
      used: 0,
      remaining: hourLimit,
      period_end: thresholdHourEnd,
    },
    day,
    guest_session: null,
    available_now: true,
    limiting_window: "day",
  };
}

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
    guest_session: null,
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

test("Usage colors message and backtest gauges independently", async ({
  page,
}) => {
  const danger = thresholdCases.find(({ tone }) => tone === "danger");
  const teal = thresholdCases.find(({ tone }) => tone === "teal");
  expect(danger).toBeDefined();
  expect(teal).toBeDefined();
  if (!danger || !teal) return;

  await mockUsageShell(page, {
    allowances: {
      messages: thresholdAllowance(danger.messageDay, 60),
      backtests: thresholdAllowance(teal.backtestDay, 10),
    },
  });
  await page.goto("/chat", { waitUntil: "networkidle" });
  await openUsageDialog(page, {
    settings: "Settings",
    data: "Data Controls",
    usage: "Usage",
  });

  const dialog = page.getByRole("dialog", { name: "Usage" });
  const bars = dialog.getByRole("progressbar");
  await expect(bars.nth(0).locator("div")).toHaveCSS(
    "background-color",
    danger.expectedColor,
  );
  await expect(bars.nth(1).locator("div")).toHaveCSS(
    "background-color",
    teal.expectedColor,
  );
  await expect(dialog).toContainText("20 left today");
  await expect(dialog).toContainText("15 left today");
  await expect(dialog.locator(`time[datetime="${thresholdDayEnd}"]`)).toHaveCount(
    2,
  );
});

for (const languageCase of [
  {
    language: "en" as const,
    locale: "en-US" as const,
    theme: "light" as const,
    labels: {
      settings: "Settings",
      data: "Data Controls",
      usage: "Usage",
    },
    remainingText: (count: number) => `${count} left today`,
  },
  {
    language: "es-419" as const,
    locale: "es-419" as const,
    theme: "dark" as const,
    labels: {
      settings: "Ajustes",
      data: "Controles de datos",
      usage: "Uso",
    },
    remainingText: (count: number) => `Quedan ${count} hoy`,
  },
]) {
  for (const thresholdCase of thresholdCases) {
    test(`Usage captures ${thresholdCase.tone} in ${languageCase.language} ${languageCase.theme}`, async ({
      page,
    }) => {
      await page.addInitScript((theme) => {
        window.localStorage.setItem("argus-theme", theme);
      }, languageCase.theme);
      await mockUsageShell(page, {
        language: languageCase.language,
        locale: languageCase.locale,
        allowances: {
          messages: thresholdAllowance(thresholdCase.messageDay, 60),
          backtests: thresholdAllowance(thresholdCase.backtestDay, 10),
        },
      });
      await page.goto("/chat", { waitUntil: "networkidle" });
      await openUsageDialog(page, languageCase.labels);

      const dialog = page.getByRole("dialog", {
        name: languageCase.labels.usage,
      });
      const bars = dialog.getByRole("progressbar");
      await expect(bars).toHaveCount(2);
      for (const bar of await bars.all()) {
        await expect(bar.locator("div")).toHaveCSS(
          "background-color",
          thresholdCase.expectedColor,
        );
      }
      await expect(dialog).toContainText(
        languageCase.remainingText(thresholdCase.messageDay.remaining),
      );
      await expect(dialog).toContainText(
        languageCase.remainingText(thresholdCase.backtestDay.remaining),
      );
      await expect(
        dialog.locator(`time[datetime="${thresholdDayEnd}"]`),
      ).toHaveCount(2);
      if (languageCase.theme === "dark") {
        await expect(page.locator("html")).toHaveClass(/dark/);
      } else {
        await expect(page.locator("html")).not.toHaveClass(/dark/);
      }

      if (process.env.ARGUS_CAPTURE_USAGE_METER_EVIDENCE === "1") {
        await page.evaluate(() => {
          if (document.activeElement instanceof HTMLElement) {
            document.activeElement.blur();
          }
        });
        await page.evaluate(async () => {
          await document.fonts.ready;
        });
        await dialog.screenshot({
          path: `../docs/reports/evidence/usage-allowance-meter/${languageCase.language}-${languageCase.theme}-${thresholdCase.tone}.png`,
          animations: "disabled",
        });
      }
    });
  }
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
  await expect(dialog).not.toContainText("reset automatically");
  await expect(dialog).not.toContainText("private-alpha");
  await expect(dialog).toContainText("200 left today");
  await expect(dialog).toContainText("50 left today");
  await expect(dialog).toContainText("60 available this hour");
  await expect(dialog).toContainText("10 available this hour");
  await expect(dialog).toContainText("Resets");
  await expect(
    dialog.locator(`time[datetime="${dayEnd}"]`).first(),
  ).not.toBeEmpty();
  await expect(dialog).not.toContainText("No usage yet");
  await expect(dialog.locator('.text-\\[\\#b94c55\\]')).toHaveCount(0);

  const requestsBeforeToggle = usageRequests;
  const disclosure = dialog.getByRole("button", { name: "What counts?" });
  await expect(disclosure).toHaveAttribute("aria-expanded", "false");
  await expect(dialog).not.toContainText("Failed or interrupted turns");
  await disclosure.click();
  await expect(disclosure).toHaveAttribute("aria-expanded", "true");
  await expect(dialog).toContainText(
    "Messages count when Argus completes a response. Failed or interrupted responses don’t count.",
  );
  await expect(dialog).toContainText(
    "New simulations count once. Retrying the same simulation doesn’t count again.",
  );
  await expect(dialog).not.toContainText("API");
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
        guest_session: null,
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
        guest_session: null,
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
  await expect(dialog).not.toContainText("alfa privada");
  await expect(dialog).toContainText("Quedan 0 hoy");
  await expect(dialog).toContainText("Quedan 50 hoy");
  await expect(dialog).toContainText("Se restablece");
  const disclosure = dialog.getByRole("button", { name: "¿Qué cuenta?" });
  await disclosure.click();
  await expect(dialog).toContainText(
    "Los mensajes cuentan cuando Argus completa una respuesta. Las respuestas fallidas o interrumpidas no cuentan.",
  );
  await expect(dialog).toContainText(
    "Las simulaciones nuevas cuentan una vez. Reintentar la misma simulación no vuelve a contar.",
  );
  await expect(dialog).not.toContainText("API");
  await expect(
    dialog.locator(`time[datetime="${dayEnd}"]`).first(),
  ).not.toBeEmpty();
});
