import {
  expect,
  type BrowserContext,
  type Locator,
  type Page,
  type Route,
} from "@playwright/test";
import type {
  ApiMessage,
  BacktestJob,
  BacktestRun,
  ConversationActivity,
  ConversationActivityPatch,
  ConversationResultCard,
} from "../../lib/argus-api";

export const NOW = new Date().toISOString();
export const EVIDENCE_DIR = process.env.CONVERSATION_ACTIVITY_EVIDENCE_DIR;
export const IDS = [
  "activity-a",
  "activity-b",
  "activity-c",
  "activity-d",
  "activity-e",
  "activity-f",
] as const;
export type ConversationId = (typeof IDS)[number];

export type PendingStream = {
  message: string;
  resolve: () => void;
  promise: Promise<void>;
};

export type ActivityFixtureOptions = {
  accountKind?: "guest" | "registered";
  activities?: Partial<Record<ConversationId, ConversationActivity>>;
  darkMode?: boolean;
  language?: "en" | "es-419";
  longTranscripts?: readonly ConversationId[];
  railTranscript?: ConversationId;
  sidebarMode?: "expanded" | "collapsed";
};

export type ActivityFixture = {
  activities: Record<ConversationId, ConversationActivity>;
  hideWorkingFrom: Set<Page>;
  activityMutations: Array<{
    conversationId: ConversationId;
    body: ConversationActivityPatch;
  }>;
  conversationRequests: string[];
  messageRequests: Array<{
    conversationId: ConversationId;
    anchorMessageId: string | null;
  }>;
  pendingStreams: Map<ConversationId, PendingStream>;
  unexpectedRequests: string[];
  jobs: Partial<Record<ConversationId, BacktestJob>>;
  messages: Record<ConversationId, ApiMessage[]>;
  setActivity: (
    conversationId: ConversationId,
    next: ConversationActivity,
  ) => void;
  settleOrdinary: (
    conversationId: ConversationId,
    attention?: ConversationActivity["attention"]["status"],
  ) => void;
  stageBacktest: (
    conversationId: ConversationId,
    status: "queued" | "running" | "checking" | "ready",
  ) => void;
};

export function activity(
  operation: ConversationActivity["operation"]["status"] = "idle",
  attention: ConversationActivity["attention"]["status"] = "none",
  cursor: string | null = null,
  kind: ConversationActivity["operation"]["kind"] =
    operation === "idle" ? null : "chat_turn",
): ConversationActivity {
  return {
    operation: {
      status: operation,
      kind,
      updated_at: operation === "idle" ? null : NOW,
    },
    attention: { status: attention, cursor },
  };
}

export function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

export function title(conversationId: ConversationId) {
  return `Activity ${conversationId.at(-1)?.toUpperCase()}`;
}

export function assistantMessage(
  conversationId: ConversationId,
  index: number,
  content = `Transcript ${conversationId} message ${index}`,
  metadata: Record<string, unknown> = {},
): ApiMessage {
  return {
    id: `${conversationId}-assistant-${index}`,
    conversation_id: conversationId,
    role: "assistant",
    content,
    created_at: new Date(Date.parse(NOW) + index * 1_000).toISOString(),
    metadata,
  };
}

export function userMessage(
  conversationId: ConversationId,
  index: number,
  content: string,
): ApiMessage {
  return {
    id: `${conversationId}-user-${index}`,
    conversation_id: conversationId,
    role: "user",
    content,
    created_at: new Date(Date.parse(NOW) + index * 1_000).toISOString(),
    metadata: {},
  };
}

export function resultCard(runId: string): ConversationResultCard {
  return {
    title: "AAPL buy and hold",
    strategy_label: "Buy and hold",
    symbols: ["AAPL"],
    asset_class: "equity",
    date_range: {
      start: "2025-08-01",
      end: "2026-08-01",
      display: "Aug 1, 2025 to Aug 1, 2026",
    },
    status_label: "Simulation complete",
    rows: [
      { key: "ending_value", label: "Ending value", value: "$11,200" },
      { key: "total_return_pct", label: "Total return", value: "12.0%" },
    ],
    assumptions: ["Long only", "Benchmark: SPY"],
    actions: [],
    evidence_artifact_id: `evidence-${runId}`,
  };
}

export function resultMessage(
  conversationId: ConversationId,
  index: number,
): ApiMessage {
  const runId = `run-${conversationId}-${index}`;
  return assistantMessage(
    conversationId,
    index,
    `Quick take for ${conversationId}.`,
    {
      latest_run_id: runId,
      result_conversation_id: conversationId,
      result_run_id: runId,
      result_card: resultCard(runId),
    },
  );
}

export function backtestJob(
  conversationId: ConversationId,
  status: BacktestJob["status"],
): BacktestJob {
  return {
    id: `job-${conversationId}`,
    conversation_id: conversationId,
    request_message_id: `${conversationId}-user-run`,
    confirmation_message_id: `${conversationId}-confirmation`,
    status,
    result_run_id: status === "succeeded" ? `run-${conversationId}` : null,
    failure_code: null,
    failure_detail: null,
    retryable: false,
    queued_at: NOW,
    started_at: status === "queued" ? null : NOW,
    finished_at:
      status === "succeeded" ||
      status === "failed" ||
      status === "canceled" ||
      status === "expired"
        ? NOW
        : null,
    created_at: NOW,
    updated_at: NOW,
  };
}

export function backtestJobMessage(
  conversationId: ConversationId,
  job: BacktestJob,
): ApiMessage {
  return assistantMessage(
    conversationId,
    1,
    "The durable backtest is still in progress.",
    { backtest_job: job, backtest_job_id: job.id },
  );
}

export function completedRun(conversationId: ConversationId): BacktestRun {
  const runId = `run-${conversationId}`;
  return {
    id: runId,
    conversation_id: conversationId,
    strategy_id: null,
    status: "completed",
    asset_class: "equity",
    symbols: ["AAPL"],
    allocation_method: "equal_weight",
    benchmark_symbol: "SPY",
    metrics: {
      aggregate: { performance: { total_return_pct: 12 } },
      by_symbol: {},
    },
    config_snapshot: {
      template: "buy_and_hold",
      benchmark_symbol: "SPY",
    },
    conversation_result_card: resultCard(runId),
    chart: null,
    trades: [],
    created_at: NOW,
  };
}

export function makePendingStream(message: string): PendingStream {
  let resolve: () => void = () => undefined;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { message, promise, resolve };
}

export function longTranscript(conversationId: ConversationId): ApiMessage[] {
  return Array.from({ length: 44 }, (_, index) =>
    assistantMessage(
      conversationId,
      index,
      `Transcript ${conversationId} message ${index} ${"detail ".repeat(18)}`,
    ),
  );
}

export function railTranscript(conversationId: ConversationId): ApiMessage[] {
  const messages = Array.from({ length: 12 }, (_, index) =>
    assistantMessage(conversationId, index),
  );
  messages[3] = resultMessage(conversationId, 3);
  messages[9] = resultMessage(conversationId, 9);
  return messages;
}

export function recoveredClarificationRailTranscript(
  conversationId: ConversationId,
): ApiMessage[] {
  const messages = Array.from({ length: 12 }, (_, index) =>
    assistantMessage(conversationId, index),
  );
  messages[3] = resultMessage(conversationId, 3);
  messages[1] = assistantMessage(
    conversationId,
    1,
    "Which asset should I test?",
    {
      clarification: {
        kind: "clarification",
        prompt_source: "degraded_fallback",
        requested_field: "asset_universe",
        semantic_needs: ["asset_target"],
      },
      pending_strategy: {
        requested_field: "asset_universe",
        strategy: {
          strategy_type: "buy_and_hold",
          date_range: "past year",
          capital_amount: 10_000,
          extra_parameters: {
            date_range_raw_text: "past year",
            requested_date_range: {
              start: "2025-08-01",
              end: "2026-08-01",
            },
          },
        },
      },
    },
  );
  messages[10] = userMessage(conversationId, 10, "AAPL");
  messages[11] = assistantMessage(
    conversationId,
    11,
    "Here is the ready-to-run confirmation.",
    {
      confirmation_card: {
        confirmation_state: "active",
        title: "AAPL buy and hold",
        statusLabel: "Ready to run",        rows: [{ label: "Assets", value: "AAPL" }],
      },
      confirmation_payload: {
        strategy: {
          strategy_type: "buy_and_hold",
          asset_universe: ["AAPL"],
          date_range: { start: "2025-08-01", end: "2026-08-01" },
          capital_amount: 10_000,
          extra_parameters: {
            date_range_raw_text: "past year",
            requested_date_range: {
              start: "2025-08-01",
              end: "2026-08-01",
            },
            effective_date_range: {
              start: "2025-08-01",
              end: "2026-08-01",
            },
          },
        },
      },
    },
  );
  return messages;
}

export async function installActivityFixture(
  page: Page | BrowserContext,
  options: ActivityFixtureOptions = {},
): Promise<ActivityFixture> {
  const accountKind = options.accountKind ?? "registered";
  const language = options.language ?? "en";
  const activities = Object.fromEntries(
    IDS.map((conversationId) => [
      conversationId,
      options.activities?.[conversationId] ?? activity(),
    ]),
  ) as Record<ConversationId, ConversationActivity>;
  const messages = Object.fromEntries(
    IDS.map((conversationId) => [
      conversationId,
      options.railTranscript === conversationId
        ? railTranscript(conversationId)
        : options.longTranscripts?.includes(conversationId)
          ? longTranscript(conversationId)
          : [assistantMessage(conversationId, 0)],
    ]),
  ) as Record<ConversationId, ApiMessage[]>;
  const fixture: ActivityFixture = {
    activities,
    hideWorkingFrom: new Set(),
    activityMutations: [],
    conversationRequests: [],
    messageRequests: [],
    pendingStreams: new Map(),
    unexpectedRequests: [],
    jobs: {},
    messages,
    setActivity: (conversationId, next) => {
      activities[conversationId] = next;
    },
    settleOrdinary: (conversationId, attention = "new_activity") => {
      const pending = fixture.pendingStreams.get(conversationId);
      if (!pending) {
        throw new Error(`No pending stream for ${conversationId}`);
      }
      const index = messages[conversationId].length;
      messages[conversationId].push(
        userMessage(conversationId, index, pending.message),
        assistantMessage(
          conversationId,
          index + 1,
          `Terminal response for ${conversationId}`,
        ),
      );
      activities[conversationId] = activity(
        "idle",
        attention,
        `chat_turn:${conversationId}-${index}`,
      );
      pending.resolve();
    },
    stageBacktest: (conversationId, status) => {
      if (status === "ready") {
        fixture.jobs[conversationId] = backtestJob(
          conversationId,
          "succeeded",
        );
        messages[conversationId] = [resultMessage(conversationId, 2)];
        activities[conversationId] = activity(
          "idle",
          "new_activity",
          `backtest_job:${conversationId}`,
        );
        return;
      }
      const jobStatus = status === "checking" ? "succeeded" : status;
      const job = backtestJob(conversationId, jobStatus);
      fixture.jobs[conversationId] = job;
      messages[conversationId] = [backtestJobMessage(conversationId, job)];
      activities[conversationId] = activity(
        status,
        "none",
        null,
        "backtest_job",
      );
    },
  };

  await page.addInitScript(
    ({ darkMode, fixtureLanguage, sidebarMode }) => {
      window.localStorage.setItem("argus:sidebar_mode", sidebarMode);
      window.localStorage.setItem("i18nextLng", fixtureLanguage);
      window.localStorage.setItem(
        "argus-theme",
        darkMode ? "dark" : "light",
      );
      Object.defineProperty(window.navigator, "userAgent", {
        configurable: true,
        value:
          "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/138 Safari/537.36",
      });
    },
    {
      darkMode: options.darkMode ?? false,
      fixtureLanguage: language,
      sidebarMode: options.sidebarMode ?? "expanded",
    },
  );

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const activityFor = (id: ConversationId): ConversationActivity => ({
      ...(fixture.hideWorkingFrom.has(request.frame().page()) && id === "activity-a" ? activity() : activities[id]),
      latest_message_id: messages[id].at(-1)?.id ?? null,
    });

    if (url.pathname.endsWith("/api/v1/memory/availability")) {
      return json(route, { enabled: false });
    }

    if (url.pathname.endsWith("/api/v1/me")) {
      return json(route, {
        user: {
          id: "conversation-activity-user",
          email: accountKind === "guest" ? null : "activity@example.com",
          username: accountKind === "guest" ? null : "activity",
          display_name: accountKind === "guest" ? null : "Activity QA",
          language,
          locale: language === "es-419" ? "es-419" : "en-US",
          onboarding: {
            completed: accountKind === "registered",
            stage:
              accountKind === "guest" ? "language_selection" : "completed",
            language_confirmed: accountKind === "registered",
            primary_goal: null,
          },
        },
        account_kind: accountKind,
        guest:
          accountKind === "guest"
            ? {
                expires_at: "2026-08-08T16:00:00.000Z",
                conversation_limit: 1,
                simulation_limit: 1,
                feedback_limit: 5,
              }
            : null,
        capabilities: {
          can_create_additional_conversation: accountKind === "registered",
          can_manage_conversation: accountKind === "registered",
          can_save_decision: accountKind === "registered",
          can_manage_account: accountKind === "registered",
          can_use_omnisearch: accountKind === "registered",
          can_search_current_workspace: accountKind === "registered",
          can_use_grounded_discovery: accountKind === "registered",
          can_submit_feedback: true,
        },
        public_account_access_enabled: false,
      });
    }

    if (
      url.pathname.endsWith("/api/v1/conversations") &&
      request.method() === "GET"
    ) {
      fixture.conversationRequests.push(`${url.pathname}${url.search}`);
      return json(route, {
        items: IDS.map((conversationId, index) => ({
          id: conversationId,
          title: title(conversationId),
          title_source: "user_renamed",
          pinned: false,
          archived: false,
          deleted_at: null,
          created_at: new Date(Date.parse(NOW) - index * 1_000).toISOString(),
          updated_at: new Date(Date.parse(NOW) - index * 1_000).toISOString(),
          last_message_preview: `Summary ${conversationId}`,
          language,
          activity: activityFor(conversationId),
        })),
        next_cursor: null,
      });
    }

    if (
      url.pathname.endsWith("/api/v1/history") &&
      request.method() === "GET"
    ) {
      return json(route, {
        items: IDS.map((conversationId, index) => ({
          type: "chat",
          id: conversationId,
          title: title(conversationId),
          title_source: "user_renamed",
          subtitle: `Summary ${conversationId}`,
          pinned: false,
          created_at: new Date(Date.parse(NOW) - index * 1_000).toISOString(),
          conversation_id: conversationId,
          activity: activityFor(conversationId),
        })),
        next_cursor: null,
      });
    }

    const messageMatch = url.pathname.match(
      /\/api\/v1\/conversations\/(activity-[a-f])\/messages$/,
    );
    if (messageMatch && request.method() === "GET") {
      const conversationId = messageMatch[1] as ConversationId;
      fixture.messageRequests.push({
        conversationId,
        anchorMessageId: url.searchParams.get("anchor_message_id"),
      });
      return json(route, {
        items: messages[conversationId],
        next_cursor: null,
      });
    }

    const activityMatch = url.pathname.match(
      /\/api\/v1\/conversations\/(activity-[a-f])\/activity$/,
    );
    if (activityMatch) {
      const conversationId = activityMatch[1] as ConversationId;
      if (request.method() === "GET") {
        return json(route, activityFor(conversationId));
      }
      if (request.method() === "PATCH") {
        const body = request.postDataJSON() as ConversationActivityPatch;
        fixture.activityMutations.push({ conversationId, body });
        const current = activities[conversationId];
        if (body.action === "mark_unread") {
          activities[conversationId] = activity(
            current.operation.status,
            "manual_unread",
            current.attention.cursor ?? null,
            current.operation.kind ?? null,
          );
        } else if (
          body.through_attention_cursor === null ||
          body.through_attention_cursor === current.attention.cursor
        ) {
          activities[conversationId] = activity(
            current.operation.status,
            "none",
            null,
            current.operation.kind ?? null,
          );
        }
        return json(route, activityFor(conversationId));
      }
    }

    const jobMatch = url.pathname.match(
      /\/api\/v1\/backtest-jobs\/job-(activity-[a-f])$/,
    );
    if (jobMatch && request.method() === "GET") {
      const conversationId = jobMatch[1] as ConversationId;
      const job = fixture.jobs[conversationId];
      if (!job) return json(route, { detail: "Missing job" }, 404);
      return json(route, {
        job,
        run:
          job.status === "succeeded" &&
          activities[conversationId].attention.status === "new_activity"
            ? completedRun(conversationId)
            : null,
      });
    }

    if (
      url.pathname.endsWith("/api/v1/chat/stream") &&
      request.method() === "POST"
    ) {
      const body = request.postDataJSON() as {
        conversation_id?: string;
        message?: string;
      };
      const conversationId = body.conversation_id as ConversationId;
      const pending = makePendingStream(body.message ?? "Activity turn");
      fixture.pendingStreams.set(conversationId, pending);
      activities[conversationId] = activity(
        "running",
        activities[conversationId].attention.status,
        activities[conversationId].attention.cursor ?? null,
        "chat_turn",
      );
      await pending.promise;
      const terminalIndex = messages[conversationId].length - 1;
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: [
          'data: {"type":"stage_start","stage":"clarify"}',
          "",
          `data: ${JSON.stringify({
            type: "final",
            payload: {
              stage_outcome: "ready_to_respond",
              assistant_response: `Terminal response for ${conversationId}`,
              message_id: `${conversationId}-assistant-${terminalIndex}`,
              conversation_id: conversationId,
            },
          })}`,
          "",
          "data: [DONE]",
          "",
        ].join("\n"),
      });
    }

    fixture.unexpectedRequests.push(
      `${request.method()} ${url.pathname}${url.search}`,
    );
    return json(route, { detail: "Unexpected activity fixture request" }, 501);
  });

  return fixture;
}

export function recentRow(page: Page, conversationId: ConversationId) {
  return page.locator(
    `[role="button"][data-conversation-id="${conversationId}"]`,
  );
}

export async function openRecents(page: Page, language: "en" | "es-419" = "en") {
  const row = recentRow(page, "activity-a");
  if (await row.count()) return;
  await page
    .getByRole("button", {
      name: language === "es-419" ? "Recientes" : "Recents",
    })
    .click();
}

export async function openConversation(page: Page, conversationId: ConversationId) {
  await openRecents(page);
  await recentRow(page, conversationId).click();
  await expect(page).toHaveURL(
    new RegExp(`conversation=${conversationId}(?:&|$)`),
  );
}

export async function refreshActivity(page: Page, fixture: ActivityFixture) {
  const before = fixture.conversationRequests.length;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect
    .poll(() => fixture.conversationRequests.length)
    .toBeGreaterThan(before);
}

export async function requiredBox(locator: Locator) {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  return box!;
}

export async function captureEvidence(page: Page, filename: string) {
  if (!EVIDENCE_DIR) return;
  await page.screenshot({
    path: `${EVIDENCE_DIR}/${filename}`,
    fullPage: true,
  });
}

