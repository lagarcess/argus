import { chmod, writeFile } from "node:fs/promises";
import {
  expect,
  test,
  type Page,
  type Request,
  type Response,
} from "@playwright/test";
import {
  latestAssistantMessage,
  ordinaryAnswerFailure,
  researchAnswerFailure,
} from "./support/private-alpha-canary-answers";

// The canary's browser checks never follow features: each one reads an API
// response or a product-owned test id, never result facts or feature copy.

type JsonRecord = Record<string, unknown>;
type CheckStatus = "passed" | "failed" | "not_run";
type CheckResult = {
  status: CheckStatus;
  reason?: string;
  sign_in_attempts?: number;
  conversation_id?: string;
  backtest_job_id?: string;
  backtest_run_id?: string;
};
type CheckContext = {
  page: Page;
  result: CheckResult;
  save: () => Promise<void>;
};
type JobSnapshot = { job: JsonRecord; run: JsonRecord | null };

const expectedUserId = process.env.ARGUS_CANARY_BROWSER_USER_ID;
const handoffPath = process.env.ARGUS_CANARY_BROWSER_CHECKS_HANDOFF;
const checkIds = (process.env.ARGUS_CANARY_BROWSER_CHECKS ?? "")
  .split("\n")
  .map((value) => value.trim())
  .filter(Boolean);
const chatPrompt = process.env.ARGUS_CANARY_BROWSER_CHAT_PROMPT;
const backtestPrompt = process.env.ARGUS_CANARY_BROWSER_BACKTEST_PROMPT;
const researchPrompt = process.env.ARGUS_CANARY_BROWSER_RESEARCH_PROMPT;
const artifactProbe =
  process.env.ARGUS_CANARY_BROWSER_ARTIFACT_PROBE ?? "none";
const redactionProbeValue =
  process.env.ARGUS_CANARY_BROWSER_REDACTION_PROBE_VALUE;
const labels = JSON.parse(
  process.env.ARGUS_CANARY_STATIC_LABELS_JSON ?? "{}",
) as Record<string, string>;

// A retried sign-in still reports its attempt count in the evidence.
const SIGN_IN_ATTEMPTS = 2;
const SIGN_IN_RETRY_DELAY_MS = 5_000;
const COMPOSER_RELEASE_TIMEOUT_MS = 240_000;
const PENDING_JOB_STATUSES = new Set(["queued", "running"]);

/** A check failure whose reason is safe to publish in canary evidence. */
class CheckFailure extends Error {
  constructor(readonly reason: string) {
    super(reason);
  }
}

/** Sign-in failed, so no later check can run. */
class SignInFailure extends CheckFailure {}

function reasonCode(...parts: Array<string | number>): string {
  const code = parts
    .map((part) => String(part).toLowerCase().replace(/[^a-z0-9]+/g, "_"))
    .join("_")
    .replace(/_+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 120);
  return code || "unknown";
}

function label(key: string): string {
  const value = labels[key];
  if (!value) throw new Error(`Missing authoritative static label: ${key}`);
  return value;
}

function requireConfig(value: string | undefined, name: string): string {
  if (!value?.trim()) throw new Error(`Missing browser canary config: ${name}`);
  return value;
}

function record(value: unknown): JsonRecord | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as JsonRecord)
    : null;
}

function privateId(value: unknown, reason: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new CheckFailure(reason);
  }
  return value;
}

async function writePrivateHandoff(
  path: string,
  payload: JsonRecord,
): Promise<void> {
  await writeFile(path, `${JSON.stringify(payload)}\n`, {
    encoding: "utf8",
    flag: "w",
    mode: 0o600,
  });
  await chmod(path, 0o600);
}

function apiPath(url: string): string | null {
  try {
    return new URL(url).pathname;
  } catch {
    return null;
  }
}

function isApiResponse(
  response: Response,
  suffix: string,
  method: string,
): boolean {
  return (
    apiPath(response.url())?.endsWith(`/api/v1${suffix}`) === true &&
    response.request().method() === method
  );
}

function isChatStreamRequest(request: Request): boolean {
  return (
    request.method() === "POST" &&
    apiPath(request.url())?.endsWith("/api/v1/chat/stream") === true
  );
}

function isRunBacktestRequest(request: Request): boolean {
  if (!isChatStreamRequest(request)) return false;
  try {
    return record(record(request.postDataJSON())?.action)?.type === "run_backtest";
  } catch {
    return false;
  }
}

async function problemCode(response: Response): Promise<string> {
  try {
    const code = record(await response.json())?.code;
    return typeof code === "string" && code ? code : "no_code";
  } catch {
    return "unreadable_body";
  }
}

/** The request once its body ends, null when it failed, undefined on timeout. */
function settledRequest(
  page: Page,
  matches: (request: Request) => boolean,
  timeout: number,
): Promise<Request | null | undefined> {
  const finished = page
    .waitForEvent("requestfinished", { predicate: matches, timeout })
    .then(
      (request) => request,
      () => undefined,
    );
  const failed = page
    .waitForEvent("requestfailed", { predicate: matches, timeout })
    .then(
      () => null,
      () => undefined,
    );
  return Promise.race([finished, failed]);
}

async function requireSettledOk(
  settled: Request | null | undefined,
  name: string,
): Promise<void> {
  if (settled === undefined) throw new CheckFailure(`${name}_timed_out`);
  if (settled === null) throw new CheckFailure(`${name}_request_failed`);
  const response = await settled.response();
  if (!response?.ok()) {
    throw new CheckFailure(reasonCode(name, "http", response?.status() ?? 0));
  }
}

async function openSignedInChat(page: Page): Promise<number> {
  const userId = requireConfig(expectedUserId, "user identity");
  const { cookies } = await page.context().storageState();
  if (
    !cookies.some((cookie) =>
      /^sb-[a-z0-9-]+-auth-token(?:\.\d+)?$/.test(cookie.name),
    )
  ) {
    throw new SignInFailure("storage_state_has_no_session");
  }

  let reason = "profile_not_requested";
  for (let attempt = 1; attempt <= SIGN_IN_ATTEMPTS; attempt += 1) {
    if (attempt > 1) await page.waitForTimeout(SIGN_IN_RETRY_DELAY_MS);
    const profile = page
      .waitForResponse((response) => isApiResponse(response, "/me", "GET"), {
        timeout: 60_000,
      })
      .catch(() => null);
    const navigated = await page
      .goto("/chat", { waitUntil: "domcontentloaded" })
      .then(
        () => true,
        () => false,
      );
    const response = await profile;
    if (!navigated) {
      reason = "chat_page_unreachable";
      continue;
    }
    if (!response) {
      reason = "profile_not_requested";
      continue;
    }
    if (!response.ok()) {
      reason = reasonCode(
        "profile_http",
        response.status(),
        await problemCode(response),
      );
      const status = response.status();
      if (status === 401 || status === 429 || status >= 500) continue;
      break;
    }
    const payload = record(await response.json().catch(() => null));
    if (record(payload?.user)?.id !== userId) {
      throw new SignInFailure("profile_identity_mismatch");
    }
    if (payload?.account_kind !== "registered") {
      throw new SignInFailure("profile_not_registered");
    }
    await expect(page.getByTestId("chat-input"))
      .toBeVisible({ timeout: 30_000 })
      .catch(() => {
        throw new SignInFailure("chat_input_not_visible");
      });
    return attempt;
  }
  throw new SignInFailure(reason);
}

async function sendTurn(
  { page, result, save }: CheckContext,
  prompt: string,
  turnTimeout: number,
): Promise<string> {
  const created = page
    .waitForResponse(
      (response) => isApiResponse(response, "/conversations", "POST"),
      { timeout: 60_000 },
    )
    .catch(() => null);
  const turn = settledRequest(
    page,
    (request) => isChatStreamRequest(request) && !isRunBacktestRequest(request),
    turnTimeout,
  );
  await page.getByTestId("chat-input").fill(prompt);
  await page.getByTestId("chat-send").click();

  const conversation = await created;
  if (!conversation) throw new CheckFailure("conversation_not_created");
  if (!conversation.ok()) {
    throw new CheckFailure(
      reasonCode("conversation_http", conversation.status()),
    );
  }
  const conversationId = privateId(
    record(record(await conversation.json().catch(() => null))?.conversation)
      ?.id,
    "conversation_id_missing",
  );
  result.conversation_id = conversationId;
  await save();

  await requireSettledOk(await turn, "chat_turn");
  await expect(page.getByTestId("chat-input"))
    .toHaveAttribute("contenteditable", "true", {
      timeout: COMPOSER_RELEASE_TIMEOUT_MS,
    })
    .catch(() => {
      throw new CheckFailure("chat_turn_kept_composer_locked");
    });
  const recoveryShown =
    (await page.getByTestId("user-turn-recovery").count()) +
    (await page.getByTestId("user-turn-retry").count());
  if (recoveryShown > 0) throw new CheckFailure("chat_turn_offered_recovery");
  return conversationId;
}

/** The newest persisted assistant message as the chat renders it, read by reopening the chat. */
async function persistedAssistantMessage(
  page: Page,
  conversationId: string,
): Promise<ReturnType<typeof latestAssistantMessage>> {
  const messagesPath = `/api/v1/conversations/${conversationId}/messages`;
  const messages = page
    .waitForResponse(
      (response) =>
        apiPath(response.url()) === messagesPath &&
        response.request().method() === "GET",
      { timeout: 60_000 },
    )
    .catch(() => null);
  const navigated = await page
    .goto(`/chat?conversation=${encodeURIComponent(conversationId)}`, {
      waitUntil: "domcontentloaded",
    })
    .then(
      () => true,
      () => false,
    );
  const response = await messages;
  if (!navigated || !response?.ok()) {
    throw new CheckFailure(
      reasonCode("messages_http", response?.status() ?? 0),
    );
  }
  return latestAssistantMessage(await response.json().catch(() => null));
}

function watchBacktestJobs(page: Page) {
  let latest: JobSnapshot | null = null;
  const isTerminal = (snapshot: JobSnapshot | null) =>
    snapshot !== null && !PENDING_JOB_STATUSES.has(String(snapshot.job.status));
  page.on("response", (response) => {
    const path = apiPath(response.url());
    if (
      response.request().method() !== "GET" ||
      !path ||
      !/\/api\/v1\/backtest-jobs\/[^/]+$/.test(path) ||
      !response.ok()
    ) {
      return;
    }
    void response.json().then(
      (value: unknown) => {
        const payload = record(value);
        const job = record(payload?.job);
        if (job && !isTerminal(latest)) {
          latest = { job, run: record(payload?.run) };
        }
      },
      () => undefined,
    );
  });
  return {
    latest: () => latest,
    terminal: () => (isTerminal(latest) ? latest : null),
  };
}

async function signedInChatAnswer(context: CheckContext): Promise<void> {
  const { page, result, save } = context;
  result.sign_in_attempts = await openSignedInChat(page);
  await save();
  const prompt = requireConfig(chatPrompt, "chat prompt");
  const conversationId = await sendTurn(context, prompt, 180_000);
  const messages = page.locator("[data-message-id]");
  const answer =
    (await messages.count()) >= 2
      ? (await messages.last().innerText()).trim()
      : "";
  if (!answer || answer === prompt.trim()) {
    throw new CheckFailure("assistant_answer_missing");
  }
  const failure = ordinaryAnswerFailure(
    await persistedAssistantMessage(page, conversationId),
  );
  if (failure) throw new CheckFailure(reasonCode(failure));
}

async function backtestCompletes(context: CheckContext): Promise<void> {
  const { page, result, save } = context;
  await openSignedInChat(page);
  const jobs = watchBacktestJobs(page);
  const conversationId = await sendTurn(
    context,
    requireConfig(backtestPrompt, "backtest prompt"),
    240_000,
  );

  const runButton = page
    .getByRole("button", {
      name: label("chat.confirmation.actions.run_backtest"),
    })
    .last();
  await expect(runButton)
    .toBeVisible({ timeout: 30_000 })
    .catch(() => {
      throw new CheckFailure("confirmation_not_offered");
    });
  const runAction = settledRequest(page, isRunBacktestRequest, 180_000);
  await runButton.click();
  await requireSettledOk(await runAction, "run_action");

  try {
    await expect
      .poll(() => jobs.terminal() !== null, {
        timeout: 420_000,
        intervals: [2_000],
      })
      .toBe(true);
  } catch {
    const pending = jobs.latest();
    if (typeof pending?.job.id === "string") {
      result.backtest_job_id = pending.job.id;
    }
    throw new CheckFailure(
      reasonCode(
        "backtest_job_not_finished",
        String(pending?.job.status ?? "never_polled"),
      ),
    );
  }

  const { job, run } = jobs.terminal() as JobSnapshot;
  result.backtest_job_id = privateId(job.id, "backtest_job_id_missing");
  await save();
  if (job.status !== "succeeded") {
    throw new CheckFailure(
      reasonCode(
        "backtest_job",
        String(job.status),
        String(job.failure_code ?? "no_code"),
      ),
    );
  }
  if (job.conversation_id !== conversationId) {
    throw new CheckFailure("backtest_job_conversation_mismatch");
  }
  if (run?.status !== "completed" || run.id !== job.result_run_id) {
    throw new CheckFailure("backtest_run_not_completed");
  }
  result.backtest_run_id = privateId(run.id, "backtest_run_id_missing");
}

async function researchAnswerWithSources(
  context: CheckContext,
): Promise<void> {
  const { page } = context;
  await openSignedInChat(page);
  const conversationId = await sendTurn(
    context,
    requireConfig(researchPrompt, "research prompt"),
    300_000,
  );
  await expect(page.getByTestId("research-sources-open").last())
    .toBeVisible({ timeout: 240_000 })
    .catch(() => {
      throw new CheckFailure("research_sources_missing");
    });
  const failure = researchAnswerFailure(
    await persistedAssistantMessage(page, conversationId),
  );
  if (failure) throw new CheckFailure(reasonCode(failure));
}

const CHECKS = new Map<string, (context: CheckContext) => Promise<void>>([
  ["signed_in_chat_answer", signedInChatAnswer],
  ["backtest_completes", backtestCompletes],
  ["research_answer_with_sources", researchAnswerWithSources],
]);

test("private-alpha canary browser checks", async ({ page }) => {
  test.setTimeout(1_800_000);
  const path = requireConfig(handoffPath, "checks handoff");
  const userId = requireConfig(expectedUserId, "user identity");
  if (checkIds.length === 0 || checkIds.some((id) => !CHECKS.has(id))) {
    throw new Error("Browser canary checks do not match the release profile");
  }

  const results: Record<string, CheckResult> = Object.fromEntries(
    checkIds.map((id) => [id, { status: "not_run" }]),
  );
  const save = () =>
    writePrivateHandoff(path, {
      schema_version: 2,
      source: "playwright",
      user_id: userId,
      checks: results,
    });
  await save();

  if (artifactProbe !== "none") {
    await openSignedInChat(page);
    await page
      .getByTestId("chat-input")
      .fill(requireConfig(redactionProbeValue, "redaction probe value"));
    await expect(page.getByTestId("forced-canary-failure")).toBeVisible();
  }

  for (const id of checkIds) {
    const result = results[id];
    let signInFailed = false;
    try {
      await CHECKS.get(id)?.({ page, result, save });
      result.status = "passed";
    } catch (error) {
      result.status = "failed";
      result.reason =
        error instanceof CheckFailure ? error.reason : "check_threw";
      signInFailed = error instanceof SignInFailure;
    }
    await save();
    if (signInFailed) break;
  }

  const failures = checkIds
    .filter((id) => results[id].status !== "passed")
    .map((id) => `${id}: ${results[id].reason ?? "not_run"}`);
  expect(failures, "every canary browser check must pass").toEqual([]);
});
