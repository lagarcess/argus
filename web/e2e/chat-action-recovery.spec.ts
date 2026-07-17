import { expect, test, type Page, type Route } from "@playwright/test";

const CONVERSATION_ID = "conv-actions";
const RUN_ID = "run-actions";
const CONFIRMATION_ID = "confirm-actions";
const CREATED_AT = "2026-06-16T12:00:00Z";
const COVERAGE_RECOVERY_REQUEST = "Test AAPL coverage recovery";
const COVERAGE_RECOVERY_PROMPT =
  "AAPL and SPY do not share enough history for one trustworthy test. Which part should we change?";
const TIMEFRAME_RECOVERY_REQUEST = "Test AAPL with five-minute bars";
const DEGRADED_TIMEFRAME_RECOVERY_REQUEST =
  "Test AAPL with five-minute bars while clarification is unavailable";
const TIMEFRAME_RECOVERY_PROMPTS = {
  en: "Five-minute bars are not supported. Choose daily or one-hour bars.",
  "es-419":
    "Las barras de cinco minutos no son compatibles. Elige barras diarias o de una hora.",
} as const;
const DEGRADED_TIMEFRAME_RECOVERY_PROMPTS = {
  en: "5m is not a supported bar size. Choose daily or 1-hour bars.",
  "es-419":
    "5m no es un tamaño de barra compatible. Elige barras diarias o de 1 hora.",
} as const;

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

type MockDateRange = {
  start: string;
  end: string;
  display: string;
};

type PendingConfirmationEdit = "date" | "asset" | "assumption" | null;

const DEFAULT_DATE_RANGE: MockDateRange = {
  start: "2025-01-01",
  end: "2025-04-01",
  display: "January 1, 2025 to April 1, 2025",
};

const UPDATED_DATE_RANGE: MockDateRange = {
  start: "2025-02-01",
  end: "2025-05-01",
  display: "February 1, 2025 to May 1, 2025",
};

function formatCurrency(amount: number) {
  return `$${amount.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}

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

function confirmationCard(
  dateRange: MockDateRange = DEFAULT_DATE_RANGE,
  assetSymbol = "AAPL",
  initialCapital = 10000,
) {
  const formattedCapital = formatCurrency(initialCapital);

  return {
    confirmation_id: CONFIRMATION_ID,
    confirmation_state: "active",
    title: `${assetSymbol} buy and hold`,
    summary: `Buy and hold ${assetSymbol} with SPY as the comparison benchmark.`,
    status: "ready_to_run",
    statusLabel: "Ready to run",
    strategy_type: "buy_and_hold",
    asset_class: "equity",
    date_range: dateRange,
    rows: [
      { key: "strategy", label: "Strategy", value: "Buy and hold" },
      { key: "assets", label: "Assets", value: assetSymbol },
      { key: "starting_capital", label: "Starting capital", value: formattedCapital },
      {
        key: "period",
        label: "Period",
        value: dateRange.display,
      },
      { key: "benchmark", label: "Benchmark", value: "SPY" },
    ],
    assumptions: [
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

function resultAction(type: string, label: string, assetSymbol = "AAPL") {
  return {
    id: `${type}-${RUN_ID}`,
    type,
    label,
    presentation: "result",
    payload: {
      run_id: RUN_ID,
      conversation_id: CONVERSATION_ID,
      strategy_name: `${assetSymbol} buy and hold`,
      symbols: [assetSymbol],
      asset_class: "equity",
      template: "buy_and_hold",
    },
  };
}

function resultCard(
  dateRange: MockDateRange = DEFAULT_DATE_RANGE,
  assetSymbol = "AAPL",
  initialCapital = 10000,
) {
  return {
    title: `${assetSymbol} buy and hold`,
    symbols: [assetSymbol],
    strategy_label: "Buy and hold",
    asset_class: "equity",
    date_range: dateRange,
    status_label: "Simulation Complete",
    rows: [
      { key: "ending_value", label: "Ending value", value: "$9,150" },
      { key: "total_return_pct", label: "Total return", value: "-8.5%" },
      { key: "benchmark_delta_pct", label: "Vs benchmark", value: "-4.4 pts" },
      { key: "max_drawdown_pct", label: "Max drawdown", value: "-12.0%" },
    ],
    benchmark_note: `${assetSymbol} lagged SPY by 4.4 percentage points.`,
    assumptions: [
      `${formatCurrency(initialCapital)} starting capital`,
      "Long-only, equal-weight run",
      "Benchmark: SPY",
    ],
    actions: [
      resultAction("show_breakdown", "Explain result", assetSymbol),
      resultAction("refine_strategy", "Refine idea", assetSymbol),
    ],
    chart: null,
  };
}

function completedRun(
  dateRange: MockDateRange = DEFAULT_DATE_RANGE,
  assetSymbol = "AAPL",
  initialCapital = 10000,
) {
  return {
    id: RUN_ID,
    conversation_id: CONVERSATION_ID,
    strategy_id: null,
    status: "completed",
    asset_class: "equity",
    symbols: [assetSymbol],
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
      symbols: [assetSymbol],
      asset_class: "equity",
      benchmark_symbol: "SPY",
      initial_capital: initialCapital,
      date_range: {
        start: dateRange.start,
        end: dateRange.end,
      },
    },
    conversation_result_card: resultCard(dateRange, assetSymbol, initialCapital),
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
  await page.addInitScript((detectedLanguage) => {
    window.localStorage.setItem("i18nextLng", detectedLanguage);
  }, language);
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
  const resultSummary =
    language === "es-419"
      ? "Resumen rápido: AAPL terminó por debajo del valor inicial y quedó detrás de SPY."
      : "Quick take: AAPL finished below the starting value and lagged SPY.";
  const resultBreakdown =
    language === "es-419"
      ? "Desglose: la mayor parte de la diferencia vino de la brecha contra SPY y la caída máxima."
      : "Breakdown: most of the shortfall came from the benchmark gap and drawdown.";
  const refinePrompt =
    language === "es-419"
      ? "Dime qué quieres ajustar a continuación."
      : "Tell me what you want to refine next.";
  const streamRequests: StreamRequest[] = [];
  const feedbackRequests: Array<Record<string, unknown>> = [];
  const messages: ApiMessage[] = [];
  let retryAttempts = 0;
  let activeDateRange = DEFAULT_DATE_RANGE;
  let activeAssetSymbol = "AAPL";
  let activeInitialCapital = 10000;
  let pendingConfirmationEdit: PendingConfirmationEdit = null;
  let confirmationRevision = 0;

  const nextConfirmationMessageId = (reason: string) => {
    confirmationRevision += 1;
    return `msg-confirmation-${reason}-${confirmationRevision}`;
  };

  const upsertConfirmationMessages = (
    prompt: string,
    messageId = nextConfirmationMessageId("draft"),
  ) => {
    messages.splice(
      0,
      messages.length,
      persistedUserMessage("msg-user-confirm", prompt),
      persistedAssistantMessage(messageId, "", {
        confirmation_card: confirmationCard(
          activeDateRange,
          activeAssetSymbol,
          activeInitialCapital,
        ),
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
          ...confirmationCard(
            activeDateRange,
            activeAssetSymbol,
            activeInitialCapital,
          ),
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
        resultSummary,
        {
          result_card: resultCard(
            activeDateRange,
            activeAssetSymbol,
            activeInitialCapital,
          ),
          result_run_id: RUN_ID,
          latest_run_id: RUN_ID,
          result_conversation_id: CONVERSATION_ID,
          result_fact_bank: {
            symbols: [activeAssetSymbol],
            asset_class: "equity",
            benchmark_symbol: "SPY",
            config_snapshot: completedRun(
              activeDateRange,
              activeAssetSymbol,
              activeInitialCapital,
            ).config_snapshot,
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

    if (body.message === COVERAGE_RECOVERY_REQUEST) {
      const clarification = {
        kind: "coverage_recovery",
        reason_code: "no_common_data_window",
        prompt_source: "llm_generated",
        requested_field: null,
        requested_fields: [
          "date_range",
          "asset_universe",
          "comparison_baseline",
        ],
        semantic_needs: ["simplification_choice"],
        payload: {
          strategy: {
            strategy_type: "buy_and_hold",
            asset_universe: ["AAPL"],
            asset_class: "equity",
          },
          coverage: {
            code: "no_common_data_window",
            benchmark_symbol: "SPY",
          },
        },
        options: [
          {
            id: "change_dates",
            replacement_values: { requested_field: "date_range" },
          },
          {
            id: "change_asset",
            replacement_values: { requested_field: "asset_universe" },
          },
          {
            id: "change_benchmark",
            replacement_values: { requested_field: "comparison_baseline" },
          },
        ],
      };
      messages.splice(
        0,
        messages.length,
        persistedUserMessage("msg-user-coverage-recovery", body.message),
        persistedAssistantMessage(
          "msg-coverage-recovery",
          COVERAGE_RECOVERY_PROMPT,
          { clarification },
        ),
      );
      return fulfillSse(route, [
        { type: "stage_start", stage: "clarify" },
        {
          type: "token",
          content: COVERAGE_RECOVERY_PROMPT,
        },
        {
          type: "final",
          payload: {
            stage_outcome: "await_user_reply",
            assistant_prompt: COVERAGE_RECOVERY_PROMPT,
            clarification,
            message_id: "msg-coverage-recovery",
          },
        },
        "[DONE]",
      ]);
    }

    if (
      body.message === TIMEFRAME_RECOVERY_REQUEST ||
      body.message === DEGRADED_TIMEFRAME_RECOVERY_REQUEST
    ) {
      const degraded = body.message === DEGRADED_TIMEFRAME_RECOVERY_REQUEST;
      const prompt = degraded
        ? DEGRADED_TIMEFRAME_RECOVERY_PROMPTS[language]
        : TIMEFRAME_RECOVERY_PROMPTS[language];
      const responseIntent = {
        kind: "unsupported_recovery",
        semantic_needs: ["simplification_choice"],
        requested_fields: ["timeframe"],
        facts: {
          unsupported_constraints: [
            {
              category: "unsupported_time_granularity",
              raw_value: "5m",
            },
          ],
        },
        options: [
          {
            id: "option_0",
            replacement_values: { timeframe: "1D" },
          },
          {
            id: "option_1",
            replacement_values: { timeframe: "1h" },
          },
        ],
      };
      const clarification = {
        kind: "unsupported_recovery",
        reason_code: "unsupported_time_granularity",
        prompt_source: degraded ? "degraded_fallback" : "llm_generated",
        requested_field: "timeframe",
        requested_fields: ["timeframe"],
        semantic_needs: ["simplification_choice"],
        payload: {
          strategy: {
            strategy_type: "buy_and_hold",
            asset_universe: ["AAPL"],
            asset_class: "equity",
          },
          raw_value: "5m",
        },
        options: [
          {
            id: "option_0",
            compatibility_label: "Retry with daily bars",
            replacement_values: { timeframe: "1D" },
          },
          {
            id: "option_1",
            compatibility_label: "Retry with 1-hour bars",
            replacement_values: { timeframe: "1h" },
          },
        ],
      };
      messages.splice(
        0,
        messages.length,
        persistedUserMessage("msg-user-timeframe-recovery", body.message),
        persistedAssistantMessage("msg-timeframe-recovery", prompt, {
          response_intent: responseIntent,
          clarification,
        }),
      );
      return fulfillSse(route, [
        { type: "stage_start", stage: "clarify" },
        { type: "token", content: prompt },
        {
          type: "final",
          payload: {
            stage_outcome: "await_user_reply",
            assistant_prompt: prompt,
            response_intent: responseIntent,
            clarification,
            message_id: "msg-timeframe-recovery",
          },
        },
        "[DONE]",
      ]);
    }

    if (body.message === "Prueba comprar y mantener AAPL") {
      const compatibilityPrompt = "What date window should I use for AAPL?";
      const clarification = {
        kind: "clarification",
        reason_code: "missing_period",
        prompt_source: "degraded_fallback",
        requested_field: "date_range",
        requested_fields: ["date_range"],
        semantic_needs: ["period"],
        payload: {
          strategy: {
            strategy_type: "buy_and_hold",
            asset_universe: ["AAPL"],
            asset_class: "equity",
          },
        },
        options: [],
      };
      messages.splice(
        0,
        messages.length,
        persistedUserMessage("msg-user-degraded-clarification", body.message),
        persistedAssistantMessage("msg-degraded-clarification", compatibilityPrompt, {
          clarification,
          pending_strategy: {
            strategy: {
              strategy_type: "buy_and_hold",
              asset_universe: ["AAPL"],
              asset_class: "equity",
            },
            requested_field: "date_range",
            missing_required_fields: ["date_range"],
            clarification,
          },
        }),
      );
      return fulfillSse(route, [
        { type: "stage_start", stage: "clarify" },
        {
          type: "final",
          payload: {
            stage_outcome: "await_user_reply",
            assistant_prompt: compatibilityPrompt,
            requested_field: "date_range",
            clarification,
            pending_strategy: {
              strategy: {
                strategy_type: "buy_and_hold",
                asset_universe: ["AAPL"],
                asset_class: "equity",
              },
              requested_field: "date_range",
              missing_required_fields: ["date_range"],
              clarification,
            },
            message_id: "msg-degraded-clarification",
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
          content: resultSummary,
        },
        {
          type: "final",
          payload: {
            stage_outcome: "completed",
            assistant_response: resultSummary,
            run: completedRun(
              activeDateRange,
              activeAssetSymbol,
              activeInitialCapital,
            ),
            message_id: "msg-result",
          },
        },
        "[DONE]",
      ]);
    }

    if (
      body.action?.type === "select_response_option" &&
      body.action.payload?.option_id === "option_0" &&
      JSON.stringify(body.action.payload?.replacement_values) ===
        JSON.stringify({ timeframe: "1D" })
    ) {
      const correctedCard = {
        ...confirmationCard(DEFAULT_DATE_RANGE, "AAPL", 10000),
        assumptions: [
          "$10,000 starting capital",
          "Daily bars",
          "0.10% fees",
          "0.05% slippage",
        ],
      };
      messages.push(
        persistedUserMessage("msg-user-timeframe-daily", body.message ?? "", {
          chat_action: body.action,
        }),
        persistedAssistantMessage("msg-timeframe-confirmation", "", {
          confirmation_card: correctedCard,
        }),
      );
      return fulfillSse(route, [
        { type: "stage_start", stage: "confirm" },
        {
          type: "final",
          payload: {
            stage_outcome: "ready_for_confirmation",
            confirmation: correctedCard,
            message_id: "msg-timeframe-confirmation",
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
            assistant_response: resultBreakdown,
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
            assistant_response: refinePrompt,
            message_id: "msg-refine",
          },
        },
        "[DONE]",
      ]);
    }

    if (body.action?.type === "cancel_confirmation") {
      const cancelMessage =
        language === "es-419" ? "Cancelé este borrador." : "Canceled this draft.";
      return fulfillSse(route, [
        {
          type: "final",
          payload: {
            stage_outcome: "ready_to_respond",
            confirmation_cancelled: { confirmation_id: CONFIRMATION_ID },
            assistant_response: cancelMessage,
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
      if (body.action?.type === "change_dates") {
        pendingConfirmationEdit = "date";
      } else if (body.action?.type === "change_asset") {
        pendingConfirmationEdit = "asset";
      } else if (body.action?.type === "adjust_assumptions") {
        pendingConfirmationEdit = "assumption";
      }
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
    const editReason = pendingConfirmationEdit ?? "draft";
    const confirmationMessageId = nextConfirmationMessageId(editReason);
    if (pendingConfirmationEdit === "date") {
      activeDateRange = UPDATED_DATE_RANGE;
    } else if (pendingConfirmationEdit === "asset") {
      activeAssetSymbol = "GOOGL";
    } else if (pendingConfirmationEdit === "assumption") {
      activeInitialCapital = 250000;
    }
    pendingConfirmationEdit = null;
    upsertConfirmationMessages(prompt, confirmationMessageId);
    return fulfillSse(route, [
      { type: "stage_start", stage: "confirm" },
      {
        type: "final",
        payload: {
          stage_outcome: "ready_for_confirmation",
          confirmation: confirmationCard(
            activeDateRange,
            activeAssetSymbol,
            activeInitialCapital,
          ),
          message_id: confirmationMessageId,
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

test("private-alpha readiness smoke covers starter, Spanish edit, result, reload, retry, and feedback", async ({
  page,
}) => {
  const api = await mockChatApi(page, { language: "es-419" });
  await page.goto("/chat", { waitUntil: "networkidle" });
  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });

  await expect(page.getByRole("button", { name: "Prueba Apple vs SPY" })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Prueba mantener Bitcoin (BTC)" }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Prueba compras semanales de Nvidia" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Prueba Apple vs SPY" }).click();
  await expect(page.getByRole("button", { name: "Ejecutar backtest" })).toBeVisible();
  expect(api.streamRequests.at(-1)?.message).toBe(
    "Compra y mantén AAPL durante los últimos 12 meses con SPY como referencia.",
  );
  expect(api.streamRequests.at(-1)?.message).not.toContain("2024");

  await page.getByRole("button", { name: "Cambiar fechas" }).click();
  await expect(page.getByText("Claro, dime el cambio que quieres hacer.")).toBeVisible();
  await page
    .getByTestId("chat-input")
    .fill("Usa del 1 de febrero de 2025 al 1 de mayo de 2025");
  await page.getByTestId("chat-send").click();
  await expect(
    page.getByText("1 feb 2025 → 1 may 2025").first(),
  ).toBeVisible();

  await page.getByRole("button", { name: "Ejecutar backtest" }).click();
  await expect(page.getByText("Simulación completa")).toBeVisible();
  await expect(page.getByText("Resumen rápido: AAPL terminó")).toBeVisible();
  await expect(
    page.getByText("1 feb 2025 → 1 may 2025").first(),
  ).toBeVisible();

  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByText("Simulación completa")).toBeVisible();
  await expect(page.getByText("Resumen rápido: AAPL terminó")).toBeVisible();
  await expect(page.getByRole("button", { name: "Explicar resultado" })).toBeVisible();

  await page.getByRole("button", { name: "Más acciones" }).nth(1).click();
  const reportIssue = page.getByRole("menuitem", { name: "Reportar problema" });
  await expect(reportIssue).toBeVisible();
  await reportIssue.click();
  await expect(
    page.getByRole("heading", { name: "Enviar comentarios" }),
  ).toBeVisible();
  await page
    .getByPlaceholder(/problema/i)
    .fill("QA readiness smoke de resultado y recarga");
  await page
    .getByPlaceholder(/1\. Ve a/)
    .fill("1. Ejecuta el smoke\n2. Recarga el resultado\n3. Envia comentarios");
  await page.getByLabel(/Autorizo al equipo/).check();
  await page.getByRole("button", { name: "Enviar comentarios" }).click();
  await expect(page.getByText("Comentarios enviados.")).toBeVisible();
  await expect.poll(() => api.feedbackRequests.length).toBe(1);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("heading", { name: "Enviar comentarios" })).toHaveCount(
    0,
  );

  await page.getByRole("button", { name: "Explicar resultado" }).click();
  await expect(page.getByLabel("Desglose del resultado")).toContainText(
    "mayor parte de la diferencia",
  );

  await page.getByTestId("chat-input").fill("Provocar reintento");
  await page.getByTestId("chat-send").click();
  await expect(
    page.getByText("Algo salió mal. Tu conversación está guardada. Intenta de nuevo."),
  ).toBeVisible();
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page.getByText("Recuperado despues de reintentar.")).toBeVisible();
});

test("Spanish confirmation edit actions preserve context through asset, assumptions, and cancel", async ({
  page,
}) => {
  const api = await mockChatApi(page, { language: "es-419" });
  await startConfirmation(
    page,
    "Compra y conserva AAPL con SPY al inicio de 2025.",
    "Ejecutar backtest",
  );

  await page.getByRole("button", { name: "Cambiar activo" }).click();
  await expect(page.getByText("Claro, dime el cambio que quieres hacer.")).toHaveCount(1);
  expect(api.streamRequests.at(-1)?.language).toBe("es-419");
  expect(api.streamRequests.at(-1)?.action?.type).toBe("change_asset");

  await page.getByTestId("chat-input").fill("ponlo con google mejor");
  await page.getByTestId("chat-send").click();
  await expect(page.getByText("GOOGL").first()).toBeVisible();
  await expect(page.getByText("1 ene 2025 → 1 abr 2025").first()).toBeVisible();
  expect(api.streamRequests.at(-1)?.message).toBe("ponlo con google mejor");
  expect(api.streamRequests.at(-1)?.action).toBeUndefined();

  await page.getByRole("button", { name: "Ajustar supuestos" }).click();
  await expect(page.getByText("Claro, dime el cambio que quieres hacer.")).toHaveCount(2);
  expect(api.streamRequests.at(-1)?.action?.type).toBe("adjust_assumptions");

  await page.getByTestId("chat-input").fill("ponle como doscientos cincuenta mil");
  await page.getByTestId("chat-send").click();
  await expect(page.getByText("$250,000").first()).toBeVisible();
  await expect(page.getByText("GOOGL").first()).toBeVisible();
  await expect(page.getByText("1 ene 2025 → 1 abr 2025").first()).toBeVisible();
  expect(api.streamRequests.at(-1)?.message).toBe(
    "ponle como doscientos cincuenta mil",
  );
  expect(api.streamRequests.at(-1)?.action).toBeUndefined();

  await page.getByRole("button", { name: "Cancelar" }).click();
  await expect(page.getByText("Borrador cancelado")).toBeVisible();
  await expect(page.getByRole("button", { name: "Ejecutar backtest" })).toHaveCount(0);
  expect(api.streamRequests.at(-1)?.action?.type).toBe("cancel_confirmation");
});

test("Spanish degraded clarification renders from typed sidecar", async ({ page }) => {
  const api = await mockChatApi(page, { language: "es-419" });

  await page.goto("/chat", { waitUntil: "networkidle" });
  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });
  await expect(
    page.getByTestId("chat-input"),
  ).toHaveAttribute("aria-label", "Describe una idea de inversión...");
  await page.getByTestId("chat-input").fill("Prueba comprar y mantener AAPL");
  await page.getByTestId("chat-send").click();

  await expect(
    page.getByText("¿Qué periodo quieres usar para AAPL?"),
  ).toBeVisible();
  await expect(
    page.getByText("What date window should I use for AAPL?"),
  ).toHaveCount(0);
  expect(api.streamRequests.at(-1)?.language).toBe("es-419");

  await page.reload({ waitUntil: "networkidle" });
  await expect(
    page.getByText("¿Qué periodo quieres usar para AAPL?"),
  ).toBeVisible();
  await expect(
    page.getByText("What date window should I use for AAPL?"),
  ).toHaveCount(0);
});

test("successful LLM coverage recovery preserves exact voice and actions after reload", async ({
  page,
}) => {
  await mockChatApi(page);

  await page.goto("/chat", { waitUntil: "networkidle" });
  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });
  await page.getByTestId("chat-input").fill(COVERAGE_RECOVERY_REQUEST);
  await page.getByTestId("chat-send").click();

  const expectCoverageRecovery = async () => {
    await expect(page.getByText(COVERAGE_RECOVERY_PROMPT, { exact: true })).toBeVisible();
    await expect(
      page.getByText(
        "Those assets and the benchmark do not share a usable data window for one trustworthy test. Change the dates, an asset, or the benchmark.",
        { exact: true },
      ),
    ).toHaveCount(0);
    for (const label of ["Change dates", "Change asset", "Change benchmark"]) {
      await expect(
        page.getByRole("button", { name: label, exact: true }).first(),
      ).toBeVisible();
    }
  };

  await expectCoverageRecovery();
  await page.reload({ waitUntil: "networkidle" });
  await expectCoverageRecovery();
});

for (const testCase of [
  {
    language: "en" as const,
    source: "LLM",
    request: TIMEFRAME_RECOVERY_REQUEST,
    prompt: TIMEFRAME_RECOVERY_PROMPTS.en,
    dailyLabel: "Retry with daily bars",
  },
  {
    language: "es-419" as const,
    source: "LLM",
    request: TIMEFRAME_RECOVERY_REQUEST,
    prompt: TIMEFRAME_RECOVERY_PROMPTS["es-419"],
    dailyLabel: "Usar barras diarias",
  },
  {
    language: "en" as const,
    source: "degraded",
    request: DEGRADED_TIMEFRAME_RECOVERY_REQUEST,
    prompt: DEGRADED_TIMEFRAME_RECOVERY_PROMPTS.en,
    dailyLabel: "Retry with daily bars",
  },
  {
    language: "es-419" as const,
    source: "degraded",
    request: DEGRADED_TIMEFRAME_RECOVERY_REQUEST,
    prompt: DEGRADED_TIMEFRAME_RECOVERY_PROMPTS["es-419"],
    dailyLabel: "Usar barras diarias",
  },
]) {
  test(`${testCase.source} timeframe recovery preserves assumptions and actions after reload (${testCase.language})`, async ({
    page,
  }) => {
    const api = await mockChatApi(page, { language: testCase.language });

    await page.goto("/chat", { waitUntil: "networkidle" });
    await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });
    await page.getByTestId("chat-input").fill(testCase.request);
    await page.getByTestId("chat-send").click();

    const expectTimeframeRecovery = async () => {
      await expect(page.getByText(testCase.prompt, { exact: true })).toBeVisible();
      await expect(
        page.getByRole("button", { name: testCase.dailyLabel, exact: true }).first(),
      ).toBeVisible();
    };

    await expectTimeframeRecovery();
    await page.reload({ waitUntil: "networkidle" });
    await expectTimeframeRecovery();

    await page
      .getByRole("button", { name: testCase.dailyLabel, exact: true })
      .first()
      .click();
    await expect(page.getByRole("button", { name: /backtest/i }).first()).toBeVisible();
    await expect(page.getByText("$10,000", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Daily bars", { exact: true })).toBeVisible();
    await expect(page.getByText("0.10% fees", { exact: true })).toBeVisible();
    await expect(page.getByText("0.05% slippage", { exact: true })).toBeVisible();

    const selection = api.streamRequests.at(-1)?.action;
    expect(selection?.type).toBe("select_response_option");
    expect(selection?.labelKey).toBe("chat.clarification.timeframe_actions.daily");
    expect(selection?.payload).toEqual({
      option_id: "option_0",
      replacement_values: { timeframe: "1D" },
    });

    await page.reload({ waitUntil: "networkidle" });
    await expect(page.getByText(testCase.prompt, { exact: true })).toBeVisible();
    await expect(page.getByText("$10,000", { exact: true }).first()).toBeVisible();
    await expect(page.getByText("Daily bars", { exact: true })).toBeVisible();
    await expect(page.getByText("0.10% fees", { exact: true })).toBeVisible();
    await expect(page.getByText("0.05% slippage", { exact: true })).toBeVisible();
  });
}

test("retry action recovers a failed stream without duplicating user input", async ({ page }) => {
  const api = await mockChatApi(page);
  await page.goto("/chat", { waitUntil: "networkidle" });
  await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });

  await page.getByTestId("chat-input").fill("Trigger retry case");
  await page.getByTestId("chat-send").click();

  await expect(
    page.getByText("Something went wrong. Your conversation is saved. Please try again."),
  ).toBeVisible();
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
  await expect(
    page.getByText("Algo salió mal. Tu conversación está guardada. Intenta de nuevo."),
  ).toBeVisible();
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
