import { describe, expect, test } from "bun:test";

import {
  hydrateTextMessageFromApi,
  loadAllConversationMessagePages,
  resolveOrdinaryTransportAmbiguity,
  resolveOrdinaryTransportAmbiguityView,
  retryRequestMessageForAssistant,
} from "../lib/chat-message-hydration";
import type { ApiMessage } from "../lib/argus-api";
import { latestInputActions } from "../components/chat/ChatInterface";
import type { Message } from "../components/chat/types";

function apiMessage(overrides: Partial<ApiMessage>): ApiMessage {
  return {
    id: "assistant-failed-1",
    conversation_id: "conversation-1",
    role: "assistant",
    content: "Something went wrong. Your conversation is saved. Please try again.",
    created_at: "2026-06-01T00:00:00Z",
    metadata: {},
    ...overrides,
  };
}

function applyViewMessages(
  messages: Message[] | ((current: Message[]) => Message[]),
  current: Message[],
): Message[] {
  return typeof messages === "function" ? messages(current) : messages;
}

describe("chat message hydration", () => {
  test("reload hydrates no-progress choices on their owning assistant", () => {
    const hydrated = hydrateTextMessageFromApi(
      apiMessage({
        id: "assistant-no-progress",
        content:
          "I could not resolve that choice without changing your current idea. Choose one of the options below.",
        metadata: {
          pending_strategy: {
            response_intent: {
              kind: "clarification",
              facts: { progress_outcome: "no_progress" },
              requested_fields: ["date_range"],
              options: [
                {
                  id: "supply_missing_value",
                  label: "Provide the missing value",
                  replacement_values: { requested_field: "date_range" },
                },
                {
                  id: "keep_unchanged",
                  label: "Keep the idea unchanged",
                  replacement_values: {
                    no_progress_action: "keep_unchanged",
                  },
                },
                {
                  id: "cancel",
                  label: "Cancel this flow",
                  replacement_values: { no_progress_action: "cancel" },
                },
              ],
            },
          },
        },
      }),
    );

    expect(hydrated.actions?.map((action) => action.id)).toEqual([
      "no-progress-supply-missing-value",
      "no-progress-keep-unchanged",
      "no-progress-cancel",
    ]);
    expect(latestInputActions([hydrated])).toEqual([]);
  });

  test("hydrates abandoned recovery on its owning persisted user message", () => {
    const hydrated = hydrateTextMessageFromApi(
      apiMessage({
        id: "request-message-1",
        role: "user",
        content: "Test AAPL",
        metadata: {
          agent_runtime_turn: {
            turn_id: "request-message-1",
            request_id: "request-1",
            status: "abandoned",
            terminal: true,
            failure_code: "turn_abandoned",
            retryable: true,
          },
          recovery: {
            code: "turn_abandoned",
            retryable: true,
          },
          retry_last_turn: {
            request_message_id: "request-message-1",
            message: "tampered browser text",
          },
        },
      }),
    );

    expect(hydrated.role).toBe("user");
    expect(hydrated.actions).toEqual([
      {
        id: "retry-last-turn-request-message-1",
        label: "Retry",
        labelKey: "common.retry",
        value: "Retry",
        type: "retry_last_turn",
        payload: {
          request_message_id: "request-message-1",
          message: "Test AAPL",
        },
      },
    ]);
    expect(hydrated.recoveryDisplay).toEqual({
      kind: "recovery_code",
      code: "turn_abandoned",
      values: undefined,
    });
  });

  test.each(["completed", "recoverable_failed", "abandoned", "reconciled"])(
    "hydrates durable terminal truth after ambiguous transport: %s",
    async (status) => {
      const request = apiMessage({
        id: "request-1",
        role: "user",
        content: "Test AAPL",
      });
      const durable = apiMessage({
        metadata: {
          agent_runtime_turn: {
            turn_id: request.id,
            request_id: "request-a",
            status,
            terminal: true,
          },
        },
      });

      const resolution = await resolveOrdinaryTransportAmbiguity(
        async () => [request, durable],
        new Set(),
        "request-a",
      );

      expect(resolution).toEqual({
        kind: "terminal",
        items: [request, durable],
      });
    },
  );

  test.each(["accepted", "running"])(
    "keeps ambiguous transport presentation-only while backend is %s",
    async (status) => {
      const durable = apiMessage({
        id: "request-1",
        role: "user",
        metadata: {
          agent_runtime_turn: {
            turn_id: "request-1",
            request_id: "request-a",
            status,
            terminal: false,
          },
        },
      });

      const resolution = await resolveOrdinaryTransportAmbiguity(
        async () => [durable],
        new Set(),
        "request-a",
      );

      expect(resolution).toEqual({ kind: "checking", items: [durable] });
    },
  );

  test("performs one bounded follow-up read when accepted becomes abandoned", async () => {
    const running = apiMessage({
      id: "request-1",
      role: "user",
      metadata: {
        agent_runtime_turn: {
          turn_id: "request-1",
          request_id: "request-a",
          status: "running",
          terminal: false,
        },
      },
    });
    const abandoned = apiMessage({
      ...running,
      metadata: {
        agent_runtime_turn: {
          turn_id: "request-1",
          request_id: "request-a",
          status: "abandoned",
          terminal: true,
        },
      },
    });
    const snapshots = [[running], [abandoned]];
    let loads = 0;
    const delays: number[] = [];

    const resolution = await resolveOrdinaryTransportAmbiguity(
      async () => snapshots[loads++] ?? snapshots.at(-1)!,
      new Set(),
      "request-a",
      {
        followUpDelayMs: 0,
        wait: async (delayMs) => {
          delays.push(delayMs);
        },
      },
    );

    expect(resolution).toEqual({ kind: "terminal", items: [abandoned] });
    expect(loads).toBe(2);
    expect(delays).toEqual([0]);
  });

  test("stops after one follow-up read when the turn remains running", async () => {
    const running = apiMessage({
      id: "request-1",
      role: "user",
      metadata: {
        agent_runtime_turn: {
          turn_id: "request-1",
          request_id: "request-a",
          status: "running",
          terminal: false,
        },
      },
    });
    let loads = 0;

    const resolution = await resolveOrdinaryTransportAmbiguity(
      async () => {
        loads += 1;
        return [running];
      },
      new Set(),
      "request-a",
      { followUpDelayMs: 0, wait: async () => undefined },
    );

    expect(resolution).toEqual({ kind: "checking", items: [running] });
    expect(loads).toBe(2);
  });

  test("distinguishes owner-scoped GET failure from unknown durable state", async () => {
    const failed = await resolveOrdinaryTransportAmbiguity(async () => {
      throw new Error("owner-scoped load failed");
    }, new Set(), "request-a");
    const unknown = await resolveOrdinaryTransportAmbiguity(
      async () => [apiMessage({ metadata: {} })],
      new Set(),
      "request-a",
    );

    expect(failed).toEqual({ kind: "load_failed", items: [] });
    expect(unknown).toEqual({
      kind: "unknown",
      items: [apiMessage({ metadata: {} })],
    });
  });

  test("ignores lifecycle evidence that predates this ambiguous submission", async () => {
    const oldTerminal = apiMessage({
      id: "assistant-old",
      metadata: {
        agent_runtime_turn: {
          turn_id: "request-old",
          status: "recoverable_failed",
          terminal: true,
        },
      },
    });

    const resolution = await resolveOrdinaryTransportAmbiguity(
      async () => [oldTerminal],
      new Set([oldTerminal.id]),
      "request-a",
    );

    expect(resolution).toEqual({ kind: "unknown", items: [oldTerminal] });
  });

  test("uses the response request id to correlate one newly returned lifecycle turn", async () => {
    const request = apiMessage({
      id: "request-new",
      role: "user",
      content: "Test AAPL",
      metadata: {},
    });
    const assistant = apiMessage({
      id: "assistant-new",
      metadata: {
        agent_runtime_turn: {
          turn_id: request.id,
          request_id: "request-a",
          status: "completed",
          terminal: true,
        },
      },
    });

    const resolution = await resolveOrdinaryTransportAmbiguity(
      async () => [request, assistant],
      new Set(),
      "request-a",
    );

    expect(resolution).toEqual({
      kind: "terminal",
      items: [request, assistant],
    });
  });

  test("does not attribute another tab's terminal turn to this submission", async () => {
    const tabBRequest = apiMessage({
      id: "tab-b-turn",
      role: "user",
      content: "Tab B turn",
      metadata: {},
    });
    const tabBAssistant = apiMessage({
      id: "tab-b-assistant",
      metadata: {
        agent_runtime_turn: {
          turn_id: tabBRequest.id,
          request_id: "request-b",
          status: "completed",
          terminal: true,
        },
      },
    });

    const resolution = await resolveOrdinaryTransportAmbiguity(
      async () => [tabBRequest, tabBAssistant],
      new Set(),
      "request-a",
    );

    expect(resolution).toEqual({
      kind: "unknown",
      items: [tabBRequest, tabBAssistant],
    });
  });

  test("does not infer ownership when response headers were never received", async () => {
    const request = apiMessage({
      id: "request-new",
      role: "user",
      metadata: {},
    });
    const assistant = apiMessage({
      id: "assistant-new",
      metadata: {
        agent_runtime_turn: {
          turn_id: request.id,
          request_id: "request-a",
          status: "completed",
          terminal: true,
        },
      },
    });

    const resolution = await resolveOrdinaryTransportAmbiguity(
      async () => [request, assistant],
      new Set(),
      null,
    );

    expect(resolution).toEqual({
      kind: "unknown",
      items: [request, assistant],
    });
  });

  test("loads cursor pages until a long-thread terminal turn is available", async () => {
    const firstPage = Array.from({ length: 50 }, (_, index) =>
      apiMessage({ id: `old-${index}` }),
    );
    const request = apiMessage({
      id: "request-new",
      role: "user",
      content: "Test AAPL.",
    });
    const assistant = apiMessage({
      id: "assistant-new",
      metadata: {
        agent_runtime_turn: {
          turn_id: request.id,
          request_id: "request-a",
          status: "completed",
          terminal: true,
        },
      },
    });
    const requestedCursors: Array<string | undefined> = [];
    const items = await loadAllConversationMessagePages(
      "conversation-1",
      async (_conversationId, _limit, cursor) => {
        requestedCursors.push(cursor);
        return cursor
          ? { items: [request, assistant], next_cursor: null }
          : { items: firstPage, next_cursor: "cursor-50" };
      },
    );

    const resolution = await resolveOrdinaryTransportAmbiguity(
      async () => items,
      new Set(firstPage.map((message) => message.id)),
      "request-a",
    );

    expect(requestedCursors).toEqual([undefined, "cursor-50"]);
    expect(resolution).toEqual({
      kind: "terminal",
      items: [...firstPage, request, assistant],
    });
  });

  test("stays unknown when more than one new lifecycle turn appears", async () => {
    const items = ["one", "two"].map((suffix) =>
      apiMessage({
        id: `assistant-${suffix}`,
        metadata: {
          agent_runtime_turn: {
            turn_id: `request-${suffix}`,
            status: "completed",
            terminal: true,
          },
        },
      }),
    );

    const resolution = await resolveOrdinaryTransportAmbiguity(
      async () => items,
      new Set(),
      "request-a",
    );

    expect(resolution).toEqual({ kind: "unknown", items });
  });

  test.each([
    {
      name: "the durable loader returns an incomplete page",
      existingMessageIds: new Set(
        Array.from({ length: 50 }, (_, index) => `old-${index}`),
      ),
      items: Array.from({ length: 50 }, (_, index) =>
        apiMessage({ id: `old-${index}`, metadata: {} }),
      ),
    },
    {
      name: "the baseline snapshot is unavailable",
      existingMessageIds: null,
      items: [apiMessage({ id: "old-1", metadata: {} })],
    },
  ])(
    "preserves the optimistic transcript while durable correlation is unknown: $name",
    async ({ existingMessageIds, items }) => {
      const optimistic: Message[] = [
        {
          id: "optimistic-user",
          role: "user",
          kind: "text",
          content: "Test the new turn",
        },
        {
          id: "optimistic-assistant",
          role: "ai",
          kind: "text",
          content: "",
        },
      ];
      const view = await resolveOrdinaryTransportAmbiguityView(
        async () => items,
        () => ({
          messages: [
            {
              id: "unrelated-hydrated",
              role: "ai",
              kind: "text",
              content: "Old page",
            },
          ],
          inputActions: [
            {
              id: "retry-last-turn",
              label: "Retry",
              type: "retry_last_turn",
              payload: { message: "Do not replay this turn" },
            },
          ],
        }),
        {
          assistantId: "optimistic-assistant",
          message: {
            id: "load-failure",
            role: "ai",
            kind: "text",
            content: "Could not load.",
          },
        },
        existingMessageIds,
        "request-a",
      );

      expect(applyViewMessages(view.messages, optimistic)).toEqual(optimistic);
      expect(view.inputActions).toEqual([]);
      expect(view.showChecking).toBe(true);
    },
  );

  test.each(["accepted", "running"])(
    "preserves the optimistic transcript while durable state is %s",
    async (status) => {
      const optimistic: Message[] = [
        {
          id: "optimistic-user",
          role: "user",
          kind: "text",
          content: "Test the new turn",
        },
        {
          id: "optimistic-assistant",
          role: "ai",
          kind: "text",
          content: "",
        },
      ];
      const request = apiMessage({
        id: "request-new",
        role: "user",
        metadata: {
          agent_runtime_turn: {
            turn_id: "request-new",
            request_id: "request-a",
            status,
            terminal: false,
          },
        },
      });
      const view = await resolveOrdinaryTransportAmbiguityView(
        async () => [request],
        () => ({
          messages: [
            {
              id: "durable-request",
              role: "user",
              kind: "text",
              content: "Durable request",
            },
          ],
          inputActions: [],
        }),
        {
          assistantId: "optimistic-assistant",
          message: {
            id: "load-failure",
            role: "ai",
            kind: "text",
            content: "Could not load.",
          },
        },
        new Set(),
        "request-a",
      );

      expect(applyViewMessages(view.messages, optimistic)).toEqual(optimistic);
      expect(view.inputActions).toEqual([]);
      expect(view.showChecking).toBe(true);
    },
  );

  test("hydrates durable messages and actions only after exact terminal correlation", async () => {
    const request = apiMessage({
      id: "request-new",
      role: "user",
      content: "Test AAPL",
    });
    const assistant = apiMessage({
      id: "assistant-new",
      metadata: {
        agent_runtime_turn: {
          turn_id: request.id,
          request_id: "request-a",
          status: "completed",
          terminal: true,
        },
      },
    });
    const hydratedMessages: Message[] = [
      {
        id: "durable-request",
        role: "user",
        kind: "text",
        content: "Test AAPL",
      },
      {
        id: "durable-assistant",
        role: "ai",
        kind: "text",
        content: "Completed.",
      },
    ];
    const hydratedActions = [
      {
        id: "next-action",
        label: "Continue",
        type: "suggested_prompt" as const,
        payload: { message: "Continue" },
      },
    ];
    const view = await resolveOrdinaryTransportAmbiguityView(
      async () => [request, assistant],
      () => ({
        messages: hydratedMessages,
        inputActions: hydratedActions,
      }),
      {
        assistantId: "optimistic-assistant",
        message: {
          id: "load-failure",
          role: "ai",
          kind: "text",
          content: "Could not load.",
        },
      },
      new Set(),
      "request-a",
    );

    expect(
      applyViewMessages(view.messages, [
        {
          id: "optimistic-user",
          role: "user",
          kind: "text",
          content: "Optimistic",
        },
      ]),
    ).toEqual(hydratedMessages);
    expect(view.inputActions).toEqual(hydratedActions);
    expect(view.showChecking).toBe(false);
  });

  test("does not surface hydrated retry controls while durable state is unknown", async () => {
    const item = apiMessage({ id: "unrelated", metadata: {} });
    const view = await resolveOrdinaryTransportAmbiguityView(
      async () => [item],
      () => ({
        messages: [],
        inputActions: [
          {
            id: "retry-last-turn",
            label: "Retry",
            type: "retry_last_turn",
            payload: { message: "Do not replay this turn" },
          },
        ],
      }),
      {
        assistantId: "local-assistant",
        message: {
          id: "load-failure",
          role: "ai",
          kind: "text",
          content: "Could not load.",
        },
      },
      new Set(),
      "request-a",
    );

    expect(view.inputActions).toEqual([]);
    expect(view.showChecking).toBe(true);
  });

  test("hydrates linked assistant retry from the persisted request message", () => {
    const request = apiMessage({
      id: "request-message-1",
      role: "user",
      content: "Test AAPL",
      metadata: {},
    });
    const assistant = apiMessage({
      id: "assistant-failed-1",
      metadata: {
        agent_runtime_turn: {
          turn_id: request.id,
          status: "recoverable_failed",
          terminal: true,
          retryable: true,
        },
        retry_last_turn: {
          request_message_id: request.id,
          message: "tampered browser text",
        },
      },
    });

    expect(retryRequestMessageForAssistant([request, assistant], assistant)).toEqual(
      request,
    );
    const hydrated = hydrateTextMessageFromApi(assistant, {
      retryRequestMessage: request,
    });

    expect(hydrated.actions).toEqual([
      {
        id: "retry-last-turn-request-message-1",
        label: "Retry",
        labelKey: "common.retry",
        value: "Retry",
        type: "retry_last_turn",
        payload: {
          request_message_id: "request-message-1",
          message: "Test AAPL",
          failed_assistant_id: "assistant-failed-1",
        },
      },
    ]);
  });

  test("rejects linked assistant retry without its persisted request message", () => {
    const assistant = apiMessage({
      metadata: {
        agent_runtime_turn: {
          turn_id: "missing-request",
          status: "recoverable_failed",
          terminal: true,
        },
        retry_last_turn: {
          request_message_id: "missing-request",
          message: "tampered browser text",
        },
      },
    });

    expect(retryRequestMessageForAssistant([assistant], assistant)).toBeNull();
    expect(hydrateTextMessageFromApi(assistant).actions).toBeUndefined();
  });

  test("suppresses hidden onboarding controls from retry hydration", () => {
    const message = hydrateTextMessageFromApi(
      apiMessage({
        metadata: {
          retry_last_turn: {
            message: "__ONBOARDING_GOAL__:test_stock_idea",
          },
        },
      }),
    );

    expect(message.actions).toBeUndefined();
  });

  test("does not hydrate retry when lifecycle and owning ids disagree", () => {
    const hydrated = hydrateTextMessageFromApi(
      apiMessage({
        id: "request-message-1",
        role: "user",
        content: "Test AAPL",
        metadata: {
          agent_runtime_turn: {
            turn_id: "foreign-request",
            status: "abandoned",
          },
          retry_last_turn: {
            request_message_id: "request-message-1",
            message: "Test AAPL",
          },
        },
      }),
    );

    expect(hydrated.actions).toBeUndefined();
  });

  test("hydrates a retry action from persisted assistant failure metadata", () => {
    const message = hydrateTextMessageFromApi(
      apiMessage({
        metadata: {
          recovery: {
            code: "runtime_failure",
            retryable: true,
          },
          retry_last_turn: {
            message: "what if I bought $125 of BTC every two weeks in 2022?",
          },
        },
      }),
    );

    expect(message.role).toBe("ai");
    expect(message.kind).toBe("text");
    expect(message.recoveryDisplay).toEqual({
      kind: "recovery_code",
      code: "runtime_failure",
      values: undefined,
    });
    expect(message.actions).toEqual([
      {
        id: "retry-last-turn",
        label: "Retry",
        labelKey: "common.retry",
        value: "Retry",
        type: "retry_last_turn",
        payload: {
          message: "what if I bought $125 of BTC every two weeks in 2022?",
          failed_assistant_id: "assistant-failed-1",
        },
      },
    ]);
  });

  test("does not expose retry actions on user messages", () => {
    const message = hydrateTextMessageFromApi(
      apiMessage({
        id: "user-1",
        role: "user",
        content: "Retry",
        metadata: {
          retry_last_turn: {
            message: "should stay server-side only",
          },
        },
      }),
    );

    expect(message.role).toBe("user");
    expect(message.actions).toBeUndefined();
  });

  test("hydrates coverage recovery actions from persisted typed metadata", () => {
    const message = hydrateTextMessageFromApi(
      apiMessage({
        id: "assistant-coverage-1",
        content: "Compatibility coverage recovery copy.",
        metadata: {
          clarification: {
            kind: "coverage_recovery",
            reason_code: "insufficient_common_data",
            requested_field: null,
            requested_fields: [
              "date_range",
              "asset_universe",
              "comparison_baseline",
            ],
            semantic_needs: ["simplification_choice"],
            payload: {
              strategy: { asset_universe: ["AAPL"] },
              coverage: {
                code: "insufficient_common_data",
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
          },
        },
      }),
    );

    expect(message.recoveryDisplay).toEqual({
      kind: "coverage_recovery",
      code: "insufficient_common_data",
    });
    expect(message.actions?.map((action) => action.labelKey)).toEqual([
      "chat.coverage_recovery.actions.change_dates",
      "chat.coverage_recovery.actions.change_asset",
      "chat.coverage_recovery.actions.change_benchmark",
    ]);
  });

  test("preserves persisted LLM coverage voice while hydrating all typed actions", () => {
    const exactLlmPrompt =
      "AAPL and SPY do not share enough history for one trustworthy test. Which part should we change?";
    const message = hydrateTextMessageFromApi(
      apiMessage({
        id: "assistant-coverage-llm",
        content: exactLlmPrompt,
        metadata: {
          clarification: {
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
              strategy: { asset_universe: ["AAPL"] },
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
                replacement_values: {
                  requested_field: "comparison_baseline",
                },
              },
            ],
          },
        },
      }),
    );

    expect(message.content).toBe(exactLlmPrompt);
    expect(message.recoveryDisplay).toBeNull();
    expect(message.actions?.map((action) => action.labelKey)).toEqual([
      "chat.coverage_recovery.actions.change_dates",
      "chat.coverage_recovery.actions.change_asset",
      "chat.coverage_recovery.actions.change_benchmark",
    ]);
  });

  test("preserves LLM timeframe voice while hydrating safe correction actions", () => {
    const exactLlmPrompt =
      "Five-minute bars are not supported. Choose daily or one-hour bars.";
    const message = hydrateTextMessageFromApi(
      apiMessage({
        id: "assistant-timeframe-llm",
        content: exactLlmPrompt,
        metadata: {
          clarification: {
            kind: "unsupported_recovery",
            reason_code: "unsupported_time_granularity",
            prompt_source: "llm_generated",
            requested_field: "timeframe",
            requested_fields: ["timeframe"],
            semantic_needs: ["simplification_choice"],
            payload: { raw_value: "5m" },
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
          },
        },
      }),
    );

    expect(message.content).toBe(exactLlmPrompt);
    expect(message.recoveryDisplay).toBeNull();
    expect(message.actions).toEqual([
      {
        id: "unsupported-timeframe-option-0",
        label: "Retry with daily bars",
        labelKey: "chat.clarification.timeframe_actions.daily",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-timeframe-llm",
          option_id: "option_0",
          replacement_values: { timeframe: "1D" },
        },
      },
      {
        id: "unsupported-timeframe-option-1",
        label: "Retry with 1-hour bars",
        labelKey: "chat.clarification.timeframe_actions.hour_1",
        type: "select_response_option",
        payload: {
          source_assistant_id: "assistant-timeframe-llm",
          option_id: "option_1",
          replacement_values: { timeframe: "1h" },
        },
      },
    ]);
  });

  test("reload keeps each strategy alternative once on its owning assistant", () => {
    const exactLlmPrompt =
      "I can't run momentum breakout yet. Choose a supported alternative.";
    const movingAverageReplacementValues = {
      strategy_type: "signal_strategy",
      rule_family: "moving_average_crossover",
    };
    const message = hydrateTextMessageFromApi(
      apiMessage({
        id: "assistant-strategy-llm",
        content: exactLlmPrompt,
        metadata: {
          clarification: {
            kind: "unsupported_recovery",
            reason_code: "unsupported_strategy_logic",
            prompt_source: "llm_generated",
            requested_field: "unsupported_constraints",
            semantic_needs: ["simplification_choice"],
            options: [
              {
                id: "rsi_threshold",
                replacement_values: { simplify_logic: "rsi_only" },
              },
              {
                id: "buy_and_hold",
                replacement_values: { strategy_type: "buy_and_hold" },
              },
              {
                id: "moving_average_crossover",
                replacement_values: movingAverageReplacementValues,
              },
            ],
          },
        },
      }),
    );

    expect(message.content).toBe(exactLlmPrompt);
    expect(message.recoveryDisplay).toBeNull();
    expect(message.actions?.map((action) => action.id)).toEqual([
      "unsupported-strategy-rsi-threshold",
      "unsupported-strategy-buy-and-hold",
      "unsupported-strategy-moving-average-crossover",
    ]);
    expect(message.actions?.map((action) => action.payload)).toEqual([
      {
        source_assistant_id: "assistant-strategy-llm",
        option_id: "rsi_threshold",
        replacement_values: { simplify_logic: "rsi_only" },
      },
      {
        source_assistant_id: "assistant-strategy-llm",
        option_id: "buy_and_hold",
        replacement_values: { strategy_type: "buy_and_hold" },
      },
      {
        source_assistant_id: "assistant-strategy-llm",
        option_id: "moving_average_crossover",
        replacement_values: movingAverageReplacementValues,
      },
    ]);
    expect(latestInputActions([message])).toEqual([]);
  });
});
