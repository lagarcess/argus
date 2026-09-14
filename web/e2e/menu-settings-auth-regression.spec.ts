import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";
import path from "node:path";
import { AUDIT_CELLS, AUDIT_DIR as evidence, auditTag, openFixture } from "./support/menu-settings-fixture";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";


for (const cell of AUDIT_CELLS.filter((cell) => cell.account === "guest")) {
  test(`${auditTag(cell)} auth settings shares shape and keyboard ownership`, async ({ page }) => {
    const copy = cell.language === "en" ? en : es;
    await openFixture(page, cell, "/?auth=login");
    const trigger = page.getByRole("button", { name: /^(settings|guest settings|ajustes de invitado|configuración de invitado)$/i });
    const language = () => page.getByRole("menuitem", { name: copy.guest.shell.language, exact: true });
    await trigger.click();
    await expect(page.locator(".argus-sheet")).toHaveCount(cell.width < 1024 ? 1 : 0);
    if (cell.width >= 1024) await expect(page.getByRole("menu")).toBeVisible();
    const appearance = page.getByRole("group", { name: copy.settings.app.appearance, exact: true });
    for (const label of Object.values(copy.settings.app.appearance_options)) {
      await expect(appearance.getByRole("button", { name: label, exact: true })).toBeVisible();
    }
    for (const theme of [cell.theme === "light" ? "dark" : "light", cell.theme ?? "dark"] as const) {
      const option = appearance.getByRole("button", { name: copy.settings.app.appearance_options[theme], exact: true });
      await option.click();
      await expect(option).toHaveAttribute("aria-pressed", "true");
      await expect(page.locator("html")).toHaveClass(new RegExp(`\\b${theme}\\b`));
    }
    await expect(page.getByRole("menuitem", { name: copy.guest.shell.feedback, exact: true })).toHaveCount(0);
    await page.evaluate(() => document.fonts.ready);
    mkdirSync(evidence, { recursive: true });
    await page.screenshot({ path: path.join(evidence, `${auditTag(cell)}-auth-settings-menu-fixed.png`), animations: "disabled", scale: "css" });
    await language().click();
    const dialog = page.getByRole("dialog", { name: copy.guest.shell.language, exact: true });
    await expect(dialog).toBeVisible();
    await expect(page.locator(".argus-sheet")).toHaveCount(cell.width < 1024 ? 1 : 0);
    await expect(dialog.getByRole("button", { name: copy.settings.app.close_language_modal, exact: true })).toBeVisible();
    await expect(dialog.getByRole("textbox")).toBeFocused();
    // Walk beyond one full cycle; focus must never escape into the login form.
    const controls = await dialog.locator("button, input").count();
    for (let index = 0; index <= controls; index += 1) {
      await page.keyboard.press("Tab");
      await expect.poll(() => dialog.evaluate((node) => node.contains(document.activeElement))).toBe(true);
    }
    await page.screenshot({ path: path.join(evidence, `${auditTag(cell)}-auth-settings-language-fixed.png`), animations: "disabled", scale: "css" });
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await expect(page).toHaveURL(/\?auth=login/);

    await trigger.click();
    await language().click();
    await expect(dialog).toBeVisible();
    await page.goBack();
    await expect(dialog).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await expect(page).toHaveURL(/\?auth=login/);

    // Auth language is a browser preference: a visible selection succeeds with
    // the fixture rejecting every profile/auth write.
    await trigger.click();
    await language().click();
    await dialog.getByRole("button", { name: cell.language === "en" ? /^Español/ : /^English/ }).click();
    await expect(dialog).toHaveCount(0);
    const changedCopy = cell.language === "en" ? es : en;
    await expect(page.getByRole("button", { name: changedCopy.guest.shell.settings, exact: true })).toBeFocused();
  });
}
