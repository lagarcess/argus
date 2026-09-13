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

import {
  LANGUAGE_STORAGE_KEY,
  THEME_STORAGE_KEY,
} from "../lib/browser-storage";
import { ALL_LANGUAGES, type ArgusLanguage } from "../lib/language-features";

/**
 * A language change either reaches the account or is shown as refused and put
 * back, so the page never holds a language the account does not. A theme
 * change never reaches the account: it stays in this browser.
 *
 * Every `/me` is answered here, so a failed save is chosen rather than waited
 * for. Set PROFILE_WRITE_EVIDENCE_DIR to keep a screenshot of each outcome.
 */

test.describe.configure({ timeout: 90_000 });

type Theme = "light" | "dark";

type Catalog = {
  common: { settings: string };
  guest: { shell: { language: string } };
  settings: {
    preferences: { title: string };
    app: {
      language: string;
      appearance: string;
      appearance_options: Record<Theme, string>;
    };
    profile: { language_save_error: string };
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

type SaveOutcome =
  | "saves"
  | "fails"
  | "saves-but-reply-fails"
  | { held: Promise<void> };

function languageRow(language: ArgusLanguage): RegExp {
  const { name } = ALL_LANGUAGES.find((entry) => entry.code === language)!;
  return new RegExp(`^${name}`);
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
  outcome: SaveOutcome,
) {
  const profile = {
    id: "language-user",
    email: "language@example.com",
    username: "language-user",
    display_name: "Language User",
    language,
    locale: LOCALE[language],
    avatar_theme: "ocean",
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
      if (typeof outcome === "object") await outcome.held;
      Object.assign(profile, patch);
      if (outcome === "saves-but-reply-fails") {
        await route.fulfill({
          status: 500,
          contentType: "application/json",
          body: JSON.stringify({ detail: "Profile read failed after the write" }),
        });
        return;
      }
    }
    await fulfillJson(route, { user: profile, account_kind: "registered" });
  });
  await page.route("**/api/v1/conversations", (route) =>
    fulfillJson(route, { items: [], next_cursor: null }),
  );

  return { saves };
}

async function openPreference(
  page: Page,
  language: ArgusLanguage,
  preference: "language" | "appearance",
) {
  const copy = COPY[language];
  await activate(page, page.getByRole("button", { name: copy.common.settings }));
  await activate(
    page,
    page.getByRole("button", { name: copy.settings.preferences.title }),
  );
  await activate(
    page,
    page.getByRole("button", { name: copy.settings.app[preference] }),
  );
  const title =
    preference === "language"
      ? copy.guest.shell.language
      : copy.settings.app.appearance;
  const panel = page.getByRole("dialog", { name: title });
  await expect(panel).toBeVisible();
  return panel;
}

function storedLanguage(page: Page) {
  return page.evaluate(
    (key) => window.localStorage.getItem(key),
    LANGUAGE_STORAGE_KEY,
  );
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

for (const [from, to] of [
  ["en", "es-419"],
  ["es-419", "en"],
] as const) {
  test(`a refused save is shown and put back (${from} account picks ${to})`, async ({
    page,
  }) => {
    const { saves } = await mockAccount(page, from, "fails");
    await page.goto("/chat", { waitUntil: "networkidle" });
    await expect(
      page.getByRole("button", { name: COPY[from].common.settings }),
    ).toBeVisible();

    const panel = await openPreference(page, from, "language");
    await activate(page, panel.getByRole("button", { name: languageRow(to) }));

    await expect(panel.getByRole("alert")).toHaveText(
      COPY[from].settings.profile.language_save_error,
    );
    expect(saves).toEqual([{ language: to, locale: LOCALE[to] }]);
    await expect.poll(() => storedLanguage(page)).toBe(from);
    await capture(page, `${from}-refused-save`);

    // Nothing is left for the next load to take back.
    await page.reload({ waitUntil: "networkidle" });
    await expect(
      page.getByRole("button", { name: COPY[from].common.settings }),
    ).toBeVisible();
    await expect.poll(() => storedLanguage(page)).toBe(from);
  });
}

test("a saved language reaches the account and survives a reload", async ({
  page,
}) => {
  const { saves } = await mockAccount(page, "en", "saves");
  await page.goto("/chat", { waitUntil: "networkidle" });

  const panel = await openPreference(page, "en", "language");
  await activate(page, panel.getByRole("button", { name: languageRow("es-419") }));

  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: COPY["es-419"].common.settings }),
  ).toBeVisible();
  expect(saves).toEqual([{ language: "es-419", locale: "es-419" }]);
  await capture(page, "en-saved-as-es-419");

  await page.reload({ waitUntil: "networkidle" });
  await expect(
    page.getByRole("button", { name: COPY["es-419"].common.settings }),
  ).toBeVisible();
});

test("a save the account took is kept when its reply fails", async ({
  page,
}) => {
  const { saves } = await mockAccount(page, "en", "saves-but-reply-fails");
  await page.goto("/chat", { waitUntil: "networkidle" });

  const panel = await openPreference(page, "en", "language");
  await activate(page, panel.getByRole("button", { name: languageRow("es-419") }));

  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: COPY["es-419"].common.settings }),
  ).toBeVisible();
  expect(saves).toEqual([{ language: "es-419", locale: "es-419" }]);
  await expect.poll(() => storedLanguage(page)).toBe("es-419");
  await capture(page, "en-kept-after-failed-reply");
});

test("a save that outlives its panel cannot close the panel that replaced it", async ({
  page,
}) => {
  let release!: () => void;
  const held = new Promise<void>((resolve) => {
    release = resolve;
  });
  await mockAccount(page, "en", { held });
  await page.goto("/chat", { waitUntil: "networkidle" });

  const language = await openPreference(page, "en", "language");
  await activate(
    page,
    language.getByRole("button", { name: languageRow("es-419") }),
  );
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);

  const appearance = await openPreference(page, "es-419", "appearance");
  const saved = page.waitForResponse(
    (response) =>
      response.request().method() === "PATCH" &&
      new URL(response.url()).pathname.endsWith("/api/v1/me"),
  );
  release();
  await saved;
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  await expect(appearance).toBeVisible();
});

function storedTheme(page: Page) {
  return page.evaluate(
    (key) => window.localStorage.getItem(key),
    THEME_STORAGE_KEY,
  );
}

/** Every `PATCH /me` the page sends from here on. */
function profileWrites(page: Page) {
  const writes: unknown[] = [];
  page.on("request", (request) => {
    if (
      request.method() === "PATCH" &&
      new URL(request.url()).pathname.endsWith("/api/v1/me")
    ) {
      writes.push(request.postDataJSON());
    }
  });
  return writes;
}

/**
 * Requests are reported in the order they were sent, so one sent now is
 * reported after any write already started.
 */
async function afterRequestsSoFar(page: Page) {
  const sentinel = `/locales/en/common.json?sentinel=${Date.now()}`;
  await Promise.all([
    page.waitForRequest((request) => request.url().includes(sentinel)),
    page.evaluate(async (url) => {
      await fetch(url);
    }, sentinel),
  ]);
}

test("the front door keeps a language in this browser and writes no profile", async ({
  page,
}) => {
  const writes = profileWrites(page);
  await page.goto("/?auth=login", { waitUntil: "networkidle" });

  await activate(page, page.getByRole("button", { name: "Settings", exact: true }));
  await activate(
    page,
    page.getByRole("button", { name: COPY.en.settings.app.language }),
  );
  const languages = page.getByRole("dialog");
  await activate(page, languages.getByRole("button", { name: languageRow("es-419") }));
  await expect(languages).toHaveCount(0);

  await afterRequestsSoFar(page);
  expect(writes).toEqual([]);
  await expect.poll(() => storedLanguage(page)).toBe("es-419");
});

for (const [language, system, picked] of [
  ["en", "dark", "light"],
  ["es-419", "light", "dark"],
] as const) {
  test(`a theme change stays in this browser and writes no profile (${language})`, async ({
    page,
  }) => {
    const writes = profileWrites(page);
    await page.emulateMedia({ colorScheme: system });
    await mockAccount(page, language, "saves");
    await page.goto("/chat", { waitUntil: "networkidle" });
    const root = page.locator("html");
    await expect(root).toHaveClass(new RegExp(`\\b${system}\\b`));

    const panel = await openPreference(page, language, "appearance");
    await activate(
      page,
      panel.getByRole("button", {
        name: COPY[language].settings.app.appearance_options[picked],
        exact: true,
      }),
    );
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(root).toHaveClass(new RegExp(`\\b${picked}\\b`));
    await expect.poll(() => storedTheme(page)).toBe(picked);
    await afterRequestsSoFar(page);
    expect(writes).toEqual([]);

    // The system still prefers the other theme, so what survives is the choice.
    await page.reload({ waitUntil: "networkidle" });
    await expect(
      page.getByRole("button", { name: COPY[language].common.settings }),
    ).toBeVisible();
    await expect(root).toHaveClass(new RegExp(`\\b${picked}\\b`));
    await openPreference(page, language, "appearance");
    await capture(page, `${language}-theme-${picked}-after-reload`);
    await afterRequestsSoFar(page);
    expect(writes).toEqual([]);
  });
}
