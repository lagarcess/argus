import { expect, test } from "@playwright/test";

type StaticLabels = Record<string, string>;

const email = process.env.ARGUS_CANARY_BROWSER_EMAIL;
const password = process.env.ARGUS_CANARY_BROWSER_PASSWORD;
const language = process.env.ARGUS_CANARY_BROWSER_LANGUAGE;
const labels = JSON.parse(
  process.env.ARGUS_CANARY_STATIC_LABELS_JSON ?? "{}",
) as StaticLabels;

function label(key: string): string {
  const value = labels[key];
  if (!value) throw new Error(`Missing authoritative static label: ${key}`);
  return value;
}

test("Spanish signup submission and login hydrate the canary profile", async ({ page }) => {
  test.skip(!email || !password || !language, "browser canary credentials are required");

  await page.addInitScript((nextLanguage) => {
    window.localStorage.setItem("i18nextLng", nextLanguage);
  }, language);

  await page.goto("/?auth=signup", { waitUntil: "networkidle" });
  await expect(page.locator("html")).toHaveAttribute("lang", language);
  await expect(page.getByRole("button", { name: label("auth.signup.submit") })).toBeVisible();
  await expect(page.getByRole("button", { name: label("landing.sign_up_email") })).toHaveCount(0);

  // The reusable canary account is already allowlisted and provisioned. Submit
  // the real Spanish signup form with that existing identity and require the
  // privacy-safe duplicate response before testing its independent login path.
  const signupResponsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/v1/auth/signup") &&
      response.request().method() === "POST",
  );
  await page.locator('input[type="text"]').fill("Argus Release Canary");
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole("button", { name: label("auth.signup.submit") }).click();
  const signupResponse = await signupResponsePromise;
  expect(signupResponse.status()).toBe(400);
  await expect(page).not.toHaveURL(/\/chat(?:\?|$)/);

  await page.goto("/?auth=login", { waitUntil: "networkidle" });
  await expect(page.locator("html")).toHaveAttribute("lang", language);
  await page.locator('input[type="email"]').fill(email);
  await page.locator('input[type="password"]').fill(password);
  await page.getByRole("button", { name: label("auth.login.submit") }).click();

  await page.waitForURL(/\/chat(?:\?|$)/, { timeout: 30_000 });
  await expect(page.locator("html")).toHaveAttribute("lang", language);
  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 30_000 });
});
