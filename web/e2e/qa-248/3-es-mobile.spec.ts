import { devices, expect, test } from "@playwright/test";

import {
  HOSTED_MODE,
  currentRecoveryPassword,
  identities,
  loginViaUi,
  protectedMeStatus,
  runIp,
  screenshot,
} from "./helpers";

// Journeys 18-20: Spanish UI and mobile layout over the same real-auth flows,
// plus cross-user isolation while a second user revokes sessions.
// Pixel 7 keeps mobile emulation inside the repo's chromium-only browser set.
test.use({
  ...devices["Pixel 7"],
  locale: "es-419",
  extraHTTPHeaders: { "x-forwarded-for": runIp(8) },
});

test.describe("issue-248 Spanish + mobile coverage (local real auth)", () => {
  test("forgot-password speaks Spanish on mobile and stays enumeration-safe", async ({
    page,
  }) => {
    test.skip(HOSTED_MODE, "hosted recovery delivery is gated on sandbox SMTP");
    await page.goto("/auth/forgot-password");
    await expect(page.getByRole("heading", { name: "Recupera tu cuenta" })).toBeVisible();
    await page.locator('input[type="email"]').fill("nadie-248@qa.argus.local");
    await page.locator('button[type="submit"]').click();
    await expect(page.locator("main").getByRole("status")).toContainText("instrucciones", {
      timeout: 20_000,
    });
    await screenshot(page, "30-es-mobile-forgot-password");
  });

  test("account security speaks Spanish on mobile; cross-user isolation holds", async ({
    page,
    browser,
  }) => {
    const { secondEmail, secondPassword, recoveryEmail } = identities();

    const recoveryContext = await browser.newContext();
    const recoveryPage = await recoveryContext.newPage();
    await loginViaUi(recoveryPage, recoveryEmail, currentRecoveryPassword());
    await expect.poll(() => protectedMeStatus(recoveryContext), { timeout: 15_000 }).toBe(200);

    await loginViaUi(page, secondEmail, secondPassword);
    await page.goto("/account/security");
    await expect(
      page.getByRole("heading", { name: "Seguridad de la cuenta" }),
    ).toBeVisible({ timeout: 20_000 });
    await screenshot(page, "31-es-mobile-security-page");

    await page.getByRole("button", { name: "Cerrar otras sesiones" }).click();
    await page.getByRole("button", { name: "Confirmar", exact: true }).click();
    await expect(page.locator("main").getByRole("status")).toContainText("Las otras sesiones se cerraron", {
      timeout: 20_000,
    });
    await screenshot(page, "32-es-mobile-revoke-others");

    // The second user's revocation must not touch the recovery user's session.
    await expect.poll(() => protectedMeStatus(recoveryContext), { timeout: 15_000 }).toBe(200);

    await page.reload();
    await expect(
      page.getByRole("heading", { name: "Seguridad de la cuenta" }),
    ).toBeVisible({ timeout: 20_000 });
    await screenshot(page, "33-es-mobile-reload-still-authenticated");
    await recoveryContext.close();
  });
});
