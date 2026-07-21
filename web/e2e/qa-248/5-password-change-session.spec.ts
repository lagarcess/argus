import { expect, test, type Browser } from "@playwright/test";

import {
  HOSTED_MODE,
  authSessionsCount,
  currentRecoveryPassword,
  identities,
  loginViaUi,
  supabaseSessionId,
} from "./helpers";

// Session-integrity pins for the normal password-change path.
//
// The current implementation proves the current password with a real
// signInWithPassword call, which persists a fresh session in the browser
// client. A failed update therefore leaves the browser on a different
// session id and an extra auth.sessions row. The provider-native contract
// (updateUser({password, current_password}) enforced by
// GOTRUE_SECURITY_UPDATE_PASSWORD_REQUIRE_CURRENT_PASSWORD) would avoid
// that, but Supabase CLI v2.109.0 exposes no config key for it, so these
// assertions are pinned as expected failures. Set
// QA_EXPECT_NATIVE_CURRENT_PASSWORD=1 once enforcement exists: the pins
// then run as hard assertions and the expected-failure marker trips.
const NATIVE_ENFORCEMENT = process.env.QA_EXPECT_NATIVE_CURRENT_PASSWORD === "1";

async function loginFresh(browser: Browser, email: string, password: string) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await loginViaUi(page, email, password);
  return { context, page };
}

test.describe("issue-248 password-change session integrity (local)", () => {
  test.skip(HOSTED_MODE, "local-only session-state proof");

  test("a failed update preserves the original session and adds no auth.sessions row", async ({
    browser,
  }) => {
    test.fail(
      !NATIVE_ENFORCEMENT,
      "signInWithPassword verification persists a session; CLI v2.109.0 cannot enable provider-native current_password enforcement",
    );
    const { recoveryEmail } = identities();
    const password = currentRecoveryPassword();
    const { context, page } = await loginFresh(browser, recoveryEmail, password);

    const originalSessionId = await supabaseSessionId(context);
    expect(originalSessionId).toBeTruthy();
    const rowsBefore = authSessionsCount(recoveryEmail);

    await page.goto("/account/security");
    // Same-password update passes every client check and the credential
    // verification, then the provider rejects it — the update fails after a
    // successful current-password check.
    await page.getByLabel("Current password", { exact: true }).fill(password);
    await page.getByLabel("New password", { exact: true }).fill(password);
    await page.getByLabel("Confirm new password", { exact: true }).fill(password);
    await page.getByRole("button", { name: "Change password" }).click();
    await expect(page.locator("main").getByRole("alert")).toBeVisible({
      timeout: 25_000,
    });

    const afterSessionId = await supabaseSessionId(context);
    expect(afterSessionId).toBe(originalSessionId);
    if (rowsBefore !== null) {
      expect(authSessionsCount(recoveryEmail)).toBe(rowsBefore);
    }
    await context.close();
  });
});
