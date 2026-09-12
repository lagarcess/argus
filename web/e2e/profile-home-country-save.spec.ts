import { mkdir } from "node:fs/promises";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  expect,
  test,
  type Locator,
  type Page,
  type Route,
} from "@playwright/test";

import { ALL_LANGUAGES, type ArgusLanguage } from "../lib/language-features";

/**
 * A country or currency pick either reaches the account or is shown as refused
 * and put back. The account resolves the currency, so the panel shows what the
 * account answers rather than deriving it.
 *
 * Every `/me` is answered here, so a failed save is chosen rather than waited
 * for. Set PROFILE_WRITE_EVIDENCE_DIR to keep a screenshot of each outcome.
 */

test.describe.configure({ timeout: 90_000 });

type Catalog = {
  common: { settings: string };
  settings: {
    preferences: { title: string };
    app: {
      home_country: string;
      country: string;
      currency: string;
      no_country: string;
    };
    profile: { country_save_error: string };
  };
};

const COPY = Object.fromEntries(
  ALL_LANGUAGES.map(({ code }) => [
    code,
    JSON.parse(
      readFileSync(
        join(__dirname, "..", "public", "locales", code, "common.json"),
        "utf-8",
      ),
    ),
  ]),
) as Record<ArgusLanguage, Catalog>;

const LOCALE: Record<ArgusLanguage, string> = { en: "en-US", "es-419": "es-419" };

// The account's answer for the countries these tests pick; the real
// derivation is the backend's and is tested there.
const IMPLIED_CURRENCY: Record<string, string> = { MX: "MXN", DO: "DOP" };

function region(code: string, language: ArgusLanguage): string {
  return new Intl.DisplayNames([language], { type: "region" }).of(code)!;
}

function currency(code: string, language: ArgusLanguage): string {
  return new Intl.DisplayNames([language], { type: "currency" }).of(code)!;
}

function startsWith(label: string): RegExp {
  return new RegExp(`^${label.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`, "i");
}

/** The dev overlay sits over the sidebar's corner, so controls are pressed, not clicked. */
async function activate(page: Page, control: Locator) {
  await control.focus();
  await page.keyboard.press("Enter");
}

async function fulfillJson(route: Route, body: unknown) {
  await route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function mockAccount(
  page: Page,
  language: ArgusLanguage,
  { outcome = "saves" }: { outcome?: "saves" | "fails" } = {},
) {
  const profile: Record<string, unknown> = {
    id: "country-user",
    email: "country@example.com",
    username: "country-user",
    display_name: "Country User",
    language,
    locale: LOCALE[language],
    avatar_theme: "ocean",
    country: null,
    currency_override: null,
    currency: null,
  };
  const saves: Array<Record<string, unknown>> = [];

  await page.route("**/api/v1/me", async (route) => {
    if (route.request().method() === "PATCH") {
      const patch = route.request().postDataJSON() as Record<string, unknown>;
      saves.push(patch);
      if (outcome === "fails") {
        await route.fulfill({
          status: 503,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Profile store unavailable" }),
        });
        return;
      }
      Object.assign(profile, patch);
      profile.currency =
        profile.currency_override ?? IMPLIED_CURRENCY[String(profile.country)] ?? null;
    }
    await fulfillJson(route, { user: profile, account_kind: "registered" });
  });
  await page.route("**/api/v1/conversations", (route) =>
    fulfillJson(route, { items: [], next_cursor: null }),
  );

  return { saves };
}

async function openHomeCountry(page: Page, language: ArgusLanguage) {
  const copy = COPY[language];
  await activate(page, page.getByRole("button", { name: copy.common.settings }));
  await activate(
    page,
    page.getByRole("button", { name: copy.settings.preferences.title }),
  );
  await activate(
    page,
    page.getByRole("button", { name: copy.settings.app.home_country }),
  );
  const panel = page.getByRole("dialog", { name: copy.settings.app.home_country });
  await expect(panel).toBeVisible();
  return panel;
}

function settingButton(panel: Locator, label: string) {
  return panel.locator("button[aria-pressed]").filter({ hasText: label });
}

async function capture(page: Page, name: string) {
  const dir = process.env.PROFILE_WRITE_EVIDENCE_DIR;
  if (!dir) return;
  await mkdir(dir, { recursive: true });
  await page.addStyleTag({
    content:
      "nextjs-portal, [data-dev-mode-badge] { display: none !important; }",
  });
  await page.screenshot({ path: join(dir, `${name}.png`) });
}

for (const language of ["en", "es-419"] as const) {
  const copy = COPY[language];

  test(`a country shows the currency it implies, an override replaces it, and both survive a reload (${language})`, async ({
    page,
  }) => {
    const { saves } = await mockAccount(page, language);
    await page.goto("/chat", { waitUntil: "networkidle" });

    let panel = await openHomeCountry(page, language);
    await panel.getByRole("textbox").fill(region("MX", language));
    await activate(
      page,
      panel.getByRole("button", { name: startsWith(region("MX", language)) }),
    );
    await expect(settingButton(panel, copy.settings.app.currency)).toContainText("MXN");
    await expect(settingButton(panel, copy.settings.app.country)).toContainText(
      region("MX", language),
    );
    await capture(page, `${language}-country-mx-implies-mxn`);

    await activate(page, settingButton(panel, copy.settings.app.currency));
    await panel.getByRole("textbox").fill("USD");
    await activate(
      page,
      panel.getByRole("button", { name: startsWith(currency("USD", language)) }),
    );
    await expect(settingButton(panel, copy.settings.app.currency)).toContainText("USD");
    expect(saves).toEqual([{ country: "MX" }, { currency_override: "USD" }]);
    await capture(page, `${language}-currency-overridden-usd`);

    await page.reload({ waitUntil: "networkidle" });
    panel = await openHomeCountry(page, language);
    await expect(settingButton(panel, copy.settings.app.country)).toContainText(
      region("MX", language),
    );
    await expect(settingButton(panel, copy.settings.app.currency)).toContainText("USD");
    await capture(page, `${language}-after-reload`);
  });

  test(`a refused country is shown and put back (${language})`, async ({ page }) => {
    const { saves } = await mockAccount(page, language, { outcome: "fails" });
    await page.goto("/chat", { waitUntil: "networkidle" });

    const panel = await openHomeCountry(page, language);
    await panel.getByRole("textbox").fill(region("DO", language));
    await activate(
      page,
      panel.getByRole("button", { name: startsWith(region("DO", language)) }),
    );

    await expect(panel.getByRole("alert")).toHaveText(
      copy.settings.profile.country_save_error,
    );
    expect(saves).toEqual([{ country: "DO" }]);
    await expect(settingButton(panel, copy.settings.app.country)).toContainText(
      copy.settings.app.no_country,
    );
    await capture(page, `${language}-refused-country`);
  });
}
