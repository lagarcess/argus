import { mkdir, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { test, type Page } from "@playwright/test";
import {
  FREEZE_CSS,
  installBreakpointFixture,
  type Account,
  type Language,
  type Theme,
  type UsageState,
} from "./support/breakpoint-fixture";

/**
 * Capture pass for the breakpoint audit.
 *
 * This spec asserts nothing. It walks every guest and signed-in surface at the
 * DESIGN.md section 8 bands and writes a PNG plus the rendered text of each
 * capture, because reading the text is what catches clipping and duplication
 * that a passing assertion does not. Enforcement lives in
 * `breakpoint-baselines.spec.ts`; this file is the evidence the audit is read
 * from. Run with:
 *   bunx playwright test e2e/breakpoint-audit.spec.ts
 */

const OUT_DIR = join(
  __dirname,
  "..",
  "..",
  "docs",
  "evidence",
  "breakpoint-audit",
);

/* Taken inside each band rather than on its boundary, so a stop that moved by a
   pixel still shows up here. */
const BANDS = {
  390: { width: 390, height: 844 },
  720: { width: 720, height: 1024 },
  1024: { width: 1024, height: 800 },
} as const;

type Band = keyof typeof BANDS;

type Ctx = {
  account?: Account;
  language?: Language;
  theme?: Theme;
  usage?: UsageState;
  emptyChat?: boolean;
};

async function capture(page: Page, name: string) {
  const base = join(OUT_DIR, name);
  await mkdir(dirname(base), { recursive: true });
  await page.addStyleTag({ content: FREEZE_CSS });
  await page.waitForTimeout(400);
  await page.screenshot({ path: `${base}.png`, fullPage: false });
  const text = await page
    .evaluate(() => document.body.innerText)
    .catch(() => "");
  await writeFile(`${base}.txt`, text, "utf8");
}

async function open(page: Page, band: Band, url: string, ctx: Ctx = {}) {
  await page.setViewportSize(BANDS[band]);
  await page.emulateMedia({ colorScheme: ctx.theme ?? "dark" });
  await installBreakpointFixture(page, ctx);
  await page.goto(url, { waitUntil: "networkidle" });
  // Dev-only chrome sits in the same corner as the header menu and swallows its
  // clicks, so it goes before any interaction, not just before a capture.
  await page.addStyleTag({ content: FREEZE_CSS });
  await page.waitForTimeout(700);
}

/** Below 720 the drawer holds what the rail holds from tablet up. */
async function openDrawerIfNarrow(page: Page, band: Band) {
  if (band >= 720) return;
  const trigger = page.getByTestId("chat-shell-menu-trigger");
  if (await trigger.count()) {
    await trigger.click();
    await page.waitForTimeout(500);
  }
}

async function openSearch(page: Page, band: Band) {
  await openDrawerIfNarrow(page, band);
  const search = page.getByRole("button", { name: /^(search|buscar)$/i }).first();
  if (await search.count()) {
    await search.click();
    await page.waitForTimeout(700);
  }
}

async function openSettings(page: Page, band: Band, label = /^(settings|configuración|ajustes)$/i) {
  await openDrawerIfNarrow(page, band);
  const trigger = page.getByRole("button", { name: label }).first();
  if (await trigger.count()) {
    await trigger.click();
    await page.waitForTimeout(600);
  }
}

async function clickByName(page: Page, name: RegExp) {
  const target = page.getByRole("button", { name }).first();
  if (!(await target.count())) return false;
  try {
    await target.click({ timeout: 4_000 });
  } catch {
    // A panel left open by the previous step swallows the click; the audit
    // should record what it can rather than abandoning the whole band.
    return false;
  }
  await page.waitForTimeout(600);
  return true;
}

/** Modals stack, and one left open intercepts every later click in the band. */
async function dismissDialogs(page: Page) {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (!(await page.locator('[role="dialog"]').count())) return;
    await page.keyboard.press("Escape");
    await page.waitForTimeout(350);
  }
}

const ALL_BANDS: Band[] = [390, 720, 1024];

/* ---------------------------------------------------------------- guest --- */

test.describe("guest surfaces", () => {
  for (const band of ALL_BANDS) {
    test(`guest at ${band}`, async ({ page }) => {
      // An established session redirects `/` straight to `/chat`, so the
      // landing surface is only reachable with the redirect suppressed.
      await open(page, band, "/?preview=true", { account: "guest" });
      await capture(page, `guest/entry-${band}-en-dark`);

      await open(page, band, "/chat", { account: "guest", emptyChat: true });
      await capture(page, `guest/empty-chat-${band}-en-dark`);

      // A first question typed but not sent: the composer at its tallest.
      const composer = page
        .locator("textarea, [contenteditable='true']")
        .first();
      if (await composer.count()) {
        await composer.click();
        await composer.fill(
          "Compare Apple with SPY over the last twelve months and show me the drawdown",
        );
        await page.waitForTimeout(500);
        await capture(page, `guest/first-question-${band}-en-dark`);
      }

      await open(page, band, "/chat?conversation=conversation-alpha", {
        account: "guest",
      });
      await capture(page, `guest/conversation-${band}-en-dark`);

      const confirm = page.locator('button[class*="tablet:min-h-9"]').first();
      if (await confirm.count()) {
        await confirm.scrollIntoViewIfNeeded();
        await page.waitForTimeout(400);
        await capture(page, `guest/confirmation-card-${band}-en-dark`);
      }

      // Scroll back up to the result card, which sits above the confirmation.
      await page.mouse.wheel(0, -4000);
      await page.waitForTimeout(500);
      await capture(page, `guest/result-card-${band}-en-dark`);
    });

    test(`guest dossier and exhaustion at ${band}`, async ({ page }) => {
      await open(page, band, "/chat?conversation=conversation-alpha", {
        account: "guest",
      });
      await openSearch(page, band);
      await capture(page, `guest/search-${band}-en-dark`);

      const row = page.locator("[data-palette-row-index]").first();
      if (await row.count()) {
        await row.click();
        await page.waitForTimeout(700);
        await capture(page, `guest/dossier-${band}-en-dark`);
      }

      await open(page, band, "/chat?conversation=conversation-alpha", {
        account: "guest",
        usage: "exhausted",
      });
      await capture(page, `guest/exhausted-${band}-en-dark`);

      /* A guest cannot open a second conversation, so New chat is the gated
         action that raises the conversion prompt without needing a live turn. */
      await open(page, band, "/chat?conversation=conversation-alpha", {
        account: "guest",
      });
      await openDrawerIfNarrow(page, band);
      if (await clickByName(page, /^(new chat|chat nuevo|nuevo chat)$/i)) {
        await capture(page, `guest/signup-prompt-${band}-en-dark`);
      }

      await open(page, band, "/chat", { account: "guest", emptyChat: true });
      if (await clickByName(page, /^(sign in|iniciar sesión)$/i)) {
        await capture(page, `guest/sign-in-cta-${band}-en-dark`);
      }
    });
  }
});

/* ------------------------------------------------------------ signed in --- */

test.describe("signed-in surfaces", () => {
  for (const band of ALL_BANDS) {
    test(`chat and recents at ${band}`, async ({ page }) => {
      await open(page, band, "/chat", { emptyChat: true });
      await capture(page, `signed-in/empty-chat-${band}-en-dark`);

      await open(page, band, "/chat?conversation=conversation-alpha", {});
      await capture(page, `signed-in/conversation-${band}-en-dark`);

      await openDrawerIfNarrow(page, band);
      await capture(page, `signed-in/recents-${band}-en-dark`);

      await open(page, band, "/chat?conversation=conversation-alpha", {});
      await openSearch(page, band);
      await capture(page, `signed-in/search-${band}-en-dark`);
    });

    /* The settings menu is an accordion whose sections push sub-views and
       modals, so each leaf is reached from a fresh open rather than by
       unwinding the previous one. */
    test(`settings panels at ${band}`, async ({ page }) => {
      // Each leaf is reached from a fresh load, so this walk is a dozen boots.
      test.setTimeout(180_000);
      await open(page, band, "/chat", { emptyChat: true });
      await openSettings(page, band);
      await capture(page, `signed-in/settings-main-${band}-en-dark`);

      for (const [section, name] of [
        ["profile", /^(profile|perfil)$/i],
        ["data", /^(data controls|controles de datos)$/i],
        ["preferences", /^(preferences|preferencias)$/i],
        ["help-legal", /^(help & legal|ayuda y legal|ayuda y aviso legal)$/i],
      ] as const) {
        await open(page, band, "/chat", { emptyChat: true });
        await openSettings(page, band);
        if (await clickByName(page, name)) {
          await capture(page, `signed-in/settings-${section}-${band}-en-dark`);
        }
      }

      for (const [leaf, name] of [
        ["archived", /archived chats|chats archivados/i],
        ["deleted", /recently deleted|eliminados recientemente/i],
        ["security", /^(security|seguridad)$/i],
        ["usage", /^(usage|uso)$/i],
      ] as const) {
        await open(page, band, "/chat", { emptyChat: true });
        await openSettings(page, band);
        if (!(await clickByName(page, /^(data controls|controles de datos)$/i)))
          continue;
        if (await clickByName(page, name)) {
          await capture(page, `signed-in/settings-${leaf}-${band}-en-dark`);
        }
        await dismissDialogs(page);
      }

      for (const [leaf, name] of [
        ["language", /^(app language|idioma de la app|idioma)$/i],
        ["appearance", /^(appearance|apariencia)$/i],
        ["sidebar", /^(sidebar|barra lateral)$/i],
      ] as const) {
        await open(page, band, "/chat", { emptyChat: true });
        await openSettings(page, band);
        if (!(await clickByName(page, /^(preferences|preferencias)$/i))) continue;
        if (await clickByName(page, name)) {
          await capture(page, `signed-in/settings-${leaf}-${band}-en-dark`);
        }
        await dismissDialogs(page);
      }
    });

    /* The profile menu is the `settings-profile` capture above; this test
       carries the two allowance states the healthy fixture never reaches. */
    test(`usage states at ${band}`, async ({ page }) => {
      await open(page, band, "/chat", { emptyChat: true, usage: "error" });
      await openSettings(page, band);
      if (await clickByName(page, /^(data controls|controles de datos)$/i)) {
        if (await clickByName(page, /^(usage|uso)$/i)) {
          await capture(page, `signed-in/usage-error-${band}-en-dark`);
        }
      }

      await open(page, band, "/chat", { emptyChat: true, usage: "nearly_out" });
      await openSettings(page, band);
      if (await clickByName(page, /^(data controls|controles de datos)$/i)) {
        if (await clickByName(page, /^(usage|uso)$/i)) {
          await capture(page, `signed-in/usage-nearly-out-${band}-en-dark`);
        }
      }

    });

    /*
     * A persisted result card hydrates from a run fetch rather than from
     * message metadata, so it cannot be stubbed onto a transcript message. The
     * committed playground renders the same component from static fixtures,
     * which is what the width behaviour is read from here.
     */
    test(`result card fixtures at ${band}`, async ({ page }) => {
      await open(page, band, "/dev/result-card", {});
      await capture(page, `signed-in/result-card-playground-${band}-en-dark`);

      for (const fixture of [
        "positive-single-symbol",
        "negative-single-symbol",
        "benchmark-underperformance-positive",
        "modeled-execution-costs",
      ]) {
        const card = page.getByTestId(`result-card-fixture-${fixture}`).first();
        if (!(await card.count())) continue;
        await card.scrollIntoViewIfNeeded();
        await page.waitForTimeout(300);
        const base = join(OUT_DIR, `signed-in/result-card-${fixture}-${band}-en-dark`);
        await mkdir(dirname(base), { recursive: true });
        await card.screenshot({ path: `${base}.png` });
        await writeFile(`${base}.txt`, await card.innerText(), "utf8");
      }
    });

    /*
     * The cross pass. Crossing every view by language and theme is ~300
     * captures that nobody reads, so it is spent only where copy length or
     * theming actually breaks things: the metric table, the allowance meters
     * and their status chips, the truncated conversation titles, and the
     * five-action confirmation row.
     */
    test(`language and theme cross at ${band}`, async ({ page }) => {
      test.setTimeout(180_000);
      for (const [language, theme] of [
        ["es-419", "dark"],
        ["en", "light"],
        ["es-419", "light"],
      ] as const) {
        const suffix = `${band}-${language === "es-419" ? "es" : "en"}-${theme}`;

        await open(page, band, "/chat?conversation=conversation-alpha", {
          language,
          theme,
        });
        await capture(page, `cross/conversation-${suffix}`);

        await openSearch(page, band);
        await capture(page, `cross/search-${suffix}`);

        const row = page.locator("[data-palette-row-index]").first();
        if (await row.count()) {
          await row.click();
          await page.waitForTimeout(700);
          await capture(page, `cross/dossier-${suffix}`);
        }

        await open(page, band, "/chat", {
          emptyChat: true,
          language,
          theme,
          usage: "nearly_out",
        });
        await openSettings(page, band);
        if (await clickByName(page, /^(data controls|controles de datos)$/i)) {
          if (await clickByName(page, /^(usage|uso)$/i)) {
            await capture(page, `cross/usage-${suffix}`);
          }
        }
      }
    });

    test(`legal and auth at ${band}`, async ({ page }) => {
      await open(page, band, "/privacy", {});
      await capture(page, `chrome/privacy-${band}-en-dark`);

      await open(page, band, "/terms", {});
      await capture(page, `chrome/terms-${band}-en-dark`);

      await open(page, band, "/?auth=login", {});
      await capture(page, `chrome/login-${band}-en-dark`);

      await open(page, band, "/?auth=signup", {});
      await capture(page, `chrome/signup-${band}-en-dark`);

      await open(page, band, "/?auth=request", {});
      await capture(page, `chrome/request-access-${band}-en-dark`);

      await open(page, band, "/auth/forgot-password", {});
      await capture(page, `chrome/forgot-password-${band}-en-dark`);

      await open(page, band, "/auth/recovery", {});
      await capture(page, `chrome/recovery-${band}-en-dark`);

      await open(page, band, "/account/security", {});
      await capture(page, `chrome/account-security-${band}-en-dark`);
    });
  }
});
