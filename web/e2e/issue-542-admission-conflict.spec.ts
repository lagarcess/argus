import { expect, test, type Page, type Route } from "@playwright/test";

const CONVERSATION_ID = "conv-issue-542";
const SPENT_CONFIRMATION_ID = "confirm-issue-542-spent";
const FRESH_CONFIRMATION_ID = "confirm-issue-542-fresh";
const FAILED_ACTION_ID = "failed-action-issue-542";
const CREATED_AT = "2026-09-04T12:00:00Z";
const SYMBOLS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"];
const FAILURE_MESSAGE =
  "This confirmation had already been used for a different setup, so I did not start another backtest. Use Retry below to create a fresh confirmation, then run the new card.";

type StreamRequest = {
  action?: {
    type: string;
    payload?: Record<string, unknown>;
  };
};

type PersistedMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  metadata: Record<string, unknown>;
};

function message(
  id: string,
  role: "user" | "assistant",
  content: string,
  metadata: Record<string, unknown> = {},
): PersistedMessage {
  return {
    id,
    conversation_id: CONVERSATION_ID,
    role,
    content,
    created_at: CREATED_AT,
    metadata,
  };
}

function confirmationCard(confirmationId: string) {
  const action = (type: string, label: string) => ({
    id: `${type}-${confirmationId}`,
    type,
    label,
    presentation: "confirmation",
    payload: {
      confirmation_id: confirmationId,
      conversation_id: CONVERSATION_ID,
      launch_payload_hash: `launch-hash-${confirmationId}`,
    },
  });
  return {
    confirmation_id: confirmationId,
    confirmation_state: "active",
    title: "Five-stock buy and hold",
    summary: "Buy and hold five equities with SPY as the comparison benchmark.",
    status: "ready_to_run",
    statusLabel: "Ready to run",
    strategy_type: "buy_and_hold",
    asset_class: "equity",
    date_range: {
      start: "2025-09-04",
      end: "2026-09-04",
      display: "September 4, 2025 to September 4, 2026",
    },
    rows: [
      { key: "strategy", label: "Strategy", value: "Buy and hold" },
      { key: "assets", label: "Assets", value: SYMBOLS.join(", ") },
      { key: "starting_capital", label: "Starting capital", value: "$100,000" },
      {
        key: "period",
        label: "Period",
        value: "September 4, 2025 to September 4, 2026",
      },
      { key: "benchmark", label: "Benchmark", value: "SPY" },
    ],
    assumptions: ["Long-only, daily close data", "No fees or slippage"],
    actions: [
      action("run_backtest", "Run backtest"),
      action("change_dates", "Change dates"),
      action("change_asset", "Change asset"),
      action("adjust_assumptions", "Adjust assumptions"),
      action("cancel_confirmation", "Cancel"),
    ],
  };
}

function failedActionReference() {
  return {
    artifact_kind: "failed_action",
    artifact_id: FAILED_ACTION_ID,
    artifact_status: "failed",
    metadata: {
      retryable: true,
      recovery_mode: "reopen_confirmation",
      launch_payload: {
        strategy_type: "buy_and_hold",
        symbols: SYMBOLS,
        initial_capital: 100000,
        date_range: { start: "2025-09-04", end: "2026-09-04" },
      },
    },
  };
}

function failedJob() {
  return {
    id: "job-issue-542-conflict",
    conversation_id: CONVERSATION_ID,
    request_message_id: "msg-user-run-issue-542",
    confirmation_message_id: "msg-confirmation-issue-542",
    operation_scope: "chat.run_backtest",
    status: "failed",
    result_run_id: null,
    failure_code: "idempotency_conflict",
    failure_detail: "confirmation_identity_already_spent",
    retryable: false,
    queued_at: CREATED_AT,
    started_at: null,
    finished_at: CREATED_AT,
    created_at: CREATED_AT,
    updated_at: CREATED_AT,
  };
}

function sse(frames: Array<Record<string, unknown> | "[DONE]">) {
  return frames
    .map((frame) =>
      frame === "[DONE]"
        ? "data: [DONE]\n\n"
        : `data: ${JSON.stringify(frame)}\n\n`,
    )
    .join("");
}

async function fulfillSse(
  route: Route,
  frames: Array<Record<string, unknown> | "[DONE]">,
) {
  await route.fulfill({
    status: 200,
    contentType: "text/event-stream",
    body: sse(frames),
  });
}

async function mockIssue542Api(page: Page) {
  await page.addInitScript(() => {
    window.localStorage.setItem("i18nextLng", "en");
  });
  const streamRequests: StreamRequest[] = [];
  const unexpectedRequests: string[] = [];
  const messages: PersistedMessage[] = [
    message(
      "msg-user-issue-542-confirm",
      "user",
      "Buy and hold AAPL, MSFT, NVDA, GOOGL, and AMZN with $100,000 through today.",
    ),
    message("msg-confirmation-issue-542", "assistant", "", {
      confirmation_card: confirmationCard(SPENT_CONFIRMATION_ID),
    }),
  ];

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;
    const json = (body: unknown) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(body),
      });

    if (request.method() === "OPTIONS") {
      return route.fulfill({ status: 204 });
    }
    if (path === "/api/v1/me") {
      return json({
        user: {
          id: "dev-user",
          email: "dev@example.com",
          username: "dev",
          display_name: "Mock Developer",
          language: "en",
          locale: "en-US",
        },
      });
    }
    if (path === "/api/v1/conversations") {
      return json({
        items: [
          {
            id: CONVERSATION_ID,
            title: "Issue 542 admission conflict",
            title_source: "ai_generated",
            pinned: false,
            archived: false,
            created_at: CREATED_AT,
            updated_at: CREATED_AT,
            language: "en",
          },
        ],
        next_cursor: null,
      });
    }
    if (path === `/api/v1/conversations/${CONVERSATION_ID}/messages`) {
      return json({ items: messages, next_cursor: null });
    }
    if (path === `/api/v1/conversations/${CONVERSATION_ID}/activity`) {
      return json({
        operation: { status: "idle", kind: null, updated_at: CREATED_AT },
        attention: { status: "none", cursor: null },
      });
    }
    if (path === "/api/v1/history") {
      return json({ items: [], next_cursor: null });
    }
    if (path === "/api/v1/search") {
      return json({ items: [], next_cursor: null });
    }
    if (path === "/api/v1/memory/availability") {
      return json({ available: false, reason: "disabled" });
    }
    if (path === "/api/v1/chat/stream") {
      const body = request.postDataJSON() as StreamRequest;
      streamRequests.push(body);
      if (body.action?.type === "run_backtest") {
        const job = failedJob();
        const failedAction = failedActionReference();
        messages.splice(
          0,
          messages.length,
          message(
            "msg-user-issue-542-confirm",
            "user",
            "Buy and hold AAPL, MSFT, NVDA, GOOGL, and AMZN with $100,000 through today.",
          ),
          message("msg-confirmation-issue-542", "assistant", "", {
            confirmation_card: {
              ...confirmationCard(SPENT_CONFIRMATION_ID),
              confirmation_state: "superseded",
              status: "not_completed",
              statusLabel: "Not completed",
              actions: [],
            },
          }),
          message("msg-user-run-issue-542", "user", "Run backtest", {
            chat_action: body.action,
          }),
          message("msg-assistant-job-issue-542", "assistant", FAILURE_MESSAGE, {
            backtest_job: job,
            backtest_job_id: job.id,
            latest_failed_action_reference: failedAction,
          }),
        );
        return fulfillSse(route, [
          { type: "stage_start", stage: "execute" },
          {
            type: "final",
            payload: {
              stage_outcome: "execution_failed_terminally",
              assistant_response: FAILURE_MESSAGE,
              backtest_job: job,
              latest_failed_action_reference: failedAction,
              message_id: "msg-assistant-job-issue-542",
            },
          },
          "[DONE]",
        ]);
      }
      if (body.action?.type === "retry_failed_action") {
        const confirmation = confirmationCard(FRESH_CONFIRMATION_ID);
        messages.push(
          message("msg-user-retry-issue-542", "user", "Retry", {
            chat_action: body.action,
          }),
          message("msg-confirmation-issue-542-fresh", "assistant", "", {
            confirmation_card: confirmation,
          }),
        );
        return fulfillSse(route, [
          { type: "stage_start", stage: "confirm" },
          {
            type: "final",
            payload: {
              stage_outcome: "ready_for_confirmation",
              confirmation,
              message_id: "msg-confirmation-issue-542-fresh",
            },
          },
          "[DONE]",
        ]);
      }
    }

    unexpectedRequests.push(`${request.method()} ${path}`);
    return route.fulfill({
      status: 501,
      contentType: "application/json",
      body: JSON.stringify({ detail: "Unexpected browser-test request" }),
    });
  });

  return { streamRequests, unexpectedRequests };
}

test("admission conflict stays specific and retryable live and after reload", async ({
  page,
}) => {
  await page.setViewportSize({ width: 1440, height: 1000 });
  const browserErrors: string[] = [];
  page.on("console", (entry) => {
    if (entry.type() === "error") browserErrors.push(entry.text());
  });
  page.on("pageerror", (error) => browserErrors.push(error.message));
  page.on("requestfailed", (request) => {
    browserErrors.push(
      `${request.failure()?.errorText ?? "request failed"}: ${request.url()}`,
    );
  });
  const api = await mockIssue542Api(page);
  await page.goto(`/chat?conversation=${CONVERSATION_ID}`, {
    waitUntil: "networkidle",
  });

  for (const symbol of SYMBOLS) {
    await expect(page.getByText(symbol, { exact: true })).toBeVisible();
  }
  await expect(page.getByText("$100,000", { exact: true })).toBeVisible();
  await expect(
    page.getByText("Sep 4, 2025 → Sep 4, 2026", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Run backtest" }).click();

  await expect(page.getByText(FAILURE_MESSAGE)).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry", exact: true })).toBeVisible();
  const evidenceDir = process.env.ARGUS_EVIDENCE_DIR;
  if (evidenceDir) {
    await page.screenshot({
      path: `${evidenceDir}/admission-conflict-live.png`,
      fullPage: true,
    });
  }

  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText(FAILURE_MESSAGE)).toBeVisible();
  await expect(page.getByRole("button", { name: "Retry", exact: true })).toBeVisible();
  if (evidenceDir) {
    await page.screenshot({
      path: `${evidenceDir}/admission-conflict-reload.png`,
      fullPage: true,
    });
  }

  await page.getByRole("button", { name: "Retry", exact: true }).click();
  await expect.poll(() => api.streamRequests.length).toBe(2);
  expect(api.streamRequests[1]?.action).toMatchObject({
    type: "retry_failed_action",
    payload: { failed_action_id: FAILED_ACTION_ID },
  });
  await expect(page.getByText("Ready to run", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run backtest" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "Retry", exact: true })).toHaveCount(0);
  if (evidenceDir) {
    await page.screenshot({
      path: `${evidenceDir}/retry-fresh-confirmation.png`,
      fullPage: true,
    });
  }

  expect(api.unexpectedRequests).toEqual([]);
  expect(browserErrors).toEqual([]);
});
