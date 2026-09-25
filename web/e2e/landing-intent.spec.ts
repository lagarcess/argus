import { expect, test, type Page, type Route } from "@playwright/test";

const GUEST_ID = "00000000-0000-4000-8000-000000000701";
const CONVERSATION_ID = "00000000-0000-4000-8000-000000000702";
const EXPIRES_AT = "2026-07-31T18:00:00Z";
const BACKTEST_EN =
  "What if I had bought an S&P 500 fund over the last 12 months?";
const BACKTEST_ES =
  "¿Qué habría pasado si hubiera comprado un fondo del S&P 500 en los últimos 12 meses?";

type LandingEvidence = {
  bootstrapBodies: Record<string, unknown>[];
  signupBodies: Record<string, unknown>[];
  streamCalls: number;
  conversationCreateCalls: number;
};

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function guestMe(language: "en" | "es-419" = "en") {
  return {
    user: {
      id: GUEST_ID,
      email: null,
      username: null,
      display_name: null,
      language,
      locale: language === "es-419" ? "es-419" : "en-US",
      onboarding: {
        completed: false,
        stage: "language_selection",
        language_confirmed: false,
        primary_goal: null,
      },
    },
    account_kind: "guest",
    guest: {
      expires_at: EXPIRES_AT,
      conversation_id: CONVERSATION_ID,
      conversation_limit: 1,
      simulation_limit: 1,
      feedback_limit: 5,
    },
    capabilities: {
      can_create_additional_conversation: false,
      can_manage_conversation: false,
      can_save_decision: false,
      can_manage_account: false,
      can_use_omnisearch: true,
      can_search_current_workspace: true,
      can_use_grounded_discovery: false,
      can_submit_feedback: true,
    },
  };
}

async function mockLandingJourney(
  page: Page,
  language: "en" | "es-419" = "en",
): Promise<LandingEvidence> {
  let authenticated = false;
  const evidence: LandingEvidence = {
    bootstrapBodies: [],
    signupBodies: [],
    streamCalls: 0,
    conversationCreateCalls: 0,
  };

  await page.route("**/api/v1/auth/guest", async (route) => {
    if (route.request().method() === "POST") {
      evidence.bootstrapBodies.push(
        route.request().postDataJSON() as Record<string, unknown>,
      );
      authenticated = true;
    }
    await fulfillJson(route, {
      authenticated: true,
      reused: false,
      account_kind: "guest",
      user: guestMe(language).user,
    });
  });

  await page.route("**/api/v1/auth/signup", async (route) => {
    if (route.request().method() === "OPTIONS") {
      await route.fulfill({ status: 204 });
      return;
    }
    evidence.signupBodies.push(
      route.request().postDataJSON() as Record<string, unknown>,
    );
    await fulfillJson(route, {
      user: { id: "user-pending", email: "ad@example.com" },
      session: null,
    });
  });

  await page.route("**/api/v1/me", async (route) => {
    if (!authenticated) {
      await fulfillJson(
        route,
        {
          type: "about:blank",
          title: "Not authenticated",
          status: 401,
          code: "not_authenticated",
        },
        401,
      );
      return;
    }
    await fulfillJson(route, guestMe(language));
  });

  await page.route("**/api/v1/conversations**", async (route) => {
    if (route.request().method() === "POST") {
      evidence.conversationCreateCalls += 1;
    }
    if (route.request().url().includes("/activity")) {
      await fulfillJson(route, {
        operation: { status: "idle", kind: null, updated_at: null },
        attention: { status: "none", cursor: null },
      });
      return;
    }
    if (route.request().url().includes("/messages")) {
      await fulfillJson(route, { items: [], next_cursor: null });
      return;
    }
    await fulfillJson(route, { items: [], next_cursor: null });
  });

  await page.route("**/api/v1/history**", async (route) => {
    await fulfillJson(route, { items: [], next_cursor: null });
  });

  await page.route("**/api/v1/chat/stream", async (route) => {
    evidence.streamCalls += 1;
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: "data: [DONE]\n\n",
    });
  });

  await page.route("**/api/v1/me/usage", async (route) => {
    await fulfillJson(route, { allowances: {} });
  });

  await page.route("**/api/v1/analytics/guest-events", async (route) => {
    await fulfillJson(route, { success: true });
  });

  return evidence;
}

const expectedAttribution = {
  utm_campaign: "x",
  starter: "backtest",
  landing_path: "/",
};

test("ad landing prefills the backtest prompt without sending and keeps attribution", async ({
  page,
}) => {
  const evidence = await mockLandingJourney(page);
  await page.goto("/?utm_campaign=x&starter=backtest", {
    waitUntil: "domcontentloaded",
  });

  const composer = page.getByTestId("chat-input");
  await expect(composer).toBeVisible({ timeout: 15_000 });
  await expect(composer).toHaveText(BACKTEST_EN);
  await expect(page.getByTestId("chat-send")).toBeDisabled();
  await expect.poll(() => evidence.bootstrapBodies.length).toBe(1);
  expect(evidence.bootstrapBodies[0]?.attribution).toEqual(expectedAttribution);
  expect(evidence.streamCalls).toBe(0);
  expect(evidence.conversationCreateCalls).toBe(0);

  await page.goto("/?auth=signup", { waitUntil: "domcontentloaded" });
  await page.locator('input[type="text"]').fill("Ad Visitor");
  await page.locator('input[type="email"]').fill("ad@example.com");
  await page.locator('input[type="password"]').fill("correct-horse-battery");
  await page.getByRole("button", { name: "Sign up" }).click();
  await expect(page.getByTestId("auth-check-email")).toBeVisible();
  expect(evidence.signupBodies).toHaveLength(1);
  expect(evidence.signupBodies[0]?.attribution).toEqual(expectedAttribution);
  expect(evidence.streamCalls).toBe(0);
});

test("Spanish ad landing prefills the localized backtest prompt without sending", async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("i18nextLng", "es-419");
  });
  const evidence = await mockLandingJourney(page, "es-419");
  await page.goto("/?utm_campaign=x&starter=backtest", {
    waitUntil: "domcontentloaded",
  });

  const composer = page.getByTestId("chat-input");
  await expect(composer).toBeVisible({ timeout: 15_000 });
  await expect(composer).toHaveText(BACKTEST_ES);
  await expect.poll(() => evidence.bootstrapBodies.length).toBe(1);
  expect(evidence.bootstrapBodies[0]?.attribution).toMatchObject({
    starter: "backtest",
    utm_campaign: "x",
  });
  expect(evidence.streamCalls).toBe(0);
});
