import { expect, test, type Page } from "@playwright/test";

type OnboardingStage =
  | "language_selection"
  | "primary_goal_selection"
  | "ready"
  | "completed";

async function mockChatBoot(page: Page, stage: OnboardingStage): Promise<void> {
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
        onboarding?: { primary_goal?: string | null };
      };
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          user: {
            id: "dev-user",
            language: "en",
            locale: "en-US",
            onboarding: {
              completed: false,
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
        "event: token",
        'data: {"text":"Great. I\'ll guide you with a starter idea to begin."}',
        "",
        "event: done",
        'data: {"message_id":"msg-onboarding"}',
        "",
      ].join("\n"),
    }),
  );
}

test("shows onboarding goal cards for first-time user", async ({ page }) => {
  await mockChatBoot(page, "language_selection");
  await page.goto("/chat", { waitUntil: "networkidle" });

  await expect(page.getByTestId("onboarding-goal-cards")).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByTestId("onboarding-goal-learn_basics")).toBeVisible();
  await expect(page.getByTestId("onboarding-goal-test_stock_idea")).toBeVisible();
  await expect(page.getByTestId("onboarding-skip")).toBeVisible();
});

test("submits onboarding skip and hides cards", async ({ page }) => {
  await mockChatBoot(page, "primary_goal_selection");
  await page.goto("/chat", { waitUntil: "networkidle" });

  await expect(page.getByTestId("onboarding-skip")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("onboarding-skip").click();

  await expect(page.getByTestId("onboarding-goal-cards")).toBeHidden();
  await expect(
    page.getByText("Great. I'll guide you with a starter idea to begin."),
  ).toBeVisible();
});

test("does not show onboarding cards for completed users", async ({ page }) => {
  await mockChatBoot(page, "completed");
  await page.goto("/chat", { waitUntil: "networkidle" });

  await expect(page.getByTestId("onboarding-goal-cards")).toHaveCount(0);
});

test("shows global sidebar search results in chat view", async ({ page }) => {
  await mockChatBoot(page, "completed");
  await page.goto("/chat", { waitUntil: "networkidle" });

  await page.getByPlaceholder("Search").fill("tesla");
  await expect(page.getByText("Tesla strategy")).toBeVisible();
});

test("login page honors spanish i18n preference", async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem("i18nextLng", "es-419");
  });
  await page.goto("/login", { waitUntil: "networkidle" });

  await expect(page.getByText("Inicia sesion para continuar")).toBeVisible();
});
