import { expect, test, type Page, type Locator } from "@playwright/test";
import { FREEZE_CSS, type Account, type Language } from "./support/breakpoint-fixture";
import { openFixture, openSettings, type Cell } from "./support/menu-settings-fixture";

const WIDTHS = [390, 719, 720, 1023, 1024, 1280] as const;
const ACCOUNTS: Account[] = ["guest", "registered"];
const LANGUAGES: Language[] = ["en", "es-419"];

async function capture(page: Page, cell: Cell, surface: string, marker: Locator) {
  await expect(marker).toBeVisible();
  await expect(page).toHaveScreenshot(`${surface}-${cell.account}-${cell.language}-${cell.width}.png`);
}

async function openSearch(page: Page, width: number) {
  if (width < 720) await page.getByTestId("chat-shell-menu-trigger").click();
  await page.getByRole("button", { name: /^(search|buscar)$/i }).first().click();
  await expect(page.locator("[data-palette-row-index]").first()).toBeVisible();
}

async function reload(page: Page) {
  await page.reload({ waitUntil: "networkidle" });
  await page.addStyleTag({ content: FREEZE_CSS });
}

for (const width of WIDTHS) for (const account of ACCOUNTS) for (const language of LANGUAGES) {
  const cell = { width, account, language };
  test(`${account} ${language} at ${width}: menu form`, async ({ page }) => {
    await openFixture(page, cell);
    await expect(page.getByTestId("chat-shell-menu-trigger")).toHaveCount(width < 720 ? 1 : 0);
    const headerTrigger = page.getByRole("button", { name: /^(chat options|opciones de chat)$/i });
    if (account === "registered") {
      await headerTrigger.click();
      await expect(page.locator(".argus-sheet")).toHaveCount(width < 720 ? 1 : 0);
      await capture(page, cell, "header-menu", page.getByRole("menuitem", { name: /rename|renombrar/i }));
      await page.keyboard.press("Escape");
      await expect(headerTrigger).toBeFocused();
    } else {
      await expect(headerTrigger).toHaveCount(0);
      await capture(page, cell, "guest-shell", page.getByTestId("chat-input"));
    }
    await openSettings(page, cell);
    await expect(page.locator(".argus-sheet")).toHaveCount(width < 720 ? 1 : 0);
    await capture(page, cell, "settings", account === "guest"
      ? page.getByRole("menuitem", { name: /^(language|idioma)$/i })
      : page.getByRole("button", { name: /^(preferences|preferencias)$/i }));
    if (account === "registered") {
      await page.getByRole("button", { name: /^(preferences|preferencias)$/i }).click();
      await page.getByRole("button", { name: /^(app language|idioma de la app)$/i }).click();
    } else {
      await page.getByRole("menuitem", { name: /^(language|idioma)$/i }).click();
    }
    await expect(page.locator(".argus-sheet")).toHaveCount(width < 720 ? 1 : 0);
    await capture(page, cell, "language", page.getByRole("dialog").last().getByText("Español", { exact: true }));
  });

  test(`${account} ${language} at ${width}: Search form and dossier exception`, async ({ page }) => {
    await openFixture(page, cell);
    await openSearch(page, width);
    const row = page.locator("[data-palette-row-index]").first();
    if (account === "registered") {
      const menu = row.getByTestId("command-palette-row-menu");
      if (width < 720) {
        await menu.click();
        await capture(page, cell, "search-row-menu", page.getByRole("menu").last());
        await page.keyboard.press("Escape");
        await expect(menu).toBeFocused();
      } else {
        await expect(menu).toBeHidden();
        await row.hover();
        await expect(row.locator(".argus-row-hover-actions")).toBeVisible();
      }
    }
    await row.hover();
    await capture(page, cell, "search", row);
    // Wider Search previews on hover; activation opens the conversation.
    if (width < 1024) await row.click();
    const dossierAction = page.getByTestId("dossier-sheet-open-conversation");
    await expect(dossierAction).toHaveCount(width < 1024 ? 1 : 0);
    await expect(page.locator(".argus-sheet")).toHaveCount(width < 1024 ? 1 : 0);
    await capture(page, cell, "dossier", width < 1024
      ? dossierAction
      : page.getByRole("button", { name: /retest with current data|volver a probar con datos actuales/i }).first());
  });

  test(`${account} ${language} at ${width}: source panel form`, async ({ page }) => {
    await openFixture(page, cell);
    await page.route("**/api/v1/conversations/*/messages*", (route) => route.fulfill({
      json: { items: [{
        id: "source-message", role: "assistant", created_at: "2026-09-14T12:00:00Z",
        content: language === "en" ? "Sources for this example." : "Fuentes de este ejemplo.",
        metadata: { discovery: {
          schema_version: "argus_asset_discovery/v1", kind: "asset_discovery",
          relationship: "peer", query_summary: "Apple peers", retrieved_at: "2026-09-14T12:00:00Z",
          unverified_names: [], can_request_search: false,
          candidates: [{ symbol: "MSFT", name: "Microsoft", asset_class: "equity",
            reason_text: language === "en" ? "Technology peer" : "Empresa tecnológica similar", source_indices: [0] }],
          sources: [{ url: "https://example.com/earnings", domain: "example.com",
            title: language === "en" ? "Quarterly earnings summary" : "Resumen de resultados trimestrales", source_date: "2026-09-11" }],
        } },
      }], next_cursor: null },
    }));
    await reload(page);
    await page.getByRole("button", { name: /1 source|1 fuente/i }).click();
    await expect(page.locator(".argus-sheet")).toHaveCount(width < 720 ? 1 : 0);
    await capture(page, cell, "sources", page.getByRole("dialog").getByRole("link", { name: /quarterly earnings|resultados trimestrales/i }));
  });
}

test.describe("tablet touch", () => {
  test.use({ hasTouch: true });
  for (const width of [720, 1023]) {
    test(`clickable popovers and row actions at ${width}`, async ({ page }) => {
      const cell: Cell = { width, account: "registered", language: "en" };
      await openFixture(page, cell);
      await openSettings(page, cell);
      await expect(page.locator(".argus-sheet")).toHaveCount(0);
      await page.getByRole("button", { name: /^preferences$/i }).tap();
      await expect(page.getByRole("button", { name: /^appearance$/i })).toBeVisible();
      await capture(page, cell, "touch-preferences", page.getByRole("button", { name: /^appearance$/i }));
      await reload(page);
      await openSearch(page, width);
      const menu = page.getByTestId("command-palette-row-menu").first();
      await expect(menu).toBeVisible();
      const box = await menu.boundingBox();
      expect(box!.width).toBeGreaterThanOrEqual(44);
      expect(box!.height).toBeGreaterThanOrEqual(44);
      await menu.tap();
      await capture(page, cell, "touch-search-row", page.getByRole("menu").last());
    });
  }
});

test("settings reopens in the current form after shell resize", async ({ page }) => {
  const cell: Cell = { width: 720, account: "registered", language: "en" };
  await openFixture(page, cell);
  await openSettings(page, cell);
  for (const width of [719, 720, 1023, 1024]) {
    await page.setViewportSize({ width, height: 900 });
    if (width === 719 || width === 720) {
      // Switching rail/drawer remounts the sidebar and closes its menu.
      await expect(page.getByRole("button", { name: /^preferences$/i })).toHaveCount(0);
      await openSettings(page, { ...cell, width });
    }
    await expect(page.locator(".argus-sheet")).toHaveCount(width < 720 ? 1 : 0);
    await expect(page.getByRole("button", { name: /^preferences$/i })).toBeVisible();
  }
});

for (const width of [720, 1023, 1024]) {
  test(`plain conversation preview uses the dossier container at ${width}`, async ({ page }) => {
    const cell: Cell = { width, account: "registered", language: "en" };
    await openFixture(page, cell);
    await openSearch(page, width);
    const row = page.locator("[data-palette-row-index]").nth(1);
    await row.hover();
    if (width < 1024) await row.click();
    const preview = page.getByRole("region", { name: "Preview", exact: true });
    await expect(page.locator(".argus-sheet")).toHaveCount(width < 1024 ? 1 : 0);
    await capture(page, cell, "conversation-preview", preview);
  });
}
