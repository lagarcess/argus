import { createHash } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Page } from "@playwright/test";

const liveGuestQaEnabled = process.env.ARGUS_LIVE_GUEST_QA === "true";
const candidateSha = process.env.ARGUS_CANDIDATE_SHA?.trim() ?? "";

test.skip(!liveGuestQaEnabled, "Runs only against the approved local QA stack.");
test.describe.configure({ mode: "serial", timeout: 240_000 });

type GuestMeShape = {
  account_kind: "guest" | "registered";
  user: {
    id: string;
    email: string | null;
    language: "en" | "es-419";
  };
  guest: { expires_at: string } | null;
};

function evidenceDirectory() {
  if (!/^[0-9a-f]{40}$/.test(candidateSha)) {
    throw new Error("ARGUS_CANDIDATE_SHA must be the exact 40-character SHA.");
  }
  const directory = join(
    process.cwd(),
    "temp",
    "qa-evidence-guest",
    candidateSha,
  );
  mkdirSync(directory, { recursive: true });
  return directory;
}

function evidenceLabel(namespace: string, value: string) {
  return createHash("sha256")
    .update(`argus-guest-qa:${candidateSha}:${namespace}:${value}`)
    .digest("hex")
    .slice(0, 20);
}

async function waitForMe(page: Page) {
  const response = await page.waitForResponse(
    (candidate) =>
      candidate.request().method() === "GET" &&
      new URL(candidate.url()).pathname.endsWith("/api/v1/me") &&
      candidate.status() === 200,
  );
  return (await response.json()) as GuestMeShape;
}

test("@guest-experience exact-head public staged journey", async ({ page }) => {
  const evidenceDir = evidenceDirectory();
  const consoleErrors: string[] = [];
  const mutationPaths: string[] = [];
  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  page.on("request", (request) => {
    if (!["GET", "HEAD", "OPTIONS"].includes(request.method())) {
      mutationPaths.push(new URL(request.url()).pathname);
    }
  });

  const initialMePromise = waitForMe(page);
  await page.goto("/", { waitUntil: "domcontentloaded" });
  const initialMe = await initialMePromise;

  expect(initialMe.account_kind).toBe("guest");
  expect(initialMe.user.email).toBeNull();
  expect(initialMe.guest?.expires_at).toBeTruthy();
  await expect(page).toHaveURL(/\/chat(?:\?|$)/);
  await expect(
    page.getByText("Test an investing idea against history."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Guest settings" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
  await expect(page.getByRole("button", { name: /Create account/i })).toHaveCount(0);
  await expect(page.getByTestId("guest-legal-before_message")).toBeVisible();
  await expect(page.getByTestId("guest-temporary-notice")).toHaveCount(1);

  const streamResponse = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname.endsWith("/api/v1/chat/stream"),
  );
  await page.getByRole("button", { name: "Test Apple vs SPY" }).click();
  expect((await streamResponse).status()).toBe(200);

  const runButton = page.getByRole("button", { name: /Run backtest/i });
  await expect(runButton).toBeVisible({ timeout: 120_000 });
  await runButton.click();
  await expect(page.getByTestId("result-equity-chart")).toBeVisible({
    timeout: 120_000,
  });

  const conversationId = new URL(page.url()).searchParams.get("conversation");
  expect(conversationId).toBeTruthy();
  const writesBeforeChart = mutationPaths.length;
  const chartRange = page.getByTestId("result-chart-range-1M");
  if (await chartRange.isVisible()) {
    await chartRange.click();
    await expect(page.getByTestId("result-chart-visible-period")).toBeVisible();
    expect(mutationPaths.length).toBe(writesBeforeChart);
  }

  const reloadMePromise = waitForMe(page);
  await page.reload({ waitUntil: "domcontentloaded" });
  const reloadMe = await reloadMePromise;
  expect(reloadMe.user.id).toBe(initialMe.user.id);
  expect(new URL(page.url()).searchParams.get("conversation")).toBe(
    conversationId,
  );
  await expect(page.getByTestId("result-equity-chart")).toBeVisible({
    timeout: 30_000,
  });

  await page.screenshot({
    path: join(evidenceDir, "public-staged-result.png"),
    fullPage: true,
  });
  writeFileSync(
    join(evidenceDir, "public-staged-summary.json"),
    `${JSON.stringify(
      {
        candidate_sha: candidateSha,
        account_kind: reloadMe.account_kind,
        owner_label: evidenceLabel("owner", reloadMe.user.id),
        conversation_label: evidenceLabel(
          "conversation",
          conversationId ?? "",
        ),
        guest_email_is_null: reloadMe.user.email === null,
        expiry_present: Boolean(reloadMe.guest?.expires_at),
        mutation_path_counts: Object.fromEntries(
          [...new Set(mutationPaths)].map((path) => [
            path,
            mutationPaths.filter((candidate) => candidate === path).length,
          ]),
        ),
        console_error_count: consoleErrors.length,
      },
      null,
      2,
    )}\n`,
    "utf8",
  );

  expect(consoleErrors).toEqual([]);
});
