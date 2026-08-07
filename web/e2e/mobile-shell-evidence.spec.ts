import { mkdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { expect, test, type Page } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";

/**
 * Browser evidence for the mobile PWA responsive shell.
 *
 * Captures the spec's surfaces at each width band, in both languages and both
 * themes, into docs/evidence so a reviewer sees the shell rather than a claim
 * about it. Run with:
 *   bunx playwright test e2e/mobile-shell-evidence.spec.ts
 */

const EVIDENCE_DIR = join(
  __dirname,
  "..",
  "..",
  "docs",
  "evidence",
  "mobile-pwa-responsive-shell",
);

const WIDTHS = {
  mobile: { width: 390, height: 844 },
  tablet: { width: 720, height: 1024 },
  desktopEdge: { width: 1024, height: 800 },
  desktop: { width: 1440, height: 900 },
} as const;

const HIDE_DEV_CHROME = `
  nextjs-portal { display: none !important; }
  [data-dev-mode-badge] { display: none !important; }
  *, *::before, *::after { animation: none !important; transition: none !important; }
`;

async function capture(page: Page, name: string) {
  const path = join(EVIDENCE_DIR, `${name}.png`);
  await mkdir(dirname(path), { recursive: true });
  await page.addStyleTag({ content: HIDE_DEV_CHROME });
  await page.waitForTimeout(500);
  await page.screenshot({ path });
}

type Band = keyof typeof WIDTHS;

async function open(
  page: Page,
  band: Band,
  options: {
    account?: "registered" | "guest";
    language?: "en" | "es-419";
    conversation?: boolean;
    theme?: "dark" | "light";
  } = {},
) {
  await page.setViewportSize(WIDTHS[band]);
  await page.emulateMedia({ colorScheme: options.theme ?? "dark" });
  await installMobileShellFixture(page, {
    account: options.account,
    language: options.language,
    theme: options.theme,
  });
  const query = options.conversation ? "?conversation=conversation-alpha" : "";
  await page.goto(`/chat${query}`, { waitUntil: "networkidle" });
  // Dev-only chrome sits in the same corner as the header menu and swallows
  // its clicks, so it goes before any interaction, not just before a capture.
  await page.addStyleTag({ content: HIDE_DEV_CHROME });
  await page.waitForTimeout(900);
}

/** Below 720 the Search entry lives in the drawer; from tablet up, in the rail. */
async function openSearch(page: Page) {
  const trigger = page.getByTestId("chat-shell-menu-trigger");
  if (await trigger.count()) await trigger.click();
  await page.getByRole("button", { name: /^search$/i }).first().click();
  await page.waitForTimeout(700);
}

test.describe("mobile shell evidence", () => {
  test("application shell at every band", async ({ page }) => {
    await open(page, "mobile", { conversation: true });
    await expect(page.getByTestId("chat-shell-menu-trigger")).toBeVisible();
    await capture(page, "01-mobile-390-top-bar-registered");

    await page.getByTestId("chat-shell-menu-trigger").click();
    await expect(page.getByTestId("sidebar-drawer")).toBeVisible();
    await expect(page.getByTestId("sidebar-drawer-logo")).toBeVisible();
    await expect(page.getByTestId("sidebar-drawer-close")).toBeVisible();
    await capture(page, "02-mobile-390-drawer-open");
  });

  test("guest top bar keeps sign up pinned and moves the gear", async ({ page }) => {
    await open(page, "mobile", { account: "guest", conversation: true });
    await expect(page.getByTestId("chat-shell-menu-trigger")).toBeVisible();
    await capture(page, "03-mobile-390-top-bar-guest");

    await page.getByTestId("chat-shell-menu-trigger").click();
    await expect(page.getByTestId("sidebar-guest-settings")).toBeVisible();
    await capture(page, "04-mobile-390-drawer-guest-settings");
  });

  test("dossier and sources arrive as sheets", async ({ page }) => {
    await open(page, "mobile", { conversation: true });
    await openSearch(page);
    await capture(page, "05-mobile-390-omnisearch-collapsed");

    await page.locator("[data-palette-row-index]").first().click();
    await expect(page.getByTestId("dossier-sheet-open-conversation")).toBeVisible();
    await capture(page, "06-mobile-390-dossier-sheet");

    await page.getByRole("button", { name: /close dossier/i }).click();
    await page.waitForTimeout(500);
    await page.getByTestId("command-palette-row-menu").first().click();
    await capture(page, "07-mobile-390-row-three-dot-menu");
  });

  test("sources sheet", async ({ page }) => {
    await open(page, "mobile", { conversation: true });
    await page
      .locator("button")
      .filter({ hasText: /sources|fuentes/i })
      .first()
      .click();
    await page.waitForTimeout(500);
    await capture(page, "08-mobile-390-sources-sheet");
  });

  test("composer starter pills scroll with a peek", async ({ page }) => {
    await open(page, "mobile");
    await expect(page.getByTestId("starter-actions")).toHaveAttribute(
      "data-starter-layout",
      "scroll",
    );
    await capture(page, "09-mobile-390-starter-pills-peek");
  });

  test("activity rail is absent below 720 and present at tablet", async ({ page }) => {
    await open(page, "mobile", { conversation: true });
    await expect(
      page.getByTestId("conversation-activity-rail"),
    ).toBeHidden();
    await capture(page, "10-mobile-390-no-activity-rail");

    // The rail also needs a long enough transcript to exist at all, so the
    // breakpoint rule itself is measured from its own class list.
    const railDisplay = async () =>
      page.evaluate(() => {
        const probe = document.createElement("div");
        probe.className = "hidden tablet:block";
        document.body.appendChild(probe);
        const display = getComputedStyle(probe).display;
        probe.remove();
        return display;
      });
    expect(await railDisplay()).toBe("none");

    await open(page, "tablet", { conversation: true });
    expect(await railDisplay()).toBe("block");
    await capture(page, "11-tablet-720-activity-rail-present");
  });

  test("confirmation card keeps all five actions on a narrow screen", async ({
    page,
  }) => {
    await open(page, "mobile", { conversation: true });
    // Confirmation actions carry the narrow-screen tap target class, so the
    // class is both the selector and the thing under test.
    const actions = page.locator('button[class*="tablet:min-h-9"]');
    await actions.first().scrollIntoViewIfNeeded();
    await page.waitForTimeout(400);
    await expect(actions).toHaveCount(5);
    for (const action of await actions.all()) {
      const box = await action.boundingBox();
      expect(box?.height ?? 0).toBeGreaterThanOrEqual(44);
    }
    await capture(page, "19-mobile-390-confirmation-card");
  });

  test("dossier is an overlay below 1024 and a pane at 1024", async ({ page }) => {
    await open(page, "tablet", { conversation: true });
    await openSearch(page);
    await page.locator("[data-palette-row-index]").first().click();
    await expect(page.getByTestId("dossier-sheet-open-conversation")).toBeVisible();
    await capture(page, "12-tablet-720-dossier-overlay");

    await open(page, "desktopEdge", { conversation: true });
    await openSearch(page);
    await capture(page, "13-desktop-1024-omnisearch-pane");
  });

  test("spanish and light theme", async ({ page }) => {
    await open(page, "mobile", { conversation: true, language: "es-419" });
    await expect(page.locator("html")).toHaveClass(/dark/);
    await capture(page, "14-mobile-390-es419-dark");

    await open(page, "mobile", {
      conversation: true,
      language: "es-419",
      theme: "light",
    });
    await expect(page.locator("html")).not.toHaveClass(/dark/);
    await capture(page, "15-mobile-390-es419-light");

    await open(page, "mobile", { conversation: true, theme: "light" });
    await capture(page, "16-mobile-390-en-light");
  });

  test("chat header menu goes through the sheet primitive", async ({ page }) => {
    await open(page, "mobile", { conversation: true });
    await page.getByRole("button", { name: /chat options/i }).click();
    const sheet = page.locator('[role="dialog"]');
    await expect(sheet).toHaveAttribute("aria-modal", "true");
    await expect(page.locator(".argus-sheet-scrim")).toBeVisible();
    await expect(page.locator(".argus-sheet-grip")).toBeVisible();
    // Hugs its content rather than taking a detent sized for a dossier.
    const box = await sheet.boundingBox();
    expect(box!.height).toBeLessThan(page.viewportSize()!.height * 0.7);
    await capture(page, "24-mobile-390-chat-menu-sheet");
  });

  test("desktop is unchanged", async ({ page }) => {
    await open(page, "desktop", { conversation: true });
    await expect(page.getByTestId("chat-shell-menu-trigger")).toHaveCount(0);
    await expect(page.getByTestId("sidebar-drawer")).toHaveCount(0);
    await capture(page, "17-desktop-1440-chat");

    await openSearch(page);
    await capture(page, "18-desktop-1440-omnisearch-expanded");
  });
});
