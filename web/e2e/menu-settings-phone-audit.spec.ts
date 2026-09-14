import { expect, test, type Locator, type Page } from "@playwright/test";
import { appendFileSync } from "node:fs";
import path from "node:path";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";
import { FREEZE_CSS, type Account, type Language } from "./support/breakpoint-fixture";
import { openFixture, openSettings, type Cell } from "./support/menu-settings-fixture";

// The labels derive from the shipped locale catalogs, including nested picker
// labels. Nothing in this walk submits a mutation or creates a model turn.
function label(language: Language, key: string): string {
  let value: unknown = language === "en" ? en : es;
  for (const part of key.split(".")) value = (value as Record<string, unknown>)[part];
  if (typeof value !== "string") throw new Error(`Missing locale label: ${key}`);
  return value;
}
function button(page: Page, cell: Cell, key: string) {
  return page.getByRole("button", { name: label(cell.language, key), exact: true }).last();
}
type Surface = { name: string; path: string[]; marker?: string; optional?: boolean };
const DATA = "settings.data.title";
const PREFS = "settings.preferences.title";
const FEEDBACK = "feedback.eyebrow";
const REGISTERED: Surface[] = [
  { name: "settings-root", path: [], marker: "settings.profile.title" },
  { name: "profile", path: ["settings.profile.title"] },
  { name: "data", path: [DATA], marker: "settings.data.archived_chats" },
  { name: "preferences", path: [PREFS], marker: "settings.app.appearance" },
  { name: "help", path: ["settings.help.title"], marker: "settings.help.terms" },
  { name: "feedback-menu", path: [FEEDBACK], marker: "feedback.type.bug" },
  { name: "archived", path: [DATA, "settings.data.archived_chats"] },
  { name: "deleted", path: [DATA, "settings.data.recently_deleted"] },
  { name: "usage", path: [DATA, "settings.data.usage"] },
  { name: "shared-links", path: [DATA, "settings.data.shared_links"], optional: true },
  { name: "delete-all-confirm", path: [DATA, "settings.data.delete_all_conversations"] },
  { name: "occluded-account-delete", path: [DATA, "settings.profile.delete_account"] },
  { name: "appearance", path: [PREFS, "settings.app.appearance"] },
  { name: "language", path: [PREFS, "settings.app.language"] },
  { name: "country", path: [PREFS, "settings.app.home_country"] },
  ...["bug", "feature", "general"].map((kind) => ({
    name: `feedback-${kind}`, path: [FEEDBACK, `feedback.type.${kind}`],
  })),
];
const GUEST: Surface[] = [
  { name: "settings-root", path: [], marker: "guest.shell.language" },
  { name: "language", path: ["guest.shell.language"] },
  { name: "feedback-general", path: ["guest.shell.feedback"] },
];

async function capture(page: Page, cell: Cell, name: string, marker: Locator) {
  await expect(marker).toBeVisible();
  const geometry = await page.locator('main, [role="dialog"], [role="alertdialog"], [role="menu"]').last().evaluate((surface) => {
    const rect = surface.getBoundingClientRect();
    const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
    return {
    width: surface.getBoundingClientRect().width,
    top: surface.getBoundingClientRect().top,
    overflow: surface.scrollWidth > surface.clientWidth,
    centerHitInside: hit !== null && surface.contains(hit),
    centerHitClass: hit?.className,
    centerHitZIndex: hit ? getComputedStyle(hit).zIndex : null,
    focusInside: surface.contains(document.activeElement),
    ancestorZIndices: [surface, surface.parentElement, surface.parentElement?.parentElement].filter((node): node is Element => node != null).map((node) => getComputedStyle(node).zIndex),
    smallControls: [...surface.querySelectorAll("button, a")].flatMap((node) => {
      const r = node.getBoundingClientRect();
      return r.width > 0 && r.height > 0 && (r.width < 44 || r.height < 44)
        ? [{ name: node.getAttribute("aria-label") ?? node.textContent?.trim(), width: r.width, height: r.height }]
        : [];
    }),
    };
  });
  await test.info().attach(`${name}-geometry`, { body: JSON.stringify(geometry, null, 2), contentType: "application/json" });
  appendFileSync(path.join(test.info().project.outputDir, "phone-geometry.jsonl"), `${JSON.stringify({ account: cell.account, language: cell.language, name, ...geometry })}\n`);
  await expect(page).toHaveScreenshot(`phone-${cell.account}-${cell.language}-${name}.png`);
}

for (const account of ["guest", "registered"] as Account[]) {
  for (const language of ["en", "es-419"] as Language[]) {
    const cell: Cell = { width: 390, account, language };
    test.describe(`phone audit ${account} ${language}`, () => {
      for (const surface of account === "guest" ? GUEST : REGISTERED) {
        test(surface.name, async ({ page }) => {
          await openFixture(page, cell);
          await openSettings(page, cell);
          for (const [index, key] of surface.path.entries()) {
            const target = page.getByRole("button", { name: label(language, key), exact: true })
              .or(page.getByRole("menuitem", { name: label(language, key), exact: true })).last();
            if (surface.optional && index === surface.path.length - 1) {
              test.skip(await target.count() === 0, "Feature is unavailable in this release fixture");
            }
            // The delete-account row includes explanatory text in its accessible name.
            if (key === "settings.profile.delete_account") {
              await page.getByRole("button", { name: new RegExp(`^${label(language, key)}`) }).click();
            } else await target.click();
          }
          const marker = surface.marker
            ? page.getByText(label(language, surface.marker), { exact: true }).filter({ visible: true }).last()
            : surface.name === "delete-all-confirm" ? page.getByRole("alertdialog")
              : surface.name === "occluded-account-delete" ? page.getByRole("dialog", { name: label(language, "settings.profile.request_deletion.title"), exact: true })
                : page.getByRole("dialog").last();
          if (surface.name === "occluded-account-delete") {
            const supportButton = marker.getByRole("button", { name: label(language, "settings.profile.request_deletion.contact_support"), exact: true });
            const hitTest = await supportButton.evaluate((control) => {
              const rect = control.getBoundingClientRect();
              const hit = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
              return { controlCovered: hit !== null && !control.contains(hit), coveringClass: hit?.className, coveringZIndex: hit ? getComputedStyle(hit).zIndex : null };
            });
            await test.info().attach("account-deletion-occlusion", { body: JSON.stringify(hitTest, null, 2), contentType: "application/json" });
            appendFileSync(path.join(test.info().project.outputDir, "phone-occlusion.jsonl"), `${JSON.stringify({ language, ...hitTest })}\n`);
          }
          await capture(page, cell, surface.name, marker);
        });
      }

      for (const kind of ["picker", "bug", "feature"] as const) {
        test(`feedback category ${kind}`, async ({ page }) => {
          await openFixture(page, cell);
          await openSettings(page, cell);
          if (account === "registered") {
            await button(page, cell, FEEDBACK).click();
            await button(page, cell, "feedback.type.general").click();
          } else await page.getByRole("menuitem", { name: label(language, "guest.shell.feedback"), exact: true }).click();
          await button(page, cell, "feedback.type.general").click();
          if (kind !== "picker") await button(page, cell, `feedback.type.${kind}`).click();
          await capture(page, cell, `feedback-category-${kind}`, kind === "picker"
            ? button(page, cell, "feedback.type.bug") : page.getByRole("dialog").last());
        });
      }

      if (account === "registered") {
        for (const destination of ["security", "terms", "privacy"] as const) {
          test(`settings route ${destination}`, async ({ page }) => {
            await openFixture(page, cell);
            await openSettings(page, cell);
            if (destination === "security") {
              await button(page, cell, DATA).click();
              await button(page, cell, "settings.data.security").click();
            } else {
              await button(page, cell, "settings.help.title").click();
              await page.getByRole("link", { name: label(language, `settings.help.${destination}`), exact: true }).click();
            }
            await expect(page).toHaveURL(new RegExp(destination === "security" ? "/account/security$" : `/${destination}$`));
            await page.addStyleTag({ content: FREEZE_CSS });
            await capture(page, cell, destination, page.getByRole("heading", { name: label(language, destination === "security" ? "account_security.title" : `legal.${destination}.title`), exact: true }));
          });
        }
        test("currency picker", async ({ page }) => {
          await openFixture(page, cell);
          await openSettings(page, cell);
          await button(page, cell, PREFS).click();
          await button(page, cell, "settings.app.home_country").click();
          await page.getByRole("button", { name: new RegExp(`^${label(language, "settings.app.currency")} `) }).click();
          await capture(page, cell, "currency", page.getByPlaceholder(label(language, "settings.app.search_currency")));
        });
        for (const picker of ["display-name", "preferred-name", "avatar", "profile-language"] as const) {
          test(`profile ${picker}`, async ({ page }) => {
            await openFixture(page, cell);
            await openSettings(page, cell);
            await button(page, cell, "settings.profile.title").click();
            const dialog = page.getByRole("dialog", { name: label(language, "settings.profile.title"), exact: true });
            let marker: Locator;
            if (picker === "display-name") {
              await button(page, cell, "settings.profile.edit_display_name").click();
              marker = dialog.getByRole("textbox");
            } else if (picker === "preferred-name") {
              await page.locator("#argus-profile-preferred-name").click();
              marker = dialog.getByRole("textbox");
            } else if (picker === "avatar") {
              await page.locator("[data-avatar-theme-trigger]").click();
              marker = dialog.getByRole("radiogroup");
            } else {
              await page.locator("#argus-profile-language-trigger").click();
              marker = dialog.getByRole("listbox");
            }
            await capture(page, cell, picker, marker);
          });
        }
        for (const action of ["menu", "rename", "delete"] as const) {
          test(`header ${action}`, async ({ page }) => {
            await openFixture(page, cell);
            await button(page, cell, "chat.chat_options").click();
            let marker = page.getByRole("menu");
            if (action !== "menu") {
              await page.getByRole("menuitem", { name: label(language, action === "rename" ? "chat.rename_chat" : "chat.delete_chat"), exact: true }).click();
              marker = action === "rename" ? page.getByRole("dialog").getByRole("textbox") : page.getByRole("alertdialog");
            }
            await capture(page, cell, `header-${action}`, marker);
          });
        }
        test("recents row menu", async ({ page }) => {
          await openFixture(page, cell);
          await page.getByTestId("chat-shell-menu-trigger").click();
          await button(page, cell, "common.recents").click();
          await page.locator("button[data-actions]").first().click();
          await capture(page, cell, "recents-menu", page.getByRole("menu"));
        });
      }

      test("assistant more actions", async ({ page }) => {
        await openFixture(page, cell);
        await page.route("**/api/v1/conversations/*/messages*", (route) => route.request().method() === "GET" ? route.fulfill({
          json: { items: [{ id: "phone-assistant", role: "assistant", content: language === "en" ? "Your idea is ready to review." : "Tu idea está lista para revisar.", created_at: "2026-08-01T12:00:00Z", metadata: {} }], next_cursor: null },
        }) : route.fallback());
        await page.reload({ waitUntil: "networkidle" });
        await page.addStyleTag({ content: FREEZE_CSS });
        await button(page, cell, "chat.more_actions").click();
        await capture(page, cell, "assistant-more", page.getByRole("menu"));
      });
      test("search row menu", async ({ page }) => {
        await openFixture(page, cell);
        await page.getByTestId("chat-shell-menu-trigger").click();
        await page.getByRole("button", { name: /^(search|buscar)$/i }).first().click();
        const rowMenu = page.getByTestId("command-palette-row-menu").first();
        await rowMenu.click();
        await capture(page, cell, "search-row-menu", page.getByRole("menu"));
      });
    });
  }
}
