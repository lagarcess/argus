import { expect, test, type Page } from "@playwright/test";

// Chat boot behavior that must survive the onboarding strip-out: private-alpha
// flag defaults on the chat surface, and the authenticated profile language
// winning before the chat first paints.

async function mockChatBoot(page: Page, language: "en" | "es-419" = "en") {
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
            language,
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

  await page.route("**/api/v1/me", async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: {
          id: "dev-user",
          email: "dev@example.com",
          username: "dev",
          display_name: "Mock Developer",
          language,
          locale: language === "es-419" ? "es-419" : "en-US",
        },
      }),
    }),
  );
}

test("hides global sidebar search under private-alpha defaults", async ({ page }) => {
  await mockChatBoot(page);
  await page.goto("/chat", { waitUntil: "networkidle" });

  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByPlaceholder("Search")).toHaveCount(0);
  await expect(page.getByText("Tesla strategy")).toHaveCount(0);
});

test("authenticated profile language wins before the chat renders", async ({ page }) => {
  await page.addInitScript(() => {
    window.localStorage.setItem("i18nextLng", "en");
  });
  await mockChatBoot(page, "es-419");

  await page.goto("/chat", { waitUntil: "domcontentloaded" });
  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });
  await expect(page.locator("html")).toHaveAttribute("lang", "es-419", {
    timeout: 500,
  });
  await expect(page.getByTestId("chat-input")).toHaveAttribute(
    "aria-label",
    /Describe una idea/,
  );
});
