import {
  expect,
  test,
  type Page,
  type Route,
} from "@playwright/test";

const CONVERSATION_ID = "continuity-conversation";
const INITIAL_CONFIRMATION_ID = "continuity-confirmation-initial";
const EDITED_CONFIRMATION_ID = "continuity-confirmation-costs";
const JOB_ID = "continuity-job";
const RUN_ID = "continuity-run";
const CREATED_AT = "2026-07-25T12:00:00Z";

type JsonRecord = Record<string, unknown>;

type StreamRequest = {
  conversation_id: string;
  message?: string;
  language?: string;
  action?: {
    type?: string;
    label?: string;
    payload?: JsonRecord;
    presentation?: string;
  };
};

type ApiMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  metadata: JsonRecord;
};

function userMessage(
  id: string,
  content: string,
  metadata: JsonRecord = {},
): ApiMessage {
  return {
    id,
    conversation_id: CONVERSATION_ID,
    role: "user",
    content,
    created_at: CREATED_AT,
    metadata,
  };
}

function assistantMessage(
  id: string,
  content: string,
  metadata: JsonRecord = {},
): ApiMessage {
  return {
    id,
    conversation_id: CONVERSATION_ID,
    role: "assistant",
    content,
    created_at: CREATED_AT,
    metadata,
  };
}

function runAction(confirmationId: string) {
  return {
    id: `run-${confirmationId}`,
    type: "run_backtest",
    label: "Run backtest",
    labelKey: "chat.confirmation.actions.run_backtest",
    presentation: "confirmation",
    payload: {
      confirmation_id: confirmationId,
      conversation_id: CONVERSATION_ID,
      launch_payload_hash: `launch-${confirmationId}`,
    },
  };
}

function confirmation(
  confirmationId: string,
  options: {
    feeRate?: number;
    slippageRate?: number;
    state?: "active" | "superseded";
    status?: "ready_to_run" | "run_complete";
  } = {},
) {
  const feeRate = options.feeRate ?? 0;
  const slippageRate = options.slippageRate ?? 0;
  const state = options.state ?? "active";
  const status = options.status ?? "ready_to_run";
  return {
    confirmation_id: confirmationId,
    confirmation_state: state,
    title: "AAPL buy and hold",
    summary: "Buy and hold AAPL and compare it with SPY.",
    status,
    statusLabel: status === "run_complete" ? "Run complete" : "Ready to run",
    strategy_type: "buy_and_hold",
    asset_class: "equity",
    date_range: {
      start: "2024-01-01",
      end: "2024-12-31",
      display: "January 1, 2024 to December 31, 2024",
    },
    rows: [
      { key: "strategy", label: "Strategy", value: "Buy and hold" },
      { key: "assets", label: "Assets", value: "AAPL" },
      { key: "starting_capital", label: "Starting capital", value: "$10,000" },
      {
        key: "period",
        label: "Period",
        value: "January 1, 2024 to December 31, 2024",
      },
      { key: "benchmark", label: "Benchmark", value: "SPY" },
    ],
    display_facts: {
      timeframe: "1D",
      benchmark_symbol: "SPY",
      fees: feeRate,
      slippage: slippageRate,
    },
    capabilities: { execution_costs_editable: true },
    assumptions: [
      "Long-only, equal-weight run",
      feeRate || slippageRate
        ? "0.10% fee and 0.05% slippage per trade"
        : "No fees or slippage",
      "Benchmark: SPY",
    ],
    actions: state === "active" ? [runAction(confirmationId)] : [],
  };
}

function resultCard() {
  return {
    title: "AAPL buy and hold",
    symbols: ["AAPL"],
    strategy_label: "Buy and hold",
    asset_class: "equity",
    date_range: {
      start: "2024-01-01",
      end: "2024-12-31",
      display: "January 1, 2024 to December 31, 2024",
    },
    status_label: "Simulation Complete",
    rows: [
      { key: "ending_value", label: "Ending value", value: "$11,240" },
      { key: "total_return_pct", label: "Total return", value: "+12.4%" },
      { key: "benchmark_delta_pct", label: "Vs benchmark", value: "+2.3 pts" },
      { key: "max_drawdown_pct", label: "Max drawdown", value: "-8.1%" },
    ],
    benchmark_note: "AAPL beat SPY by 2.3 percentage points.",
    assumptions: [
      "$10,000 starting capital",
      "Long-only, equal-weight run",
      "0.10% fee and 0.05% slippage per trade",
      "Benchmark: SPY",
    ],
    execution_costs: {
      fee_bps: 10,
      slippage_bps: 5,
      gross_total_return_pct: 12.7,
      net_total_return_pct: 12.4,
      return_drag_pct: 0.3,
      benchmark_treatment: "same_modeled_costs",
    },
    actions: [],
    chart: null,
  };
}

function completedRun() {
  return {
    id: RUN_ID,
    conversation_id: CONVERSATION_ID,
    strategy_id: null,
    status: "completed",
    asset_class: "equity",
    symbols: ["AAPL"],
    allocation_method: "equal_weight",
    benchmark_symbol: "SPY",
    metrics: {
      aggregate: {
        ending_value: 11240,
        total_return_pct: 12.4,
        benchmark_delta_pct: 2.3,
        max_drawdown_pct: -8.1,
      },
      by_symbol: {},
    },
    config_snapshot: {
      template: "buy_and_hold",
      symbols: ["AAPL"],
      asset_class: "equity",
      benchmark_symbol: "SPY",
      initial_capital: 10000,
      timeframe: "1D",
      date_range: { start: "2024-01-01", end: "2024-12-31" },
      execution_costs: { fee_bps: 10, slippage_bps: 5 },
    },
    conversation_result_card: resultCard(),
    created_at: CREATED_AT,
  };
}

function sse(frames: Array<JsonRecord | "[DONE]">): string {
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
  frames: Array<JsonRecord | "[DONE]">,
) {
  await route.fulfill({
    status: 200,
    contentType: "text/event-stream",
    headers: { "x-request-id": "mock-continuity-request" },
    body: sse(frames),
  });
}

async function fulfillJson(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function installMockApi(page: Page) {
  const messages: ApiMessage[] = [];
  const streamRequests: StreamRequest[] = [];
  const unexpectedApiRequests: string[] = [];
  let runSubmissionCount = 0;

  await page.addInitScript(() => {
    window.localStorage.setItem("i18nextLng", "en");
  });

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === "/api/v1/me") {
      return fulfillJson(route, {
        user: {
          id: "continuity-user",
          email: "continuity@example.com",
          username: "continuity-user",
          display_name: "Continuity User",
          language: "en",
          locale: "en-US",
          onboarding: {
            completed: true,
            stage: "completed",
            language_confirmed: true,
            primary_goal: "test_stock_idea",
          },
        },
      });
    }
    if (path === `/api/v1/conversations/${CONVERSATION_ID}/messages`) {
      return fulfillJson(route, { items: messages, next_cursor: null });
    }
    if (path === "/api/v1/conversations") {
      const conversationRecord = {
        id: CONVERSATION_ID,
        title: "AAPL continuity",
        title_source: "ai_generated",
        pinned: false,
        archived: false,
        language: "en",
        created_at: CREATED_AT,
        updated_at: CREATED_AT,
      };
      return fulfillJson(
        route,
        request.method() === "POST"
          ? { conversation: conversationRecord }
          : { items: [conversationRecord], next_cursor: null },
      );
    }
    if (path === "/api/v1/history") {
      return fulfillJson(route, {
        items: [
          {
            type: "chat",
            id: CONVERSATION_ID,
            conversation_id: CONVERSATION_ID,
            title: "AAPL continuity",
            subtitle: "AAPL continuity",
            pinned: false,
            created_at: CREATED_AT,
          },
        ],
        next_cursor: null,
      });
    }
    if (path === "/api/v1/search") {
      return fulfillJson(route, {
        items: [],
        next_cursor: null,
        ledger_groups: [],
      });
    }
    if (path === "/api/v1/chat/starter-prompts") {
      return fulfillJson(route, { prompts: [] });
    }
    if (path === "/api/v1/chat/stream") {
      const body = request.postDataJSON() as StreamRequest;
      streamRequests.push(body);

      if (body.action?.type === "run_backtest") {
        runSubmissionCount += 1;
        const activeConfirmationId = body.action.payload?.confirmation_id;
        if (activeConfirmationId !== EDITED_CONFIRMATION_ID) {
          return fulfillJson(
            route,
            {
              type: "https://api.argus.app/problems/confirmation-action-stale",
              title: "Confirmation action is stale",
              status: 409,
              detail: "Only the latest confirmation can run.",
              code: "confirmation_action_stale_card",
              request_id: "mock-continuity-request",
            },
            409,
          );
        }
        messages.splice(
          0,
          messages.length,
          userMessage("message-user-initial", "Test buy and hold AAPL."),
          assistantMessage(
            "message-clarification",
            "Which date window should I use for AAPL?",
          ),
          userMessage("message-user-period", "Use calendar year 2024."),
          assistantMessage("message-confirmation-edited", "", {
            confirmation_card: confirmation(EDITED_CONFIRMATION_ID, {
              feeRate: 0.001,
              slippageRate: 0.0005,
              state: "superseded",
              status: "run_complete",
            }),
          }),
          userMessage("message-user-run", "Run backtest", {
            chat_action: body.action,
          }),
          assistantMessage(
            "message-result",
            "Quick take: AAPL returned 12.4% after modeled costs.",
            {
              result_card: resultCard(),
              result_run_id: RUN_ID,
              latest_run_id: RUN_ID,
              backtest_job_id: JOB_ID,
              result_conversation_id: CONVERSATION_ID,
            },
          ),
        );
        return fulfillSse(route, [
          { type: "stage_start", stage: "execute" },
          {
            type: "final",
            payload: {
              stage_outcome: "completed",
              assistant_response:
                "Quick take: AAPL returned 12.4% after modeled costs.",
              run: completedRun(),
              message_id: "message-result",
            },
          },
          "[DONE]",
        ]);
      }

      if (body.message === "Test buy and hold AAPL.") {
        const clarification = {
          kind: "clarification",
          reason_code: "missing_period",
          prompt_source: "llm_generated",
          requested_field: "date_range",
          requested_fields: ["date_range"],
          semantic_needs: ["period"],
          payload: {
            strategy: {
              strategy_type: "buy_and_hold",
              asset_universe: ["AAPL"],
              asset_class: "equity",
              comparison_baseline: "SPY",
              starting_capital: 10000,
            },
          },
          options: [],
        };
        messages.splice(
          0,
          messages.length,
          userMessage("message-user-initial", body.message),
          assistantMessage(
            "message-clarification",
            "Which date window should I use for AAPL?",
            { clarification },
          ),
        );
        return fulfillSse(route, [
          { type: "stage_start", stage: "clarify" },
          {
            type: "token",
            content: "Which date window should I use for AAPL?",
          },
          {
            type: "final",
            payload: {
              stage_outcome: "await_user_reply",
              assistant_prompt: "Which date window should I use for AAPL?",
              clarification,
              message_id: "message-clarification",
            },
          },
          "[DONE]",
        ]);
      }

      if (body.message === "Use calendar year 2024.") {
        messages.push(
          userMessage("message-user-period", body.message),
          assistantMessage("message-confirmation-initial", "", {
            confirmation_card: confirmation(INITIAL_CONFIRMATION_ID),
          }),
        );
        return fulfillSse(route, [
          { type: "stage_start", stage: "confirm" },
          {
            type: "final",
            payload: {
              stage_outcome: "ready_for_confirmation",
              confirmation: confirmation(INITIAL_CONFIRMATION_ID),
              message_id: "message-confirmation-initial",
            },
          },
          "[DONE]",
        ]);
      }

      if (
        body.message ===
        "Set fees to 0.1% and slippage to 0.05% per trade."
      ) {
        const prior = messages.find(
          (message) => message.id === "message-confirmation-initial",
        );
        if (prior) {
          prior.metadata.confirmation_card = confirmation(
            INITIAL_CONFIRMATION_ID,
            { state: "superseded" },
          );
        }
        messages.push(
          userMessage("message-user-costs", body.message),
          assistantMessage("message-confirmation-edited", "", {
            confirmation_card: confirmation(EDITED_CONFIRMATION_ID, {
              feeRate: 0.001,
              slippageRate: 0.0005,
            }),
          }),
        );
        return fulfillSse(route, [
          { type: "stage_start", stage: "confirm" },
          {
            type: "final",
            payload: {
              stage_outcome: "ready_for_confirmation",
              confirmation: confirmation(EDITED_CONFIRMATION_ID, {
                feeRate: 0.001,
                slippageRate: 0.0005,
              }),
              message_id: "message-confirmation-edited",
            },
          },
          "[DONE]",
        ]);
      }

      return fulfillJson(
        route,
        {
          type: "https://api.argus.app/problems/unexpected-test-request",
          title: "Unexpected test request",
          status: 422,
          detail: "The mocked journey did not define this turn.",
          code: "unexpected_test_request",
          request_id: "mock-continuity-request",
        },
        422,
      );
    }

    unexpectedApiRequests.push(`${request.method()} ${path}`);
    return fulfillJson(route, {
      type: "https://api.argus.app/problems/not-found",
      title: "Not found",
      status: 404,
      detail: "The deterministic harness does not expose this endpoint.",
      code: "not_found",
      request_id: "mock-continuity-request",
    }, 404);
  });

  return {
    streamRequests,
    unexpectedApiRequests,
    get runSubmissionCount() {
      return runSubmissionCount;
    },
  };
}

test.describe.serial("Argus always progresses deterministic browser contract", () => {
  test("clarifies, edits costs without executing, runs once, and reloads one result", async ({
    page,
  }) => {
    const api = await installMockApi(page);

    await page.goto("/chat", { waitUntil: "networkidle" });
    await expect(page.getByTestId("chat-input")).toBeVisible({
      timeout: 15_000,
    });

    await page.getByTestId("chat-input").fill("Test buy and hold AAPL.");
    await page.getByTestId("chat-send").click();
    await expect(
      page.getByText("Which date window should I use for AAPL?", {
        exact: true,
      }),
    ).toBeVisible();

    await page.getByTestId("chat-input").fill("Use calendar year 2024.");
    await page.getByTestId("chat-send").click();
    await expect(
      page.getByRole("button", { name: "Run backtest", exact: true }),
    ).toBeVisible();

    const requestCountBeforeEdit = api.streamRequests.length;
    await page.getByTestId("edit-execution-costs").click();
    await expect(page.getByTestId("execution-cost-editor")).toBeVisible();
    expect(api.streamRequests).toHaveLength(requestCountBeforeEdit);
    expect(api.runSubmissionCount).toBe(0);

    const costEditor = page.getByTestId("execution-cost-editor");
    await costEditor.getByLabel("Fee % per trade").fill("0.1");
    await costEditor.getByLabel("Slippage % per trade").fill("0.05");
    await costEditor.getByRole("button", { name: "Apply" }).click();

    await expect
      .poll(() => api.streamRequests.at(-1)?.message)
      .toBe("Set fees to 0.1% and slippage to 0.05% per trade.");
    expect(api.streamRequests.at(-1)?.action).toBeUndefined();
    expect(api.runSubmissionCount).toBe(0);
    await expect(
      page.getByRole("button", { name: "Run backtest", exact: true }),
    ).toBeVisible();

    await page
      .getByRole("button", { name: "Run backtest", exact: true })
      .click();
    await expect(page.getByText("Simulation Complete", { exact: true })).toBeVisible();
    await expect(
      page.getByText(
        "Quick take: AAPL returned 12.4% after modeled costs.",
        { exact: true },
      ),
    ).toBeVisible();
    expect(api.runSubmissionCount).toBe(1);
    expect(
      api.streamRequests.filter(
        (request) => request.action?.type === "run_backtest",
      ),
    ).toHaveLength(1);

    await page.reload({ waitUntil: "networkidle" });
    await expect(page.getByText("Simulation Complete", { exact: true })).toHaveCount(
      1,
    );
    await expect(
      page.getByText(
        "Quick take: AAPL returned 12.4% after modeled costs.",
        { exact: true },
      ),
    ).toHaveCount(1);
    expect(api.runSubmissionCount).toBe(1);
    expect(api.unexpectedApiRequests).toEqual([]);
  });
});
