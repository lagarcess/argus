import { expect, test } from "@playwright/test";

test.skip(process.env.CUADRAO_WEBSITE_PREVIEW !== "true", "Requires the local website preview");

for (const localePath of ["", "/en"]) {
  test.describe(`marketing forms ${localePath || "Spanish"} without JavaScript`, () => {
    test.use({ javaScriptEnabled: false });

    for (const [surface,field] of [["personal", "personal-email"], ["demo", "demo-email"]]) {
      test(`${surface} cannot submit visitor information through native navigation`, async ({ page }) => {
        await page.goto(`/business${localePath}/${surface}`);
        await expect(page.locator(`#${field}`)).toBeDisabled();
        await expect(page.locator('main button[type="submit"]')).toBeDisabled();
        await expect(page.locator('main noscript')).toContainText("JavaScript");
        expect(new URL(page.url()).search).toBe("");
      });
    }
  });

  test(`Personal ${localePath || "Spanish"} retains email after unavailable signup`, async ({ page }) => {
    await page.goto(`/business${localePath}/personal`);
    const email = page.locator("#personal-email");
    await expect(email).toBeEnabled();
    await email.fill("synthetic-hydration@example.invalid");
    await page.locator('main button[type="submit"]').click();
    await expect(page.locator("#signup-error")).toBeVisible();
    await expect(email).toHaveValue("synthetic-hydration@example.invalid");
    expect(new URL(page.url()).search).toBe("");
  });
}
