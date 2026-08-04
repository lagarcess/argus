import { expect, test, type Browser } from "@playwright/test";

import {
  HOSTED_MODE,
  argusCookieNames,
  cookieOnlyMeStatus,
  cookieReplayMeStatus,
  identities,
  loginViaUi,
} from "./helpers";

// Journey 8/14/15 on the ACTUAL Argus HttpOnly cookie transport. The local
// topology is same-site (localhost:3000 app -> localhost:8000 API), so the
// backend's Set-Cookie is stored and replayable — unlike bearer replay,
// which 2-sessions.spec.ts covers separately.
async function loginFresh(browser: Browser, email: string, password: string) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await loginViaUi(page, email, password);
  return { context, page };
}

test.describe("issue-248 Argus HttpOnly cookie path (same-site local)", () => {
  test.skip(HOSTED_MODE, "local same-site topology proof");

  test("cookies authenticate alone, are rejected once revoked, and clear on logout", async ({
    browser,
  }) => {
    const { secondEmail, secondPassword } = identities();
    const a = await loginFresh(browser, secondEmail, secondPassword);

    // 1: login stored the Argus cookies on the backend origin.
    const names = await argusCookieNames(a.context);
    expect(names).toContain("sb-auth-token");
    expect(names).toContain("sb-refresh-token");

    // 2: a request with no Authorization header authenticates via cookie.
    await expect
      .poll(() => cookieOnlyMeStatus(a.page), { timeout: 15_000 })
      .toBe(200);

    // 3: revoke the Supabase session while cookie cleanup is blocked.
    await a.context.route("**/api/v1/auth/logout", (route) => route.abort());
    await a.page.goto("/account/security");
    await a.page.getByRole("button", { name: /Sign out this browser|Cerrar sesión en este navegador/ }).click();
    await expect(a.page.locator("main").getByRole("alert")).toContainText(
      /cookie cleanup|limpieza local de cookies/,
      { timeout: 20_000 },
    );

    // 4: the Argus cookie survived the failed cleanup.
    expect(await argusCookieNames(a.context)).toContain("sb-auth-token");

    // 5: replaying it is rejected — its session_id is gone from auth.sessions.
    await expect
      .poll(() => cookieReplayMeStatus(a.context), { timeout: 20_000 })
      .toBe(401);
    await a.context.unroute("**/api/v1/auth/logout");
    await a.context.close();

    // 6: a successful logout removes the backend-origin Argus cookies.
    const b = await loginFresh(browser, secondEmail, secondPassword);
    expect(await argusCookieNames(b.context)).toContain("sb-auth-token");
    await b.page.goto("/account/security");
    await b.page.getByRole("button", { name: /Sign out this browser|Cerrar sesión en este navegador/ }).click();
    await expect(b.page.locator("main").getByRole("status")).toBeVisible({
      timeout: 20_000,
    });
    await expect
      .poll(async () => (await argusCookieNames(b.context)).includes("sb-auth-token"), {
        timeout: 15_000,
      })
      .toBe(false);
    await b.context.close();
  });
});
