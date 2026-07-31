import {
  expect,
  test,
  type Page,
  type Route,
} from "@playwright/test";

const GUEST_ID = "00000000-0000-4000-8000-000000000501";
const CONVERSATION_ID = "00000000-0000-4000-8000-000000000502";
const EXPIRES_AT = "2026-08-07T18:00:00Z";

function corsHeaders(page: Page): Record<string, string> {
  return {
    "Access-Control-Allow-Credentials": "true",
    "Access-Control-Allow-Headers": "content-type",
    "Access-Control-Allow-Methods": "GET, PATCH, POST, OPTIONS",
    "Access-Control-Allow-Origin": new URL(page.url()).origin,
    Vary: "Origin",
  };
}

async function fulfillJson(
  route: Route,
  page: Page,
  body: unknown,
  status = 200,
): Promise<void> {
  if (route.request().method() === "OPTIONS") {
    await route.fulfill({ status: 204, headers: corsHeaders(page) });
    return;
  }
  await route.fulfill({
    status,
    contentType: "application/json",
    headers: corsHeaders(page),
    body: JSON.stringify(body),
  });
}

function guestMe(publicAccountAccessEnabled = false) {
  return {
    user: {
      id: GUEST_ID,
      email: null,
      username: null,
      display_name: null,
      language: "en",
      locale: "en-US",
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
      conversation_limit: 1,
      message_limit: 10,
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
      can_use_grounded_discovery: true,
      can_submit_feedback: true,
    },
    public_account_access_enabled: publicAccountAccessEnabled,
  };
}

async function mockGuestJourney(
  page: Page,
  publicAccountAccessEnabled = false,
): Promise<void> {
  await page.route("**/api/v1/auth/guest", (route) =>
    fulfillJson(route, page, {
      authenticated: true,
      reused: false,
      renewed_after_expiry: false,
      public_account_access_enabled: publicAccountAccessEnabled,
      account_kind: "guest",
      user: guestMe(publicAccountAccessEnabled).user,
    }),
  );
  await page.route("**/api/v1/me", (route) =>
    fulfillJson(route, page, guestMe(publicAccountAccessEnabled)),
  );
  await page.route("**/api/v1/me/usage", (route) =>
    fulfillJson(route, page, {
      allowances: {
        messages: { available_now: true },
        backtests: { available_now: true },
      },
    }),
  );
  await page.route("**/api/v1/history**", (route) =>
    fulfillJson(route, page, { items: [], next_cursor: null }),
  );
  await page.route("**/api/v1/conversations**", (route) => {
    const pathname = new URL(route.request().url()).pathname;
    if (pathname.endsWith("/messages")) {
      return fulfillJson(route, page, { items: [], next_cursor: null });
    }
    return fulfillJson(route, page, {
      items: [
        {
          id: CONVERSATION_ID,
          title: "Temporary idea",
          title_source: "system_default",
          pinned: false,
          archived: false,
          created_at: "2026-07-31T18:00:00Z",
          updated_at: "2026-07-31T18:00:00Z",
          language: "en",
        },
      ],
      next_cursor: null,
    });
  });
}

async function mockAcceptedAccessRequest(
  page: Page,
  bodies?: Array<Record<string, unknown>>,
): Promise<void> {
  await page.route("**/api/v1/auth/access-requests", async (route) => {
    if (route.request().method() !== "OPTIONS") {
      bodies?.push(route.request().postDataJSON() as Record<string, unknown>);
    }
    await fulfillJson(route, page, { accepted: true }, 202);
  });
}

test("gated landing opens request access by default", async ({ page }) => {
  await page.goto("/");

  const requestButton = page.getByRole("button", {
    name: "Request access",
    exact: true,
  });
  await expect(requestButton).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  await requestButton.click();

  await expect(page).toHaveURL(/\?auth=request$/);
  await expect(
    page.getByRole("heading", { name: "Request access to Argus" }),
  ).toBeVisible();
});

test("landing request route submits a generic request and focuses acceptance", async ({
  page,
}) => {
  const bodies: Array<Record<string, unknown>> = [];
  await mockAcceptedAccessRequest(page, bodies);
  await page.goto("/?auth=request");

  const email = page.getByRole("textbox", { name: "Email address" });
  await expect(
    page.getByRole("heading", { name: "Request access to Argus" }),
  ).toBeVisible();
  await expect(email).toBeFocused();
  await email.fill("person@example.com");
  await page.getByRole("button", { name: "Request access" }).click();

  await expect(
    page.getByRole("heading", { name: "Request received" }),
  ).toBeFocused();
  await expect(page.getByText(/If access is approved/)).toBeVisible();
  expect(bodies).toEqual([
    { email: "person@example.com", language: "en" },
  ]);
});

test("approval signup and existing login remain separate landing modes", async ({
  page,
}) => {
  await page.goto("/?auth=request");
  await page.getByRole("button", { name: "Sign up" }).click();

  await expect(page).toHaveURL(/\?auth=signup$/);
  await expect(page.getByPlaceholder("Name")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign up" })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Request access to Argus" }),
  ).toHaveCount(0);

  await page.goto("/?auth=request");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL(/\?auth=login$/);
  await expect(page.getByRole("button", { name: "Sign In" })).toBeVisible();
});

test("request failure stays generic and retry-safe", async ({ page }) => {
  await page.route("**/api/v1/auth/access-requests", (route) =>
    fulfillJson(
      route,
      page,
      {
        status: 503,
        code: "access_request_unavailable",
        detail: "This email is already approved on the allowlist.",
      },
      503,
    ),
  );
  await page.goto("/?auth=request");
  await page.getByRole("textbox", { name: "Email address" }).fill(
    "person@example.com",
  );
  await page.getByRole("button", { name: "Request access" }).click();

  await expect(page.locator("p[role='alert']")).toHaveText(
    "We couldn’t send your request. Please try again.",
  );
  await expect(
    page.getByText("This email is already approved on the allowlist."),
  ).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Request access" }))
    .toBeEnabled();
});

test("request state is localized in Latin American Spanish", async ({
  page,
}) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("i18nextLng", "es-419");
  });
  await mockAcceptedAccessRequest(page);
  await page.goto("/?auth=request");

  await expect(
    page.getByRole("heading", { name: "Solicita acceso a Argus" }),
  ).toBeVisible();
  await page.getByRole("textbox", { name: "Correo electrónico" }).fill(
    "persona@example.com",
  );
  await page.getByRole("button", { name: "Solicitar acceso" }).click();
  await expect(
    page.getByRole("heading", { name: "Solicitud recibida" }),
  ).toBeFocused();
});

test("gated guest conversion wraps the mounted conversation and restores focus", async ({
  page,
}) => {
  await mockGuestJourney(page);
  await mockAcceptedAccessRequest(page);
  await page.goto("/chat");
  const opener = page.getByRole("button", { name: "Sign in" });
  const chatInput = page.getByTestId("chat-input");
  await expect(page).toHaveURL(/\/chat(?:\?|$)/, { timeout: 10_000 });
  await expect(chatInput).toBeVisible({ timeout: 60_000 });

  await opener.click();
  let dialog = page.getByRole("dialog", {
    name: "Request access to Argus",
  });
  await expect(dialog).toBeVisible();
  await expect(chatInput).toHaveCount(1);
  await dialog.getByRole("button", { name: "Sign up" }).click();
  dialog = page.getByRole("dialog", { name: "Create your account" });
  await expect(dialog.getByPlaceholder("Name")).toBeVisible();
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(dialog).toHaveCount(0);
  await expect(opener).toBeFocused();

  await opener.click();
  dialog = page.getByRole("dialog", {
    name: "Request access to Argus",
  });
  await dialog.getByRole("button", { name: "Sign in" }).click();
  dialog = page.getByRole("dialog", { name: "Sign in" });
  await expect(dialog.getByRole("button", { name: "Sign In" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(opener).toBeFocused();

  await opener.click();
  dialog = page.getByRole("dialog", {
    name: "Request access to Argus",
  });
  await dialog.getByRole("textbox", { name: "Email address" }).fill(
    "guest@example.com",
  );
  await dialog.getByRole("button", { name: "Request access" }).click();
  dialog = page.getByRole("dialog", { name: "Request received" });
  await expect(
    dialog.getByRole("heading", { name: "Request received" }),
  ).toBeFocused();
  await expect(chatInput).toHaveCount(1);
});

test("enabled guest account access preserves the direct auth flow", async ({
  page,
}) => {
  await mockGuestJourney(page, true);
  await page.goto("/chat");
  await expect(page).toHaveURL(/\/chat(?:\?|$)/, { timeout: 10_000 });
  await expect(page.getByTestId("chat-input")).toBeVisible({
    timeout: 60_000,
  });

  await page.getByRole("button", { name: "Sign in" }).click();
  let dialog = page.getByRole("dialog", { name: "Sign in" });
  await expect(dialog).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Request access to Argus" }),
  ).toHaveCount(0);

  await dialog.getByRole("button", { name: "Sign up" }).click();
  dialog = page.getByRole("dialog", { name: "Create your account" });
  await expect(dialog.getByPlaceholder("Name")).toBeVisible();
});
