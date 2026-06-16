import { expect, test, type Page } from "@playwright/test";

type OnboardingStage =
  | "language_selection"
  | "primary_goal_selection"
  | "ready"
  | "completed";

type MockChatBoot = {
  profilePatches: Array<{ onboarding?: Record<string, unknown> }>;
};

async function mockChatBoot(page: Page, stage: OnboardingStage): Promise<MockChatBoot> {
  const profilePatches: MockChatBoot["profilePatches"] = [];

  await page.route("**/api/v1/conversations", async (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          conversation: {
            id: "conv-e2e",
            title: "New idea",
            title_source: "system_default",
            pinned: false,
            archived: false,
            created_at: "2026-04-25T00:00:00Z",
            updated_at: "2026-04-25T00:00:00Z",
            language: "en",
          },
        }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], next_cursor: null }),
    });
  });

  await page.route("**/api/v1/me", async (route) => {
    const method = route.request().method();
    if (method === "PATCH") {
      const body = route.request().postDataJSON() as {
        onboarding?: { completed?: boolean; primary_goal?: string | null };
      };
      profilePatches.push(body as MockChatBoot["profilePatches"][number]);
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          user: {
            id: "dev-user",
            language: "en",
            locale: "en-US",
            onboarding: {
              completed: body.onboarding?.completed ?? true,
              stage: "ready",
              language_confirmed: true,
              primary_goal: body.onboarding?.primary_goal ?? "surprise_me",
            },
          },
        }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: {
          id: "dev-user",
          language: "en",
          locale: "en-US",
          onboarding: {
            completed: stage === "completed",
            stage,
            language_confirmed: stage !== "language_selection",
            primary_goal:
              stage === "completed" || stage === "ready"
                ? "test_stock_idea"
                : null,
          },
        },
      }),
    });
  });

  await page.route("**/api/v1/history**", async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], next_cursor: null }),
    }),
  );

  await page.route("**/api/v1/search**", async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            type: "chat",
            id: "conv-e2e",
            title: "Tesla chat",
            matched_text: "Discussing TSLA",
            updated_at: "2026-04-25T00:00:00Z",
          },
          {
            type: "strategy",
            id: "strat-e2e",
            title: "Tesla strategy",
            matched_text: "TSLA",
            updated_at: "2026-04-24T00:00:00Z",
          },
        ],
        next_cursor: null,
      }),
    }),
  );

  await page.route("**/api/v1/chat/stream", async (route) =>
    route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: [
        'data: {"type":"stage_start","stage":"clarify"}',
        "",
        'data: {"type":"token","content":"Great. I\'ll guide you with a starter idea to begin."}',
        "",
        'data: {"type":"final","payload":{"stage_outcome":"ready_to_respond","assistant_response":"Great. I\'ll guide you with a starter idea to begin.","message_id":"msg-onboarding"}}',
        "",
        "data: [DONE]",
        "",
      ].join("\n"),
    }),
  );

  return { profilePatches };
}

test("skips onboarding friction for first-time private-alpha users", async ({ page }) => {
  const boot = await mockChatBoot(page, "language_selection");
  await page.goto("/chat", { waitUntil: "networkidle" });

  await expect(page.getByTestId("chat-input")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByTestId("onboarding-goal-cards")).toHaveCount(0);
  await expect(page.getByTestId("onboarding-skip")).toHaveCount(0);
  await expect
    .poll(() => boot.profilePatches.length, { timeout: 15_000 })
    .toBeGreaterThan(0);
  expect(boot.profilePatches.at(-1)?.onboarding).toMatchObject({
    completed: true,
    primary_goal: "surprise_me",
    stage: "ready",
  });
});

test("primary-goal onboarding records enter chat without a skip step", async ({ page }) => {
  await mockChatBoot(page, "primary_goal_selection");
  await page.goto("/chat", { waitUntil: "networkidle" });

  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByTestId("onboarding-skip")).toHaveCount(0);
  await expect(page.getByTestId("onboarding-goal-cards")).toHaveCount(0);
});

test("does not show onboarding cards for completed users", async ({ page }) => {
  await mockChatBoot(page, "completed");
  await page.goto("/chat", { waitUntil: "networkidle" });

  await expect(page.getByTestId("onboarding-goal-cards")).toHaveCount(0);
});

test("ready onboarding records enter chat even if legacy completed flag is false", async ({ page }) => {
  await mockChatBoot(page, "ready");
  await page.goto("/chat", { waitUntil: "networkidle" });

  await expect(page.getByText("Choose your language")).toHaveCount(0);
  await expect(page.getByTestId("onboarding-goal-cards")).toHaveCount(0);
});

test("hides global sidebar search under private-alpha defaults", async ({ page }) => {
  await mockChatBoot(page, "completed");
  await page.goto("/chat", { waitUntil: "networkidle" });

  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByPlaceholder("Search")).toHaveCount(0);
  await expect(page.getByText("Tesla strategy")).toHaveCount(0);
});

test("signup and login expose persisted account entry", async ({ page }) => {
  await page.goto("/?auth=signup", { waitUntil: "networkidle" });

  await expect(page.getByPlaceholder("Name")).toBeVisible();
  await expect(page.getByPlaceholder("Email address")).toBeVisible();
  await expect(page.getByPlaceholder("Password")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign up" })).toBeVisible();
  await expect(page.getByText(/guest/i)).toHaveCount(0);

  await page.goto("/?auth=login", { waitUntil: "networkidle" });

  await expect(page.getByPlaceholder("Email address")).toBeVisible();
  await expect(page.getByPlaceholder("Password")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign In" })).toBeVisible();
});

test("mock-auth login submits into the private-alpha chat", async ({ page }) => {
  await mockChatBoot(page, "completed");
  await page.goto("/?auth=login", { waitUntil: "networkidle" });

  await page.getByPlaceholder("Email address").fill("dev@example.com");
  await page.getByPlaceholder("Password").fill("local-password");
  await page.getByRole("button", { name: "Sign In" }).click();

  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });
});
