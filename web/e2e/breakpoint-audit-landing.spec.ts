import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { test, type Page } from "@playwright/test";
import { FREEZE_CSS } from "./support/breakpoint-fixture";

/**
 * Capture pass for the signed-out landing surfaces.
 *
 * Split from `breakpoint-audit.spec.ts` because these only render with mock
 * auth off; see `breakpoint-audit-landing.playwright.config.ts`. Asserts
 * nothing. Run with:
 *   bunx playwright test -c e2e/breakpoint-audit-landing.playwright.config.ts
 */

const OUT_DIR = join(
  __dirname,
  "..",
  "..",
  "docs",
  "evidence",
  "breakpoint-audit",
);

const BANDS = {
  390: { width: 390, height: 844 },
  720: { width: 720, height: 1024 },
  1024: { width: 1024, height: 800 },
} as const;

type Band = keyof typeof BANDS;

async function capture(page: Page, name: string) {
  const base = join(OUT_DIR, name);
  await mkdir(dirname(base), { recursive: true });
  await page.addStyleTag({ content: FREEZE_CSS });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${base}.png` });
  await writeFile(
    `${base}.txt`,
    await page.evaluate(() => document.body.innerText).catch(() => ""),
    "utf8",
  );
}

async function open(
  page: Page,
  band: Band,
  url: string,
  language: "en" | "es-419" = "en",
  theme: "dark" | "light" = "dark",
) {
  await page.setViewportSize(BANDS[band]);
  await page.emulateMedia({ colorScheme: theme });
  await page.addInitScript(
    ([lang, storedTheme]) => {
      window.localStorage.setItem("i18nextLng", lang);
      window.localStorage.setItem("argus-theme", storedTheme);
    },
    [language, theme],
  );
  // No backend in this config, so every call fails the way a cold visitor's
  // would rather than hanging the page.
  await page.route("**/api/v1/**", (route) =>
    route.fulfill({
      status: 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: "unauthenticated" }),
    }),
  );
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await page.addStyleTag({ content: FREEZE_CSS });
  await page.waitForTimeout(1_200);
}

for (const band of [390, 720, 1024] as Band[]) {
  test(`landing surfaces at ${band}`, async ({ page }) => {
    await open(page, band, "/");
    await capture(page, `guest/entry-${band}-en-dark`);

    await open(page, band, "/", "es-419");
    await capture(page, `guest/entry-${band}-es-dark`);

    await open(page, band, "/", "en", "light");
    await capture(page, `guest/entry-${band}-en-light`);
  });
}
