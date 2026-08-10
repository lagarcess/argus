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

/** The landing surface, in both languages. */
const ENTRY_PROOF =
  /Test an investing idea against history|Prueba una idea de inversión con datos históricos/i;

/**
 * The guest workspace notice, which only renders once a guest session exists.
 */
const GUEST_SESSION = /Temporary chat · available until|Chat temporal · disponible hasta/i;

/**
 * Same rule as the audit spec: a capture proves the surface it is named for.
 *
 * This one needs a negative as well as a positive. `/` hands off to `/chat`
 * even with no session, and the signed-out entry renders the same copy as the
 * guest empty chat that the audit spec captures, so the entry text alone would
 * accept either. What separates them is that the signed-out visitor has no
 * guest workspace yet, and so no temporary-chat notice. Asserting the path
 * instead would be wrong: the handoff to `/chat` is the product behaving
 * correctly, not the failure this guard is for.
 */
async function capture(page: Page, name: string, proof: RegExp) {
  const base = join(OUT_DIR, name);
  await mkdir(dirname(base), { recursive: true });
  await page.addStyleTag({ content: FREEZE_CSS });
  await page.waitForTimeout(400);
  const text = await page
    .evaluate(() => document.body.innerText)
    .catch(() => "");
  if (GUEST_SESSION.test(text)) {
    throw new Error(
      `Capture "${name}" is named for the signed-out entry, but a guest ` +
        `session notice is on screen, so this is the guest empty chat instead.`,
    );
  }
  if (!proof.test(text)) {
    throw new Error(
      `Capture "${name}" does not contain the surface it is named for.\n` +
        `Expected to match ${proof}\nRendered text was:\n${text.slice(0, 800)}`,
    );
  }
  await page.screenshot({ path: `${base}.png` });
  await writeFile(`${base}.txt`, text, "utf8");
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
    await capture(page, `guest/entry-${band}-en-dark`, ENTRY_PROOF);

    await open(page, band, "/", "es-419");
    await capture(page, `guest/entry-${band}-es-dark`, ENTRY_PROOF);

    await open(page, band, "/", "en", "light");
    await capture(page, `guest/entry-${band}-en-light`, ENTRY_PROOF);
  });
}
