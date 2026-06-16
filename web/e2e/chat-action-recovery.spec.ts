import { expect, test, type Page, type Route } from "@playwright/test";

const CONVERSATION_ID = "conv-actions";
const RUN_ID = "run-actions";
const CONFIRMATION_ID = "confirm-actions";
const CREATED_AT = "2026-06-16T12:00:00Z";

type StreamRequest = {
  conversation_id: string;
  message?: string;
  language?: string;
  action?: {
    type: string;
    label?: string;
    labelKey?: string;
    payload?: Record<string, unknown>;
    presentation?: string;
  };
};

type ApiMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  metadata?: Record<string, unknown>;
};

type MockChatApi = {
  streamRequests: StreamRequest[];
  feedbackRequests: Array<Record<string, unknown>>;
};

type MockChatApiOptions = {
  language?: "en" | "es-419";
};

function baseConversation(language = "en") {
  return {
    id: CONVERSATION_ID,
    title: "AAPL readiness",
    title_source: "ai_generated",
    pinned: false,
    archived: false,
    created_at: CREATED_AT,
    updated_at: CREATED_AT,
    language,
  };
}

function mockUser(language = "en") {
  return {
    id: "dev-user",
    email: "dev@example.com",
    username: "dev",
    display_name: "Mock Developer",
    language,
    locale: language === "es-419" ? "es-419" : "en-US",
    onboarding: {
      completed: true,
      stage: "completed",
      language_confirmed: true,
      primary_goal: "test_stock_idea",
    },
  };
}

function confirmationAction(type: string, label: string) {
  return {
    id: `${type}-${CONFIRMATION_ID}`,
    type,
    label,
    presentation: "confirmation",
    payload: {
      confirmation_id: CONFIRMATION_ID,
      conversation_id: CONVERSATION_ID,
      launch_payload_hash: "launch-hash-actions",
    },
  };
}

function confirmationCard() {
  return {
    confirmation_id: CONFIRMATION_ID,
    confirmation_state: "active",
    title: "AAPL buy and hold",
    summary: "Buy and hold AAPL with SPY as the comparison benchmark.",
    status: "ready_to_run",
    statusLabel: "Ready to run",
    strategy_type: "buy_and_hold",
    asset_class: "equity",
    date_range: {
      start: "2025-01-01",
      end: "2025-04-01",
      display: "January 1, 2025 to April 1, 2025",
    },
    rows: [
      { key: "strategy", label: "Strategy", value: "Buy and hold" },
      { key: "asset", label: "Asset", value: "AAPL" },
      {
        key: "period",
        label: "Period",
        value: "January 1, 2025 to April 1, 2025",
      },
      { key: "benchmark", label: "Benchmark", value: "SPY" },
    ],
    assumptions: [
      "$10,000 starting capital",
      "Long-only, daily close data",
      "No fees or slippage",
    ],
    actions: [
      confirmationAction("run_backtest", "Run backtest"),
      confirmationAction("change_dates", "Change dates"),
      confirmationAction("change_asset", "Change asset"),
      confirmationAction("adjust_assumptions", "Adjust assumptions"),
      confirmationAction("cancel_confirmation", "Cancel"),
    ],
  };
}

function resultAction(type: string, label: string) {
  return {
    id: `${type}-${RUN_ID}`,
    type,
    label,
    presentation: "result",
    payload: {
      run_id: RUN_ID,
      conversation_id: CONVERSATION_ID,
      strategy_name: "AAPL buy and hold",
      symbols: ["AAPL"],
      asset_class: "equity",
      template: "buy_and_hold",
    },
  };
}

function resultCard() {
  return {
    title: "AAPL buy and hold",
    symbols: ["AAPL"],
    strategy_label: "Buy and hold",
    asset_class: "equity",
    date_range: {
      start: "2025-01-01",
      end: "2025-04-01",
      display: "January 1, 2025 to April 1, 2025",
    },
    status_label: "Simulation Complete",
    rows: [
      { key: "ending_value", label: "Ending value", value: "$9,150" },
      { key: "total_return_pct", label: "Total return", value: "-8.5%" },
      { key: "benchmark_delta_pct", label: "Vs benchmark", value: "-4.4 pts" },
      { key: "max_drawdown_pct", label: "Max drawdown", value: "-12.0%" },
    ],
    benchmark_note: "AAPL lagged SPY by 4.4 percentage points.",
    assumptions: [
      "$10,000 starting capital",
      "Long-only, equal-weight run",
      "Benchmark: SPY",
    ],
    actions: [
      resultAction("show_breakdown", "Explain result"),
      resultAction("refine_strategy", "Refine idea"),
    ],
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
        ending_value: 9150,
        total_return_pct: -8.5,
        benchmark_delta_pct: -4.4,
        max_drawdown_pct: -12,
      },
      by_symbol: {},
    },
    config_snapshot: {
      template: "buy_and_hold",
      symbols: ["AAPL"],
      asset_class: "equity",
      benchmark_symbol: "SPY",
      initial_capital: 10000,
      date_range: {
        start: "2025-01-01",
        end: "2025-04-01",
      },
    },
    conversation_result_card: resultCard(),
    created_at: CREATED_AT,
  };
}

function sse(frames: Array<Record<string, unknown> | "[DONE]">) {
  return frames
    .map((frame) =>
      frame === "[DONE]" ? "data: [DONE]\n\n" : `data: ${JSON.stringify(frame)}\n\n`,
    )
    .join("");
}

async function fulfillSse(route: Route, frames: Array<Record<string, unknown> | "[DONE]">) {
  await route.fulfill({
    status: 200,
    contentType: "text/event-stream",
    body: sse(frames),
  });
}

function persistedUserMessage(
  id: string,
  content: string,
  metadata: Record<string, unknown> = {},
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

function persistedAssistantMessage(
  id: string,
  content: string,
  metadata: Record<string, unknown> = {},
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

async function mockChatApi(
  page: Page,
  options: MockChatApiOptions = {},
): Promise<MockChatApi> {
  const language = options.language ?? "en";
  const retryPrompt =
    language === "es-419" ? "Provocar reintento" : "Trigger retry case";
  const retryErrorMessage =
    language === "es-419"
      ? "Los datos de mercado tardaron demasiado"
      : "Market data timed out";
  const retrySuccessMessage =
    language === "es-419"
      ? "Recuperado despues de reintentar."
      : "Recovered after retry.";
  const streamRequests: StreamRequest[] = [];
  const feedbackRequests: Array<Record<string, unknown>> = [];
  const messages: ApiMessage[] = [];
  let retryAttempts = 0;

  const upsertConfirmationMessages = (prompt: string) => {
    messages.splice(
      0,
      messages.length,
      persistedUserMessage("msg-user-confirm", prompt),
      persistedAssistantMessage("msg-confirmation", "", {
        confirmation_card: confirmationCard(),
      }),
    );
  };

  const upsertResultMessages = (runAction: StreamRequest["action"]) => {
    messages.splice(
      0,
      messages.length,
      persistedUserMessage("msg-user-confirm", "Buy and hold AAPL with SPY in early 2025."),
      persistedAssistantMessage("msg-confirmation", "", {
        confirmation_card: {
          ...confirmationCard(),
          confirmation_state: "superseded",
          status: "run_complete",
          statusLabel: "Run complete",
          actions: [],
        },
      }),
      persistedUserMessage("msg-user-run", "Run backtest", {
        chat_action: runAction,
      }),
      persistedAssistantMessage(
        "msg-result",
        "Quick take: AAPL finished below the starting value and lagged SPY.",
        {
          result_card: resultCard(),
          result_run_id: RUN_ID,
          latest_run_id: RUN_ID,
          result_conversation_id: CONVERSATION_ID,
          result_fact_bank: {
            symbols: ["AAPL"],
            asset_class: "equity",
            benchmark_symbol: "SPY",
            config_snapshot: completedRun().config_snapshot,
          },
        },
      ),
    );
  };

  await page.route("**/api/v1/me", async (route) => {
    if (route.request().method() === "PATCH") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          user: mockUser(language),
        }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        user: mockUser(language),
      }),
    });
  });

  await page.route(`**/api/v1/conversations/${CONVERSATION_ID}/messages**`, async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: messages, next_cursor: null }),
    }),
  );

  await page.route("**/api/v1/conversations", async (route) => {
    if (route.request().method() === "POST") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ conversation: baseConversation(language) }),
      });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [baseConversation(language)], next_cursor: null }),
    });
  });

  await page.route("**/api/v1/history**", async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            type: "chat",
            id: CONVERSATION_ID,
            title: "AAPL readiness",
            subtitle: "Latest AAPL backtest",
            pinned: false,
            created_at: CREATED_AT,
            conversation_id: CONVERSATION_ID,
          },
        ],
        next_cursor: null,
      }),
    }),
  );

  await page.route("**/api/v1/search**", async (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: [], next_cursor: null }),
    }),
  );

  await page.route("**/api/v1/feedback", async (route) => {
    feedbackRequests.push(route.request().postDataJSON() as Record<string, unknown>);
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ success: true }),
    });
  });

  await page.route("**/api/v1/chat/stream", async (route) => {
    const body = route.request().postDataJSON() as StreamRequest;
    streamRequests.push(body);

    if (body.message === retryPrompt) {
      retryAttempts += 1;
      if (retryAttempts === 1) {
        messages.splice(
          0,
          messages.length,
          persistedUserMessage("msg-user-retry", retryPrompt),
          persistedAssistantMessage("msg-retry-error", retryErrorMessage, {
            retry_last_turn: { message: retryPrompt },
            recovery: {
              code: "runtime_failure",
              retryable: true,
              language,
            },
          }),
        );
        return fulfillSse(route, [
          {
            type: "error",
            code: "market_data_timeout",
            message: retryErrorMessage,
            message_id: "msg-retry-error",
            retry_last_turn: { message: retryPrompt },
            recovery: {
              code: "runtime_failure",
              retryable: true,
              language,
            },
          },
        ]);
      }
      messages.splice(
        0,
        messages.length,
        persistedUserMessage("msg-user-retry", retryPrompt),
        persistedAssistantMessage("msg-retry-success", retrySuccessMessage),
      );
      return fulfillSse(route, [
        {
          type: "final",
          payload: {
            stage_outcome: "ready_to_respond",
            assistant_response: retrySuccessMessage,
            message_id: "msg-retry-success",
          },
        },
        "[DONE]",
      ]);
    }

    if (body.action?.type === "run_backtest") {
      upsertResultMessages(body.action);
      return fulfillSse(route, [
        { type: "stage_start", stage: "execute" },
        {
          type: "token",
          content: "Quick take: AAPL finished below the starting value and lagged SPY.",
        },
        {
          type: "final",
          payload: {
            stage_outcome: "completed",
            assistant_response:
              "Quick take: AAPL finished below the starting value and lagged SPY.",
            run: completedRun(),
            message_id: "msg-result",
          },
        },
        "[DONE]",
      ]);
    }

    if (body.action?.type === "show_breakdown") {
      return fulfillSse(route, [
        {
          type: "final",
          payload: {
            stage_outcome: "ready_to_respond",
            assistant_response:
              "Breakdown: most of the shortfall came from the benchmark gap and drawdown.",
            message_id: "msg-breakdown",
          },
        },
        "[DONE]",
      ]);
    }

    if (body.action?.type === "refine_strategy") {
      return fulfillSse(route, [
        {
          type: "final",
          payload: {
            stage_outcome: "ready_to_respond",
            assistant_response: "Tell me what you want to refine next.",
            message_id: "msg-refine",
          },
        },
        "[DONE]",
      ]);
    }

    if (body.action?.type === "cancel_confirmation") {
      return fulfillSse(route, [
        {
          type: "final",
          payload: {
            stage_outcome: "ready_to_respond",
            confirmation_cancelled: { confirmation_id: CONFIRMATION_ID },
            assistant_response: "Canceled this draft.",
            message_id: "msg-cancel",
          },
        },
        "[DONE]",
      ]);
    }

    if (
      body.action?.type === "change_dates" ||
      body.action?.type === "change_asset" ||
      body.action?.type === "adjust_assumptions"
    ) {
      const actionPrompt =
        language === "es-419"
          ? "Claro, dime el cambio que quieres hacer."
          : `Sure, tell me the ${body.action.type.replace("_", " ")} update.`;
      return fulfillSse(route, [
        {
          type: "final",
          payload: {
            stage_outcome: "await_user_reply",
            assistant_response: actionPrompt,
            message_id: `msg-${body.action.type}`,
          },
        },
        "[DONE]",
      ]);
    }

    const prompt = body.message ?? "Buy and hold AAPL with SPY in early 2025.";
    upsertConfirmationMessages(prompt);
    return fulfillSse(route, [
      { type: "stage_start", stage: "confirm" },
      {
        type: "final",
        payload: {
          stage_outcome: "ready_for_confirmation",
          confirmation: confirmationCard(),
          message_id: "msg-confirmation",
        },
      },
      "[DONE]",
    ]);
  });

  return { streamRequests, feedbackRequests };
}

async function startConfirmation(
  page: Page,
  prompt: string,
  runLabel = "Run backtest",
) {
  await page.goto("/chat", { waitUntil: "networkidle" });
  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("chat-input").fill(prompt);
  await page.getByTestId("chat-send").click();
  await expect(page.getByRole("button", { name: runLabel })).toBeVisible();
}

test("confirmation actions stream structured action payloads from the browser", async ({ page }) => {
  const api = await mockChatApi(page);
  const actions = [
    ["Change dates", "change_dates"],
    ["Change asset", "change_asset"],
    ["Adjust assumptions", "adjust_assumptions"],
    ["Cancel", "cancel_confirmation"],
  ] as const;

  for (const [label, type] of actions) {
    await startConfirmation(page, `Buy and hold AAPL before ${label}`);
    await expect(page.getByRole("button", { name: "Run backtest" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Change dates" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Change asset" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Adjust assumptions" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Cancel" })).toBeVisible();

    const previousRequestCount = api.streamRequests.length;
    await page.getByRole("button", { name: label }).click();
    await expect
      .poll(() => api.streamRequests.length)
      .toBe(previousRequestCount + 1);
    expect(api.streamRequests.at(-1)?.action?.type).toBe(type);
    expect(api.streamRequests.at(-1)?.action?.payload?.confirmation_id).toBe(
      CONFIRMATION_ID,
    );
  }
});

test("run result actions hydrate after reload and submit feedback from more menu", async ({ page }) => {
  const api = await mockChatApi(page);
  await startConfirmation(page, "Buy and hold AAPL with SPY in early 2025.");

  await page.getByRole("button", { name: "Run backtest" }).click();
  await expect(page.getByText("Simulation Complete")).toBeVisible();
  await expect(page.getByText("Quick take: AAPL finished below")).toBeVisible();
  expect(api.streamRequests.at(-1)?.action?.type).toBe("run_backtest");

  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Simulation Complete")).toBeVisible();
  await expect(page.getByRole("button", { name: "Explain result" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Refine idea" })).toBeVisible();

  await page.getByLabel("More actions").nth(1).click();
  const reportIssue = page.getByRole("menuitem", { name: "Report issue" });
  await expect(reportIssue).toBeVisible();
  await reportIssue.click();
  await expect(page.getByText("Provide feedback")).toBeVisible();
  await page
    .getByPlaceholder("Brief description of the issue")
    .fill("Result action browser QA");
  await page
    .getByPlaceholder(/1\. Go to/)
    .fill("1. Run the mocked result flow\n2. Open more actions\n3. Submit issue");
  await page.getByLabel(/I consent to the Argus team processing/).check();
  await page.getByRole("button", { name: "Submit feedback" }).click();
  await expect(page.getByText("Feedback submitted.")).toBeVisible();
  await expect.poll(() => api.feedbackRequests.length).toBe(1);
  expect(api.feedbackRequests[0].type).toBe("bug");
  await page.keyboard.press("Escape");
  await expect(page.getByText("Provide feedback")).toHaveCount(0);

  await page.getByRole("button", { name: "Explain result" }).click();
  await expect(page.getByLabel("Result breakdown")).toContainText(
    "most of the shortfall",
  );
  expect(api.streamRequests.at(-1)?.action?.type).toBe("show_breakdown");

  await page.getByRole("button", { name: "Refine idea" }).click();
  await expect(page.getByText("Tell me what you want to refine next.")).toBeVisible();
  expect(api.streamRequests.at(-1)?.action?.type).toBe("refine_strategy");
});

test("retry action recovers a failed stream without duplicating user input", async ({ page }) => {
  const api = await mockChatApi(page);
  await page.goto("/chat", { waitUntil: "networkidle" });
  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });

  await page.getByTestId("chat-input").fill("Trigger retry case");
  await page.getByTestId("chat-send").click();

  await expect(page.getByText("Market data timed out")).toBeVisible();
  await page.getByRole("button", { name: "Retry" }).click();
  await expect(page.getByText("Recovered after retry.")).toBeVisible();

  expect(api.streamRequests.map((request) => request.message)).toEqual([
    "Trigger retry case",
    "Trigger retry case",
  ]);
});

test("Spanish action recovery localizes retry after reload and feedback controls", async ({
  page,
}) => {
  const api = await mockChatApi(page, { language: "es-419" });
  await startConfirmation(
    page,
    "Compra y conserva AAPL con SPY al inicio de 2025.",
    "Ejecutar backtest",
  );

  await expect(page.getByRole("button", { name: "Cambiar fechas" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Cambiar activo" })).toBeVisible();

  const previousRequestCount = api.streamRequests.length;
  await page.getByRole("button", { name: "Cambiar fechas" }).click();
  await expect.poll(() => api.streamRequests.length).toBe(previousRequestCount + 1);
  expect(api.streamRequests.at(-1)?.language).toBe("es-419");
  expect(api.streamRequests.at(-1)?.action?.type).toBe("change_dates");
  await expect(page.getByText("Claro, dime el cambio que quieres hacer.")).toBeVisible();

  await page.getByTestId("chat-input").fill("Provocar reintento");
  await page.getByTestId("chat-send").click();
  await expect(page.getByText("Los datos de mercado tardaron demasiado")).toBeVisible();
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page.getByText("Recuperado despues de reintentar.")).toBeVisible();

  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Recuperado despues de reintentar.")).toBeVisible();
  await expect(page.getByRole("button", { name: "Reintentar" })).toHaveCount(0);

  await page.getByLabel(/acciones/i).last().click();
  const reportIssue = page.getByRole("menuitem", { name: "Reportar problema" });
  await expect(reportIssue).toBeVisible();
  await reportIssue.click();
  await expect(
    page.getByRole("heading", { name: "Enviar comentarios" }),
  ).toBeVisible();
  await page.getByPlaceholder(/problema/i).fill("QA de recuperacion en espanol");
  await page
    .getByPlaceholder(/1\. Ve a/)
    .fill("1. Provocar un reintento\n2. Reintentar\n3. Recargar el chat");
  await page.getByLabel(/Autorizo al equipo/).check();
  await page.getByRole("button", { name: "Enviar comentarios" }).click();
  await expect(page.getByText("Comentarios enviados.")).toBeVisible();
  await expect.poll(() => api.feedbackRequests.length).toBe(1);
  expect(api.feedbackRequests[0].type).toBe("bug");
});
