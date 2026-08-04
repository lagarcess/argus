import { expect, test } from "@playwright/test";

import {
  identities,
  loginViaUi,
  protectedMe,
  screenshot,
} from "./helpers";

// Journey 16: the auth provider stays healthy while the session-verification
// database is unreachable. The runner starts the backend against a dead
// DATABASE_URL (memory checkpointer) before running this file, so protected
// APIs must answer a retryable 503 instead of redirecting to login.
test.describe("issue-248 session-verification outage (orchestrated)", () => {
  test.skip(
    process.env.QA_EXPECT_VERIFICATION_OUTAGE !== "1",
    "run via scripts/qa/run-local-auth-qa.sh outage phase",
  );

  test("verification outage is a retryable 503, never a false login redirect", async ({
    browser,
  }) => {
    const { secondEmail, secondPassword } = identities();
    const context = await browser.newContext();
    const page = await context.newPage();
    // Login itself only needs the healthy auth provider.
    await loginViaUi(page, secondEmail, secondPassword);

    await expect
      .poll(async () => (await protectedMe(context)).status, {
        timeout: 30_000,
        intervals: [1_500],
      })
      .toBe(503);
    const me = await protectedMe(context);
    expect(me.code).toBe("auth_session_verification_unavailable");

    await page.goto("/account/security");
    const alert = page.locator("main").getByRole("alert");
    await expect(alert).toContainText("verify your session", { timeout: 30_000 });
    await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
    expect(page.url()).toContain("/account/security");
    await screenshot(page, "26-retryable-503-surface");

    // Retry keeps the user on the surface while verification stays down.
    await page.getByRole("button", { name: "Retry" }).click();
    await expect(alert).toContainText("verify your session", { timeout: 30_000 });
    expect(page.url()).toContain("/account/security");
    await screenshot(page, "27-retry-stays-on-surface");
    await context.close();
  });
});
