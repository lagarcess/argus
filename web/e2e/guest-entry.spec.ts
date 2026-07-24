import { expect, test, type Page, type Route } from "@playwright/test";

test.describe.configure({ timeout: 60_000 });

const GUEST_ID = "00000000-0000-4000-8000-000000000101";
const CONVERSATION_ID = "00000000-0000-4000-8000-000000000202";
const EXPIRES_AT = "2026-07-31T18:00:00Z";

type GuestBootEvidence = {
  bootstrapCalls: number;
  profilePatches: unknown[];
  sentMessages: string[];
  persistedMessages: Array<{
    id: string;
    conversation_id: string;
    role: "user" | "assistant";
    content: string;
    created_at: string;
    metadata: Record<string, unknown>;
  }>;
};

function guestMe() {
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
      can_use_omnisearch: false,
      can_submit_feedback: true,
    },
  };
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function mockGuestJourney(page: Page): Promise<GuestBootEvidence> {
  const evidence: GuestBootEvidence = {
    bootstrapCalls: 0,
    profilePatches: [],
    sentMessages: [],
    persistedMessages: [],
  };
  await page.route("**/api/v1/auth/guest", async (route) => {
    evidence.bootstrapCalls += 1;
    await fulfillJson(route, {
      authenticated: true,
      reused: evidence.bootstrapCalls > 1,
      account_kind: "guest",
      user: guestMe().user,
    });
  });

  await page.route("**/api/v1/me", async (route) => {
    if (route.request().method() === "PATCH") {
      evidence.profilePatches.push(route.request().postDataJSON());
    }
    await fulfillJson(route, guestMe());
  });

  await page.route("**/api/v1/conversations**", async (route) => {
    const url = new URL(route.request().url());
    const pathname = url.pathname;
    if (pathname.endsWith("/messages")) {
      await fulfillJson(route, {
        items: evidence.persistedMessages,
        next_cursor: null,
      });
      return;
    }
    if (route.request().method() === "POST") {
      await fulfillJson(route, {
        conversation: {
          id: CONVERSATION_ID,
          title: "New idea",
          title_source: "system_default",
          pinned: false,
          archived: false,
          created_at: "2026-07-24T18:00:00Z",
          updated_at: "2026-07-24T18:00:00Z",
          language: "en",
        },
      });
      return;
    }
    await fulfillJson(route, {
      items:
        evidence.persistedMessages.length > 0
          ? [
              {
                id: CONVERSATION_ID,
                title: "New idea",
                title_source: "system_default",
                pinned: false,
                archived: false,
                created_at: "2026-07-24T18:00:00Z",
                updated_at: "2026-07-24T18:00:00Z",
                language: "en",
              },
            ]
          : [],
      next_cursor: null,
    });
  });

  await page.route("**/api/v1/history**", async (route) => {
    await fulfillJson(route, { items: [], next_cursor: null });
  });

  await page.route("**/api/v1/chat/stream", async (route) => {
    const body = route.request().postDataJSON() as { message?: string };
    evidence.sentMessages.push(body.message ?? "");
    evidence.persistedMessages = [
      {
        id: "msg-user",
        conversation_id: CONVERSATION_ID,
        role: "user",
        content: body.message ?? "",
        created_at: "2026-07-24T18:01:00Z",
        metadata: {},
      },
      {
        id: "msg-guest",
        conversation_id: CONVERSATION_ID,
        role: "assistant",
        content: "Let’s test that idea.",
        created_at: "2026-07-24T18:01:01Z",
        metadata: {},
      },
    ];
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: [
        'data: {"type":"stage_start","stage":"clarify"}',
        "",
        'data: {"type":"token","content":"Let’s test that idea."}',
        "",
        `data: {"type":"final","payload":{"stage_outcome":"ready_to_respond","assistant_response":"Let’s test that idea.","message_id":"msg-guest","conversation_id":"${CONVERSATION_ID}"}}`,
        "",
        "data: [DONE]",
        "",
      ].join("\n"),
    });
  });

  return evidence;
}

test("@guest-shell guest entry bootstraps once and bypasses onboarding without profile mutation", async ({
  page,
}) => {
  const evidence = await mockGuestJourney(page);

  await page.goto("/", { waitUntil: "networkidle" });

  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByTestId("onboarding-goal-cards")).toHaveCount(0);
  await expect(page.getByTestId("onboarding-skip")).toHaveCount(0);
  expect(evidence.bootstrapCalls).toBe(1);
  expect(evidence.profilePatches).toEqual([]);

  await page.getByTestId("chat-input").fill("Compare Apple with SPY");
  await page.getByTestId("chat-input").press("Enter");
  await expect(page.getByText("Let’s test that idea.")).toBeVisible();
  expect(evidence.sentMessages).toEqual(["Compare Apple with SPY"]);
});

test("@guest-shell verified starter action uses the ordinary localized send path", async ({
  page,
}) => {
  const evidence = await mockGuestJourney(page);
  await page.goto("/", { waitUntil: "networkidle" });

  await page.getByRole("button", { name: "Test Apple vs SPY" }).click();
  await expect(page.getByText("Let’s test that idea.")).toBeVisible();
  expect(evidence.sentMessages).toEqual([
    "Buy and hold AAPL over the last 12 months with SPY as the benchmark.",
  ]);
  await expect(
    page.getByRole("button", { name: "Test Apple vs SPY" }),
  ).toHaveCount(0);
});

test("@guest-shell root re-entry restores the one server-owned guest conversation", async ({
  page,
}) => {
  const evidence = await mockGuestJourney(page);
  await page.goto("/", { waitUntil: "networkidle" });
  await page.getByTestId("chat-input").fill("Compare Apple with SPY");
  await page.getByTestId("chat-input").press("Enter");
  await expect(page.getByText("Let’s test that idea.")).toBeVisible();

  await page.goto("/", { waitUntil: "networkidle" });

  await expect(page.getByText("Compare Apple with SPY")).toBeVisible();
  await expect(page.getByText("Let’s test that idea.")).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`conversation=${CONVERSATION_ID}`));
  expect(evidence.bootstrapCalls).toBe(2);
  expect(evidence.profilePatches).toEqual([]);
});

test("@guest-shell frontend-on server-off mismatch stays on a retry surface", async ({
  page,
}) => {
  await page.route("**/api/v1/auth/guest", async (route) => {
    await fulfillJson(
      route,
      {
        detail: {
          title: "Guest Access Unavailable",
          detail: "Guest access is not available.",
          code: "guest_access_unavailable",
        },
      },
      403,
    );
  });

  await page.goto("/", { waitUntil: "networkidle" });

  await expect(page.getByRole("button", { name: "Try again" })).toBeVisible();
  await expect(page.getByTestId("chat-input")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Sign up" })).toHaveCount(0);
});
