import { mkdir } from "node:fs/promises";
import { join } from "node:path";

import { expect, test, type Page } from "@playwright/test";

import en from "../public/locales/en/common.json";
import { FREEZE_CSS } from "./support/breakpoint-fixture";

/**
 * Opens the written feedback dialog the same way a registered user does from
 * Settings, then records the panel. FEEDBACK_DIALOG_SHOT_DIR keeps screenshots
 * for the #675 before/after evidence.
 */
async function mockChat(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("i18nextLng", "en");
    window.localStorage.setItem("argus-theme", "light");
  });

  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const method = route.request().method();

    if (url.pathname.endsWith("/api/v1/feedback") && method === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ success: true }),
      });
    }

    if (url.pathname.endsWith("/api/v1/me")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          user: {
            id: "feedback-dialog-user",
            email: "qa@example.com",
            username: "qa",
            display_name: "Feedback Dialog QA",
            language: "en",
            locale: "en-US",
            onboarding: {
              completed: true,
              stage: "completed",
              language_confirmed: true,
              primary_goal: null,
            },
          },
          account_kind: "registered",
          guest: null,
          capabilities: {
            can_create_additional_conversation: true,
            can_manage_conversation: true,
            can_save_decision: true,
            can_manage_account: true,
            can_use_omnisearch: true,
            can_search_current_workspace: true,
            can_use_grounded_discovery: true,
            can_submit_feedback: true,
          },
          public_account_access_enabled: false,
        }),
      });
    }

    if (url.pathname.endsWith("/api/v1/conversations") && method === "GET") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ items: [], next_cursor: null }),
      });
    }

    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({}),
    });
  });
}

async function openGeneralFeedback(page: Page) {
  await page.goto("/chat", { waitUntil: "networkidle" });
  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });
  await page.addStyleTag({ content: FREEZE_CSS });
  await page.getByRole("button", { name: "Settings" }).first().click();
  await page.getByRole("button", { name: en.feedback.eyebrow, exact: true }).click();
  await page
    .getByRole("button", { name: en.feedback.type.general, exact: true })
    .click();
  const dialog = page.getByRole("dialog", { name: en.feedback.title });
  await expect(dialog).toBeVisible();
  return dialog;
}

async function capture(page: Page, name: string) {
  const dir = process.env.FEEDBACK_DIALOG_SHOT_DIR;
  if (!dir) return;
  await mkdir(dir, { recursive: true });
  await page.addStyleTag({
    content:
      "nextjs-portal, [data-dev-mode-badge] { display: none !important; }",
  });
  await page.screenshot({
    path: join(dir, `${name}.png`),
    animations: "disabled",
  });
}

test("opens the written feedback dialog without an attachment picker", async ({
  page,
}) => {
  await mockChat(page);
  const dialog = await openGeneralFeedback(page);
  await expect(dialog.getByPlaceholder(en.feedback.details_placeholder)).toBeVisible();
  await expect(dialog.locator('input[type="file"]')).toHaveCount(0);
  await capture(page, "feedback-dialog-en");

  await dialog.getByPlaceholder(en.feedback.details_placeholder).fill(
    "The chat stayed clear.",
  );
  const posted = page.waitForRequest(
    (request) =>
      request.method() === "POST" &&
      new URL(request.url()).pathname.endsWith("/api/v1/feedback"),
  );
  await dialog.getByRole("button", { name: en.feedback.submit }).click();
  const payload = (await posted).postDataJSON() as {
    type: string;
    message: string;
    context?: Record<string, unknown>;
  };
  expect(payload.type).toBe("general");
  expect(payload.message).toBe("The chat stayed clear.");
  expect(payload.context).toEqual({
    surface: "sidebar",
    tags: [],
  });
  expect(payload.context).not.toHaveProperty("hasAttachments");
  expect(payload.context).not.toHaveProperty("attachmentCount");
  await expect(dialog.getByText(en.feedback.success_detail)).toBeVisible();
});
