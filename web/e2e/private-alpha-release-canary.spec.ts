import { chmod, writeFile } from "node:fs/promises";
import { expect, test, type Page, type Response } from "@playwright/test";

type JsonRecord = Record<string, unknown>;
type StaticLabels = Record<string, string>;

const email = process.env.ARGUS_CANARY_BROWSER_EMAIL;
const password = process.env.ARGUS_CANARY_BROWSER_PASSWORD;
const language = process.env.ARGUS_CANARY_BROWSER_LANGUAGE;
const prompt = process.env.ARGUS_CANARY_BROWSER_PROMPT;
const decisionState = process.env.ARGUS_CANARY_BROWSER_DECISION_STATE;
const decisionNote = process.env.ARGUS_CANARY_BROWSER_DECISION_NOTE;
const searchQuery = process.env.ARGUS_CANARY_BROWSER_SEARCH_QUERY;
const identityHandoff = process.env.ARGUS_CANARY_BROWSER_IDENTITY_HANDOFF;
const labels = JSON.parse(
  process.env.ARGUS_CANARY_STATIC_LABELS_JSON ?? "{}",
) as StaticLabels;

function label(key: string): string {
  const value = labels[key];
  if (!value) throw new Error(`Missing authoritative static label: ${key}`);
  return value;
}

function requireConfig(value: string | undefined, name: string): string {
  if (!value?.trim()) throw new Error(`Missing browser canary config: ${name}`);
  return value;
}

function record(value: unknown, name: string): JsonRecord {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`Browser canary response omitted ${name}`);
  }
  return value as JsonRecord;
}

function privateId(value: unknown, name: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`Browser canary could not capture ${name}`);
  }
  return value;
}

function isApiResponse(response: Response, suffix: string, method: string): boolean {
  try {
    return (
      new URL(response.url()).pathname.endsWith(`/api/v1${suffix}`) &&
      response.request().method() === method
    );
  } catch {
    return false;
  }
}

async function loginThroughRenderedUi(page: Page): Promise<string> {
  const canaryEmail = requireConfig(email, "email");
  const canaryPassword = requireConfig(password, "password");
  const canaryLanguage = requireConfig(language, "language");

  await page.addInitScript((nextLanguage) => {
    window.localStorage.setItem("i18nextLng", nextLanguage);
  }, canaryLanguage);

  await page.goto("/?auth=login", { waitUntil: "networkidle" });
  await expect(page.locator("html")).toHaveAttribute("lang", canaryLanguage);

  const loginResponsePromise = page.waitForResponse((response) =>
    isApiResponse(response, "/auth/login", "POST"),
  );
  const profileResponsePromise = page.waitForResponse((response) =>
    isApiResponse(response, "/me", "GET"),
  );
  await page.locator('input[type="email"]').fill(canaryEmail);
  await page.locator('input[type="password"]').fill(canaryPassword);
  await page.getByRole("button", { name: label("auth.login.submit") }).click();

  const loginResponse = await loginResponsePromise;
  if (!loginResponse.ok()) throw new Error("Rendered login failed");
  const loginPayload = record(await loginResponse.json(), "login payload");
  const userId = privateId(record(loginPayload.user, "login user").id, "user identity");

  await page.waitForURL(/\/chat(?:\?|$)/, { timeout: 30_000 });
  const profileResponse = await profileResponsePromise;
  if (!profileResponse.ok()) throw new Error("Rendered profile hydration failed");
  const profilePayload = record(await profileResponse.json(), "profile payload");
  const profileUser = record(profilePayload.user, "hydrated profile");
  if (
    profileUser.id !== userId ||
    profileUser.language !== canaryLanguage ||
    profileUser.locale !== canaryLanguage
  ) {
    throw new Error("Rendered profile hydration did not preserve Spanish identity");
  }
  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 30_000 });
  return userId;
}

function captureBrowserErrors(page: Page) {
  const evidence = { consoleErrorCount: 0, pageErrorCount: 0 };
  page.on("console", (message) => {
    if (message.type() === "error") evidence.consoleErrorCount += 1;
  });
  page.on("pageerror", () => {
    evidence.pageErrorCount += 1;
  });
  return evidence;
}

function successfulJobCapture(page: Page) {
  const capture: { payload: JsonRecord | null } = { payload: null };
  page.on("response", (response) => {
    let pathname = "";
    try {
      pathname = new URL(response.url()).pathname;
    } catch {
      return;
    }
    if (
      response.request().method() !== "GET" ||
      !pathname.includes("/api/v1/backtest-jobs/") ||
      !response.ok()
    ) {
      return;
    }
    void response
      .json()
      .then((value: unknown) => {
        const payload = record(value, "backtest job payload");
        const job = record(payload.job, "backtest job");
        if (job.status === "succeeded" && payload.run) capture.payload = payload;
      })
      .catch(() => undefined);
  });
  return capture;
}

test.describe.serial("private-alpha rendered release canary", () => {
  test("browser owns the Spanish Golden Path and exports private identities", async ({ page }) => {
    test.setTimeout(480_000);
    const canaryPrompt = requireConfig(prompt, "prompt");
    const canaryDecisionState = requireConfig(decisionState, "decision state");
    const canaryDecisionNote = requireConfig(decisionNote, "decision note");
    const canarySearchQuery = requireConfig(searchQuery, "search query");
    const handoffPath = requireConfig(identityHandoff, "identity handoff");
    const browserErrors = captureBrowserErrors(page);
    const jobCapture = successfulJobCapture(page);
    let runBacktestRequests = 0;

    page.on("request", (request) => {
      let pathname = "";
      try {
        pathname = new URL(request.url()).pathname;
      } catch {
        return;
      }
      if (
        request.method() !== "POST" ||
        !pathname.endsWith("/api/v1/chat/stream")
      ) {
        return;
      }
      try {
        const body = request.postDataJSON() as JsonRecord;
        const action = body.action;
        if (record(action, "chat action").type === "run_backtest") {
          runBacktestRequests += 1;
        }
      } catch {
        // A normal prompt has no action object.
      }
    });

    const userId = await loginThroughRenderedUi(page);
    const conversationResponsePromise = page.waitForResponse((response) =>
      isApiResponse(response, "/conversations", "POST"),
    );
    await page.getByTestId("chat-input").fill(canaryPrompt);
    await page.getByTestId("chat-send").click();
    const conversationResponse = await conversationResponsePromise;
    if (!conversationResponse.ok()) throw new Error("Browser conversation creation failed");
    const conversationPayload = record(
      await conversationResponse.json(),
      "conversation payload",
    );
    const conversationId = privateId(
      record(conversationPayload.conversation, "conversation").id,
      "conversation identity",
    );
    if (new URL(page.url()).searchParams.get("conversation") !== conversationId) {
      throw new Error("Rendered conversation route did not preserve browser identity");
    }

    await expect(
      page.getByText(label("chat.confirmation.status.ready_to_run"), { exact: true }),
    ).toBeVisible({ timeout: 180_000 });
    await page
      .getByRole("button", { name: label("chat.confirmation.actions.run_backtest") })
      .click();

    await expect(
      page.getByText(label("chat.simulation_complete"), { exact: true }),
    ).toHaveCount(1, { timeout: 360_000 });
    await expect.poll(() => jobCapture.payload !== null, { timeout: 30_000 }).toBe(true);
    expect(runBacktestRequests).toBe(1);
    await expect(
      page.getByText(label("chat.backtest_job.queued_title"), { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText(label("chat.backtest_job.running_title"), { exact: true }),
    ).toHaveCount(0);
    await expect(
      page.getByText(label("chat.backtest_job.failed_title"), { exact: true }),
    ).toHaveCount(0);

    const jobPayload = record(jobCapture.payload, "successful job capture");
    const job = record(jobPayload.job, "successful job");
    const run = record(jobPayload.run, "completed run");
    const resultCard = record(run.conversation_result_card, "result card");
    const backtestJobId = privateId(job.id, "backtest job identity");
    const backtestRunId = privateId(run.id, "backtest run identity");
    const evidenceArtifactId = privateId(
      resultCard.evidence_artifact_id,
      "evidence identity",
    );
    const ideaId = privateId(resultCard.idea_id, "idea identity");
    const ideaVersionId = privateId(
      resultCard.idea_version_id,
      "idea version identity",
    );
    if (
      job.conversation_id !== conversationId ||
      job.result_run_id !== backtestRunId ||
      run.conversation_id !== conversationId
    ) {
      throw new Error("Browser-captured job and run identities did not finalize together");
    }

    await page
      .getByRole("button", { name: label("chat.result_card.add_decision") })
      .click();
    await page
      .getByRole("button", {
        name: label(`chat.result_card.decision_states.${canaryDecisionState}`),
      })
      .click();
    await page
      .getByPlaceholder(label("chat.result_card.decision_note_placeholder"))
      .fill(canaryDecisionNote);
    const decisionResponsePromise = page.waitForResponse((response) => {
      let pathname = "";
      try {
        pathname = new URL(response.url()).pathname;
      } catch {
        return false;
      }
      return (
        response.request().method() === "POST" &&
        pathname.endsWith("/decision") &&
        pathname.includes("/api/v1/evidence-artifacts/")
      );
    });
    await page
      .getByRole("button", { name: label("chat.result_card.save_decision") })
      .click();
    const decisionResponse = await decisionResponsePromise;
    if (!decisionResponse.ok()) throw new Error("Rendered decision capture failed");
    const decisionPayload = record(await decisionResponse.json(), "decision payload");
    const decision = record(decisionPayload.decision, "decision");
    const decidedArtifact = record(
      decisionPayload.evidence_artifact,
      "decided evidence artifact",
    );
    const decisionNoteId = privateId(decision.id, "decision identity");
    if (
      decision.evidence_artifact_id !== evidenceArtifactId ||
      decision.idea_id !== ideaId ||
      decision.idea_version_id !== ideaVersionId ||
      decision.decision_state !== canaryDecisionState ||
      decidedArtifact.id !== evidenceArtifactId ||
      decidedArtifact.lifecycle !== "decided"
    ) {
      throw new Error("Rendered decision did not preserve canonical artifact identity");
    }

    await expect(
      page.getByText(label(`chat.result_card.decision_states.${canaryDecisionState}`), {
        exact: true,
      }),
    ).toBeVisible();
    await page.reload();
    await expect(
      page.getByText(label("chat.simulation_complete"), { exact: true }),
    ).toHaveCount(1, { timeout: 60_000 });
    await expect(
      page.getByText(label(`chat.result_card.decision_states.${canaryDecisionState}`), {
        exact: true,
      }),
    ).toBeVisible();

    await page.getByRole("button", { name: label("common.search") }).click();
    const searchResponsePromise = page.waitForResponse((response) => {
      try {
        const url = new URL(response.url());
        return (
          response.request().method() === "GET" &&
          url.pathname.endsWith("/api/v1/search") &&
          url.searchParams.get("q") === canarySearchQuery
        );
      } catch {
        return false;
      }
    });
    await page
      .getByPlaceholder(label("command_palette.search_placeholder"))
      .fill(canarySearchQuery);
    const searchResponse = await searchResponsePromise;
    if (!searchResponse.ok()) throw new Error("Rendered Omnisearch request failed");
    const searchPayload = record(await searchResponse.json(), "Omnisearch payload");
    const searchItems = Array.isArray(searchPayload.items) ? searchPayload.items : [];
    const matchingEvidence = searchItems
      .map((item) => record(item, "Omnisearch item"))
      .find(
        (item) =>
          item.type === "evidence" &&
          item.id === evidenceArtifactId &&
          item.conversation_id === conversationId &&
          item.lifecycle === "decided",
      );
    if (!matchingEvidence) {
      throw new Error("Omnisearch did not return the browser-created canonical evidence");
    }
    const evidenceTitle = String(matchingEvidence.title ?? "").trim();
    if (!evidenceTitle) throw new Error("Omnisearch evidence omitted a rendered title");
    await page
      .getByRole("button")
      .filter({ hasText: label("command_palette.type.evidence") })
      .filter({ hasText: evidenceTitle })
      .first()
      .click();
    await expect(
      page.getByText(label("chat.simulation_complete"), { exact: true }),
    ).toHaveCount(1, { timeout: 60_000 });
    if (new URL(page.url()).searchParams.get("conversation") !== conversationId) {
      throw new Error("Omnisearch did not reopen the canonical source conversation");
    }

    const blockingOverlay = page.locator(
      '[data-testid="blocking-overlay"], [role="alertdialog"], [aria-modal="true"][data-state="open"]',
    );
    await expect(blockingOverlay).toHaveCount(0);
    expect(browserErrors.consoleErrorCount).toBe(0);
    expect(browserErrors.pageErrorCount).toBe(0);

    await writeFile(
      handoffPath,
      `${JSON.stringify({
        schema_version: 1,
        source: "playwright",
        user_id: userId,
        conversation_id: conversationId,
        backtest_job_id: backtestJobId,
        backtest_run_id: backtestRunId,
        evidence_artifact_id: evidenceArtifactId,
        decision_note_id: decisionNoteId,
        idea_id: ideaId,
        idea_version_id: ideaVersionId,
        decision_state: canaryDecisionState,
        run_action_request_count: runBacktestRequests,
        assertions: {
          result_rendered_once: true,
          reload_hydrated: true,
          omnisearch_reopened_source: true,
          console_error_count: browserErrors.consoleErrorCount,
          page_error_count: browserErrors.pageErrorCount,
          blocking_overlay_present: false,
        },
      })}\n`,
      { encoding: "utf8", flag: "w", mode: 0o600 },
    );
    await chmod(handoffPath, 0o600);
  });

  test("deterministic/intercepted recovery is not deployed backend proof", async ({ page }) => {
    test.setTimeout(90_000);
    const retryPrompt = "Provocar recuperación tipada sin ejecutar un backtest";
    const fakeConversationId = "00000000-0000-4000-8000-000000000233";
    const fakeAssistantId = "00000000-0000-4000-8000-000000000234";
    let interceptedRunRequests = 0;

    await loginThroughRenderedUi(page);
    await page.route("**/api/v1/conversations", async (route) => {
      if (route.request().method() !== "POST") {
        await route.fallback();
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          conversation: {
            id: fakeConversationId,
            title: "Recuperación determinista",
            title_source: "default",
            pinned: false,
            archived: false,
            created_at: "2026-07-16T00:00:00Z",
            updated_at: "2026-07-16T00:00:00Z",
            language: "es-419",
          },
        }),
      });
    });
    await page.route("**/api/v1/chat/stream", async (route) => {
      const body = route.request().postDataJSON() as JsonRecord;
      const action = body.action;
      if (action && record(action, "intercepted chat action").type === "run_backtest") {
        interceptedRunRequests += 1;
      }
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: `data: ${JSON.stringify({
          type: "error",
          code: "deterministic_canary_error",
          message: label("chat.error_backtest"),
          message_id: fakeAssistantId,
          recovery_action: "retry_last_turn",
          retry_last_turn: { message: retryPrompt },
          recovery: {
            code: "runtime_failure",
            retryable: true,
            language: "es-419",
          },
        })}\n\n`,
      });
    });

    await page.getByTestId("chat-input").fill(retryPrompt);
    await page.getByTestId("chat-send").click();
    await expect(page.getByText(label("chat.error_backtest"), { exact: true })).toBeVisible();
    await expect(page.getByRole("button", { name: label("common.retry") })).toBeVisible();
    expect(interceptedRunRequests).toBe(0);
  });
});
