import { expect, test } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

const liveGuestQaEnabled = process.env.ARGUS_LIVE_GUEST_QA === "true";
const intentionalPrompt =
  "Compare Apple with SPY over the last 12 months.";

test.skip(!liveGuestQaEnabled, "Runs only against the approved local QA stack.");
test.describe.configure({ timeout: 180_000 });

test("@guest-live thin anonymous entry, turn, and reload checkpoint", async ({
  page,
}) => {
  const firstMeResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname.endsWith("/api/v1/me") &&
      response.status() === 200,
  );

  await page.goto("/", { waitUntil: "domcontentloaded" });
  const firstMe = (await (await firstMeResponse).json()) as {
    account_kind: string;
    user: { id: string; onboarding: { primary_goal: string | null } };
    guest: { expires_at: string } | null;
  };

  expect(firstMe.account_kind).toBe("guest");
  expect(firstMe.user.onboarding.primary_goal).toBeNull();
  expect(firstMe.guest?.expires_at).toBeTruthy();
  await expect(page.getByTestId("chat-input")).toBeVisible({
    timeout: 30_000,
  });
  await expect(page).toHaveURL(/\/chat(?:\?|$)/);
  await expect(page.getByTestId("onboarding-goal-cards")).toHaveCount(0);

  const streamResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname.endsWith("/api/v1/chat/stream") &&
      response.status() === 200,
  );
  await page.getByTestId("chat-input").fill(intentionalPrompt);
  await page.getByTestId("chat-input").press("Enter");
  await expect(page.getByText(intentionalPrompt, { exact: true })).toBeVisible();
  await (await streamResponse).finished();

  const conversationId = new URL(page.url()).searchParams.get("conversation");
  expect(conversationId).toBeTruthy();

  const reloadMeResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname.endsWith("/api/v1/me") &&
      response.status() === 200,
  );
  const messagesResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname.endsWith(
        `/api/v1/conversations/${conversationId}/messages`,
      ) &&
      response.status() === 200,
  );
  await page.reload({ waitUntil: "domcontentloaded" });
  const reloadMe = (await (await reloadMeResponse).json()) as {
    account_kind: string;
    user: { id: string };
  };
  const durableMessages = (await (await messagesResponse).json()) as {
    items: Array<{
      role: string;
      content: string;
      metadata?: Record<string, unknown>;
    }>;
  };

  expect(reloadMe.account_kind).toBe("guest");
  expect(reloadMe.user.id).toBe(firstMe.user.id);
  expect(
    durableMessages.items.some(
      (message) =>
        message.role === "user" && message.content === intentionalPrompt,
    ),
  ).toBe(true);
  const durableAssistantMessages = durableMessages.items.filter(
    (message) => message.role === "assistant",
  );
  expect(durableAssistantMessages.length).toBeGreaterThan(0);
  await expect(page.getByText(intentionalPrompt, { exact: true })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByLabel("Copy Plain Text").first()).toBeAttached({
    timeout: 30_000,
  });
  expect(new URL(page.url()).searchParams.get("conversation")).toBe(
    conversationId,
  );

  const evidenceDir = join(
    process.cwd(),
    "temp",
    "block2-evidence",
    process.env.ARGUS_CANDIDATE_SHA ?? "local",
  );
  mkdirSync(evidenceDir, { recursive: true });
  const screenshotPath = join(evidenceDir, "checkpoint-a-reload.png");
  await page.screenshot({ path: screenshotPath, fullPage: true });

  console.log(
    "LIVE_GUEST_EVIDENCE",
    JSON.stringify({
      account_kind: reloadMe.account_kind,
      user_id: reloadMe.user.id,
      conversation_id: conversationId,
      assistant_messages: durableAssistantMessages.length,
      confirmation_artifacts: durableAssistantMessages.filter(
        (message) => message.metadata?.confirmation_card,
      ).length,
      result_artifacts: durableAssistantMessages.filter(
        (message) => message.metadata?.result_card,
      ).length,
      screenshot: screenshotPath,
    }),
  );
});
