import {
  expect,
  test,
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
} from "../lib/argus-api";

const NOW = "2026-08-01T16:00:00.000Z";
const EVIDENCE_DIR = process.env.CONVERSATION_ACTIVITY_EVIDENCE_DIR;
const IDS = [
  "activity-a",
  "activity-b",
  "activity-c",
  "activity-d",
  "activity-e",
  "activity-f",
] as const;
type ConversationId = (typeof IDS)[number];

type PendingStream = {
  message: string;
  resolve: () => void;
  promise: Promise<void>;
};

type ActivityFixtureOptions = {
  accountKind?: "guest" | "registered";
  activities?: Partial<Record<ConversationId, ConversationActivity>>;
  darkMode?: boolean;
  language?: "en" | "es-419";
  longTranscripts?: readonly ConversationId[];
  railTranscript?: ConversationId;
  sidebarMode?: "expanded" | "collapsed";
};

type ActivityFixture = {
  activities: Record<ConversationId, ConversationActivity>;
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

function activity(
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

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function title(conversationId: ConversationId) {
  return `Activity ${conversationId.at(-1)?.toUpperCase()}`;
}

function assistantMessage(
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

function userMessage(
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

function resultCard(runId: string) {
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

function resultMessage(
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

function backtestJob(
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

function backtestJobMessage(
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

function completedRun(conversationId: ConversationId): BacktestRun {
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

function makePendingStream(message: string): PendingStream {
  let resolve = () => undefined;
  const promise = new Promise<void>((done) => {
    resolve = done;
  });
  return { message, promise, resolve };
}

function longTranscript(conversationId: ConversationId): ApiMessage[] {
  return Array.from({ length: 44 }, (_, index) =>
    assistantMessage(
      conversationId,
      index,
      `Transcript ${conversationId} message ${index} ${"detail ".repeat(18)}`,
    ),
  );
}

function railTranscript(conversationId: ConversationId): ApiMessage[] {
  const messages = Array.from({ length: 12 }, (_, index) =>
    assistantMessage(conversationId, index),
  );
  messages[3] = resultMessage(conversationId, 3);
  messages[9] = resultMessage(conversationId, 9);
  return messages;
}

function recoveredClarificationRailTranscript(
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
          capital_amount: 10_000,
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
        statusLabel: "Ready to run",
        summary: "AAPL with the supplied dates.",
        rows: [{ label: "Assets", value: "AAPL" }],
      },
      confirmation_payload: {
        strategy: {
          strategy_type: "buy_and_hold",
          asset_universe: ["AAPL"],
          capital_amount: 10_000,
        },
      },
    },
  );
  return messages;
}

async function installActivityFixture(
  page: Page,
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
                message_limit: 10,
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
          activity: activities[conversationId],
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
          activity: activities[conversationId],
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
        return json(route, activities[conversationId]);
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
        return json(route, activities[conversationId]);
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

function recentRow(page: Page, conversationId: ConversationId) {
  return page.locator(
    `[role="button"][data-conversation-id="${conversationId}"]`,
  );
}

async function openRecents(page: Page, language: "en" | "es-419" = "en") {
  const row = recentRow(page, "activity-a");
  if (await row.count()) return;
  await page
    .getByRole("button", {
      name: language === "es-419" ? "Recientes" : "Recents",
    })
    .click();
}

async function openConversation(page: Page, conversationId: ConversationId) {
  await openRecents(page);
  await recentRow(page, conversationId).click();
  await expect(page).toHaveURL(
    new RegExp(`conversation=${conversationId}(?:&|$)`),
  );
}

async function refreshActivity(page: Page, fixture: ActivityFixture) {
  const before = fixture.conversationRequests.length;
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await expect
    .poll(() => fixture.conversationRequests.length)
    .toBeGreaterThan(before);
}

async function requiredBox(locator: Locator) {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  return box!;
}

async function captureEvidence(page: Page, filename: string) {
  if (!EVIDENCE_DIR) return;
  await page.screenshot({
    path: `${EVIDENCE_DIR}/${filename}`,
    fullPage: true,
  });
}

test("ordinary work remains owned by A after switching to B and clears only at visible latest", async ({
  page,
}) => {
  const fixture = await installActivityFixture(page);
  await page.goto("/chat?conversation=activity-a");
  await expect(page.locator("html")).not.toHaveClass(/dark/);
  await openRecents(page);

  await page.getByTestId("chat-input").fill("Keep working in A");
  await page.getByTestId("chat-send").click();
  await expect.poll(() => fixture.pendingStreams.has("activity-a")).toBe(true);
  await expect(
    recentRow(page, "activity-a").locator(
      '[data-conversation-activity="working"]',
    ),
  ).toBeVisible();

  await openConversation(page, "activity-b");
  await expect(page.getByTestId("chat-input")).toHaveAttribute(
    "aria-disabled",
    "false",
  );
  await captureEvidence(
    page,
    "01-en-desktop-light-working-a-viewing-b.png",
  );
  fixture.settleOrdinary("activity-a");

  const aRow = recentRow(page, "activity-a");
  await expect(
    aRow.locator('[data-conversation-activity="new_activity"]'),
  ).toBeVisible();
  await expect(page.getByText("Terminal response for activity-a")).toHaveCount(0);
  await captureEvidence(
    page,
    "02-en-desktop-light-settled-a-unread.png",
  );

  await openConversation(page, "activity-a");
  await expect(page.getByText("Terminal response for activity-a")).toBeVisible();
  await expect
    .poll(() => fixture.activityMutations)
    .toContainEqual({
      conversationId: "activity-a",
      body: {
        action: "mark_read",
        through_attention_cursor: "chat_turn:activity-a-1",
      },
    });
  await expect(aRow.locator("[data-conversation-activity]")).toHaveCount(0);
  expect(fixture.unexpectedRequests).toEqual([]);
});

for (const firstToSettle of ["activity-a", "activity-b"] as const) {
  test(`simultaneous A and B requests stay isolated when ${firstToSettle} settles first`, async ({
    page,
  }) => {
    const fixture = await installActivityFixture(page);
    await page.goto("/chat?conversation=activity-a");
    await openRecents(page);
    await page.getByTestId("chat-input").fill("Start A");
    await page.getByTestId("chat-send").click();
    await expect.poll(() => fixture.pendingStreams.has("activity-a")).toBe(true);

    await openConversation(page, "activity-b");
    await page.getByTestId("chat-input").fill("Start B");
    await page.getByTestId("chat-send").click();
    await expect.poll(() => fixture.pendingStreams.has("activity-b")).toBe(true);
    await expect(
      recentRow(page, "activity-a").locator(
        '[data-conversation-activity="working"]',
      ),
    ).toBeVisible();
    await expect(
      recentRow(page, "activity-b").locator(
        '[data-conversation-activity="working"]',
      ),
    ).toBeVisible();
    if (firstToSettle === "activity-a") {
      await captureEvidence(
        page,
        "03-en-desktop-light-simultaneous-a-b-working.png",
      );
    }

    fixture.settleOrdinary(firstToSettle);
    const other =
      firstToSettle === "activity-a" ? "activity-b" : "activity-a";
    await expect(
      recentRow(page, other).locator('[data-conversation-activity="working"]'),
    ).toBeVisible();
    await expect(page).toHaveURL(/conversation=activity-b(?:&|$)/);
    await expect(page.getByText("Terminal response for activity-a")).toHaveCount(
      0,
    );

    fixture.settleOrdinary(other);
    await expect(
      recentRow(page, "activity-a").locator(
        '[data-conversation-activity="new_activity"]',
      ),
    ).toBeVisible();
    await expect(page).toHaveURL(/conversation=activity-b(?:&|$)/);
    await expect(page.getByText("Terminal response for activity-a")).toHaveCount(0);
    expect(fixture.unexpectedRequests).toEqual([]);
  });
}

test("durable backtest stays working through queued, running, and checking before canonical result hydration", async ({
  page,
}) => {
  const fixture = await installActivityFixture(page);
  fixture.stageBacktest("activity-a", "queued");
  await page.goto("/chat?conversation=activity-a");
  await openRecents(page);
  await expect(page.getByText("Backtest queued", { exact: true })).toBeVisible();
  await openConversation(page, "activity-b");

  fixture.stageBacktest("activity-a", "running");
  await refreshActivity(page, fixture);
  await expect(
    recentRow(page, "activity-a").locator(
      '[data-conversation-activity="working"]',
    ),
  ).toBeVisible();

  fixture.stageBacktest("activity-a", "checking");
  await refreshActivity(page, fixture);
  await expect(recentRow(page, "activity-a")).toHaveAccessibleName(
    /Activity A\. Checking status\./,
  );
  await expect(
    recentRow(page, "activity-a").locator(
      '[data-conversation-activity="new_activity"]',
    ),
  ).toHaveCount(0);
  await captureEvidence(page, "04-en-desktop-light-backtest-checking.png");

  fixture.stageBacktest("activity-a", "ready");
  await refreshActivity(page, fixture);
  await expect(
    recentRow(page, "activity-a").locator(
      '[data-conversation-activity="new_activity"]',
    ),
  ).toBeVisible();
  await openConversation(page, "activity-a");
  await expect(page.getByText("Simulation Complete", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("heading", { name: "Buy and hold", exact: true }),
  ).toBeVisible();
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("completion while scrolled up keeps position and evolves the single Jump to latest control", async ({
  page,
}) => {
  const fixture = await installActivityFixture(page, {
    longTranscripts: ["activity-a"],
  });
  fixture.setActivity("activity-a", activity("running"));
  await page.goto("/chat?conversation=activity-a");
  await openRecents(page);
  const transcript = page.getByTestId("conversation-transcript-region");
  await expect(transcript.getByText(/Transcript activity-a message 43/)).toBeVisible();
  const scrollTop = await transcript.evaluate((element) => {
    element.scrollTop = 0;
    element.dispatchEvent(new Event("scroll"));
    return element.scrollTop;
  });
  const workingJump = page.getByRole("button", {
    name: "Jump to latest; Argus is working below",
  });
  await expect(workingJump).toBeVisible();
  await captureEvidence(page, "05-en-desktop-light-jump-working-below.png");

  fixture.setActivity(
    "activity-a",
    activity("idle", "new_activity", "chat_turn:activity-a-complete"),
  );
  await refreshActivity(page, fixture);
  await expect
    .poll(() => transcript.evaluate((element) => element.scrollTop))
    .toBeCloseTo(scrollTop, 0);
  const unreadJump = page.getByRole("button", { name: "Jump to new activity" });
  await expect(unreadJump).toBeVisible();
  await expect(page.getByRole("button", { name: /Jump to/ })).toHaveCount(1);
  await captureEvidence(page, "06-en-desktop-light-jump-unread-below.png");
  await unreadJump.focus();
  await unreadJump.press("Enter");
  await expect
    .poll(() => fixture.activityMutations)
    .toContainEqual({
      conversationId: "activity-a",
      body: {
        action: "mark_read",
        through_attention_cursor: "chat_turn:activity-a-complete",
      },
    });
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("restored older scroll and an older message anchor retain unread until latest", async ({
  page,
}) => {
  const fixture = await installActivityFixture(page, {
    longTranscripts: ["activity-a", "activity-c"],
  });
  await page.goto("/chat?conversation=activity-a");
  await openRecents(page);
  const transcript = page.getByTestId("conversation-transcript-region");
  await expect(transcript.getByText(/Transcript activity-a message 43/)).toBeVisible();
  await transcript.evaluate((element) => {
    element.scrollTop = 180;
    element.dispatchEvent(new Event("scroll"));
  });
  await openConversation(page, "activity-b");
  fixture.setActivity(
    "activity-a",
    activity("idle", "new_activity", "chat_turn:activity-a-restored"),
  );
  await refreshActivity(page, fixture);
  await openConversation(page, "activity-a");
  await expect(page.getByRole("button", { name: "Jump to new activity" })).toBeVisible();
  await captureEvidence(
    page,
    "07-en-desktop-light-restored-scroll-unread.png",
  );
  expect(
    fixture.activityMutations.some(
      (mutation) => mutation.conversationId === "activity-a",
    ),
  ).toBe(false);

  fixture.setActivity(
    "activity-c",
    activity("idle", "new_activity", "chat_turn:activity-c-anchor"),
  );
  await page.goto(
    "/chat?conversation=activity-c&message=activity-c-assistant-2",
  );
  await expect(page).toHaveURL(
    /conversation=activity-c&message=activity-c-assistant-2/,
  );
  await expect(
    transcript.locator('[data-message-id="activity-c-assistant-2"]'),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Jump to new activity" })).toBeVisible();
  await captureEvidence(page, "08-en-desktop-light-anchor-unread.png");
  expect(
    fixture.activityMutations.some(
      (mutation) => mutation.conversationId === "activity-c",
    ),
  ).toBe(false);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("row and header menus toggle durable unread without reordering or same-view self-clear", async ({
  page,
}) => {
  const fixture = await installActivityFixture(page);
  await page.goto("/chat?conversation=activity-a");
  await openRecents(page);
  const rowsBefore = await page
    .locator('[role="button"][data-conversation-id]')
    .evaluateAll((rows) => rows.map((row) => row.getAttribute("data-conversation-id")));
  const bRow = recentRow(page, "activity-b");
  const bTitle = bRow.getByText("Activity B", { exact: true });
  const rowBefore = await requiredBox(bRow);
  const titleBefore = await requiredBox(bTitle);
  const more = bRow.getByRole("button", { name: "More" });
  await more.focus();
  const moreBox = await requiredBox(more);
  expect(moreBox.width).toBeGreaterThanOrEqual(44);
  expect(moreBox.height).toBeGreaterThanOrEqual(44);
  await more.press("Enter");
  await expect(page.getByRole("menuitem").first()).toHaveText("Mark as unread");
  await captureEvidence(
    page,
    "09-en-desktop-light-recents-menu-mark-unread.png",
  );
  await page.getByRole("menuitem", { name: "Mark as unread" }).click();
  await expect(
    bRow.locator('[data-conversation-activity="manual_unread"]'),
  ).toBeVisible();
  const rowAfter = await requiredBox(bRow);
  const titleAfter = await requiredBox(bTitle);
  expect(rowAfter.y).toBeCloseTo(rowBefore.y, 1);
  expect(titleAfter.x).toBeCloseTo(titleBefore.x, 1);
  expect(
    await page
      .locator('[role="button"][data-conversation-id]')
      .evaluateAll((rows) => rows.map((row) => row.getAttribute("data-conversation-id"))),
  ).toEqual(rowsBefore);
  await captureEvidence(
    page,
    "10-en-desktop-light-recents-manual-unread-no-reorder.png",
  );

  const headerMenu = page.getByRole("button", { name: "Chat options" });
  await headerMenu.click();
  await expect(page.getByRole("menuitem").first()).toHaveText("Mark as unread");
  await captureEvidence(
    page,
    "11-en-desktop-light-header-menu-mark-unread.png",
  );
  await page.getByRole("menuitem", { name: "Mark as unread" }).click();
  const aRow = recentRow(page, "activity-a");
  await expect(
    aRow.locator('[data-conversation-activity="manual_unread"]'),
  ).toBeVisible();
  await refreshActivity(page, fixture);
  await expect(
    aRow.locator('[data-conversation-activity="manual_unread"]'),
  ).toBeVisible();
  await captureEvidence(
    page,
    "12-en-desktop-light-header-manual-unread.png",
  );

  await headerMenu.click();
  await expect(page.getByRole("menuitem").first()).toHaveText("Mark as read");
  await captureEvidence(
    page,
    "13-en-desktop-light-header-menu-mark-read.png",
  );
  await page.getByRole("menuitem", { name: "Mark as read" }).click();
  await expect(aRow.locator("[data-conversation-activity]")).toHaveCount(0);
  await captureEvidence(page, "14-en-desktop-light-header-marked-read.png");

  await bRow.getByRole("button", { name: "More" }).click();
  await page.keyboard.press("Escape");
  await expect(bRow.getByRole("button", { name: "More" })).toBeFocused();
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("expanded, collapsed, Quick Peek, selected, dark, and reduced-motion projections share one precedence", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const fixture = await installActivityFixture(page, {
    activities: {
      "activity-a": activity("running", "new_activity", "cursor-a"),
      "activity-b": activity("idle", "new_activity", "cursor-b"),
      "activity-c": activity("idle", "manual_unread", "cursor-c"),
      "activity-d": activity("idle", "needs_input", "cursor-d"),
      "activity-e": activity("idle", "needs_attention", "cursor-e"),
      "activity-f": activity("checking", "none", null, "backtest_job"),
    },
    darkMode: true,
    longTranscripts: ["activity-a"],
  });
  await page.goto("/chat?conversation=activity-a");
  await openRecents(page);
  await expect(page.locator("html")).toHaveClass(/dark/);
  await expect(recentRow(page, "activity-a")).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(recentRow(page, "activity-a")).toHaveAccessibleName(
    "Activity A. Working.",
  );
  await expect(recentRow(page, "activity-d")).toHaveAccessibleName(
    "Activity D. Needs your input.",
  );
  await expect(recentRow(page, "activity-e")).toHaveAccessibleName(
    "Activity E. Needs attention.",
  );
  const ring = recentRow(page, "activity-a").locator(
    '[data-conversation-activity="working"] svg',
  );
  expect(await ring.evaluate((node) => getComputedStyle(node).animationName)).toBe(
    "none",
  );
  await captureEvidence(
    page,
    "15-en-desktop-dark-reduced-expanded-selected.png",
  );

  await page.keyboard.press("Meta+Shift+Comma");
  const peek = page.getByRole("dialog", { name: "Recents" });
  await expect(
    peek.getByRole("button", { name: "Activity A. Working." }),
  ).toBeVisible();
  await expect(
    peek.getByRole("button", { name: "Activity E. Needs attention." }),
  ).toBeVisible();
  await captureEvidence(page, "16-en-desktop-dark-reduced-quick-peek.png");
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: "Collapse sidebar" }).click();
  const recents = page.getByRole("button", { name: "Recents" });
  await expect(
    recents.locator('[data-sidebar-activity-overlay="true"]'),
  ).toBeVisible();
  await expect(
    recents.locator('[data-conversation-activity="working"]'),
  ).toBeVisible();
  await captureEvidence(
    page,
    "17-en-desktop-dark-reduced-collapsed-aggregate.png",
  );

  const transcript = page.getByTestId("conversation-transcript-region");
  await transcript.evaluate((element) => {
    element.scrollTop = 0;
    element.dispatchEvent(new Event("scroll"));
  });
  const workingJump = page.getByRole("button", {
    name: "Jump to latest; Argus is working below",
  });
  await expect(workingJump).toBeVisible();
  const dotAnimations = await workingJump
    .locator("[data-working-dot]")
    .evaluateAll((nodes) =>
      nodes.map((node) => getComputedStyle(node).animationName),
    );
  expect(dotAnimations).toEqual(["none", "none", "none"]);
  await captureEvidence(
    page,
    "18-en-desktop-dark-reduced-static-working-below.png",
  );
  expect(fixture.unexpectedRequests).toEqual([]);
});

test.describe("390px coarse pointer", () => {
  test.use({
    viewport: { width: 390, height: 844 },
    hasTouch: true,
    isMobile: true,
  });

  test("mobile Recents keeps the touch-safe owner menu and typed activity labels", async ({
    page,
  }) => {
    const fixture = await installActivityFixture(page, {
      activities: {
        "activity-a": activity("running"),
        "activity-b": activity("idle", "new_activity", "cursor-b"),
      },
      language: "es-419",
    });
    await page.goto("/chat?conversation=activity-a");
    await openRecents(page, "es-419");
    await expect(page.locator("html")).toHaveAttribute("lang", "es-419");
    await expect(recentRow(page, "activity-a")).toHaveAccessibleName(
      "Activity A. En curso.",
    );
    await expect(recentRow(page, "activity-b")).toHaveAccessibleName(
      "Activity B. Actividad nueva.",
    );
    const more = recentRow(page, "activity-b").getByRole("button", {
      name: "Más",
    });
    await expect(more).toBeVisible();
    const box = await requiredBox(more);
    expect(box.width).toBeGreaterThanOrEqual(44);
    expect(box.height).toBeGreaterThanOrEqual(44);
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    ).toBe(true);
    await captureEvidence(page, "19-es-mobile-coarse-recents.png");
    expect(fixture.unexpectedRequests).toEqual([]);
  });
});

test("typed needs-input, attention, canceled, expired, and checking states do not alter the activity rail", async ({
  page,
}) => {
  const fixture = await installActivityFixture(page, {
    activities: {
      "activity-a": activity(),
      "activity-b": activity("idle", "needs_input", "cursor-b"),
      "activity-c": activity("idle", "needs_attention", "cursor-c"),
      "activity-d": activity("idle", "needs_attention", "cursor-d"),
      "activity-e": activity("checking", "none", null, "backtest_job"),
    },
    railTranscript: "activity-a",
  });
  const canceled = backtestJob("activity-c", "canceled");
  fixture.jobs["activity-c"] = canceled;
  fixture.messages["activity-c"] = [
    backtestJobMessage("activity-c", canceled),
  ];
  const expired = backtestJob("activity-d", "expired");
  fixture.jobs["activity-d"] = expired;
  fixture.messages["activity-d"] = [
    backtestJobMessage("activity-d", expired),
  ];
  await page.goto("/chat?conversation=activity-a");
  await openRecents(page);
  await expect(recentRow(page, "activity-b")).toHaveAccessibleName(
    "Activity B. Needs your input.",
  );
  await expect(recentRow(page, "activity-c")).toHaveAccessibleName(
    "Activity C. Needs attention.",
  );
  await expect(recentRow(page, "activity-d")).toHaveAccessibleName(
    "Activity D. Needs attention.",
  );
  await expect(recentRow(page, "activity-e")).toHaveAccessibleName(
    "Activity E. Checking status.",
  );
  await expect(page.getByTestId("conversation-activity-rail")).toBeVisible();
  await expect(
    page.getByRole("navigation", { name: "Conversation activity" }),
  ).toBeVisible();
  await expect(
    page
      .getByTestId("conversation-activity-rail")
      .locator("[data-conversation-activity]"),
  ).toHaveCount(0);
  await captureEvidence(
    page,
    "20-en-desktop-light-typed-attention-checking.png",
  );
  await openConversation(page, "activity-c");
  await expect(
    page.getByText("Backtest not completed", { exact: true }),
  ).toBeVisible();
  await openConversation(page, "activity-d");
  await expect(
    page.getByText("Backtest not completed", { exact: true }),
  ).toBeVisible();
  expect(fixture.unexpectedRequests).toEqual([]);
});

for (const [language, screenshot, completedLabel] of [
  [
    "en",
    "issue-337-en.png",
    "Backtest finished — AAPL · Buy and hold",
  ],
  [
    "es-419",
    "issue-337-es-419.png",
    "Backtest terminado — AAPL · Buy and hold",
  ],
] as const) {
  test(`resolved clarification clears its rail marker in ${language}`, async ({
    page,
  }) => {
    const fixture = await installActivityFixture(page, {
      accountKind: "guest",
      language,
      railTranscript: "activity-a",
    });
    fixture.messages["activity-a"] = recoveredClarificationRailTranscript(
      "activity-a",
    );

    await page.goto("/chat?conversation=activity-a");

    await expect(page.getByTestId("guest-temporary-notice")).toBeVisible();
    const rail = page.getByTestId("conversation-activity-rail");
    await expect(rail).toBeVisible();
    await expect(rail.getByRole("button")).toHaveCount(1);
    await expect(
      rail.getByRole("button", { name: completedLabel }),
    ).toBeVisible();
    await captureEvidence(page, screenshot);
    expect(fixture.unexpectedRequests).toEqual([]);
  });
}

test("Spanish desktop exposes the complete typed activity vocabulary", async ({
  page,
}) => {
  const fixture = await installActivityFixture(page, {
    activities: {
      "activity-a": activity("running"),
      "activity-b": activity("idle", "new_activity", "cursor-b"),
      "activity-c": activity("idle", "manual_unread", "cursor-c"),
      "activity-d": activity("idle", "needs_input", "cursor-d"),
      "activity-e": activity("idle", "needs_attention", "cursor-e"),
      "activity-f": activity("checking", "none", null, "backtest_job"),
    },
    language: "es-419",
  });
  await page.goto("/chat?conversation=activity-a");
  await openRecents(page, "es-419");
  await expect(page.locator("html")).toHaveAttribute("lang", "es-419");
  await expect(recentRow(page, "activity-a")).toHaveAccessibleName(
    "Activity A. En curso.",
  );
  await expect(recentRow(page, "activity-b")).toHaveAccessibleName(
    "Activity B. Actividad nueva.",
  );
  await expect(recentRow(page, "activity-c")).toHaveAccessibleName(
    "Activity C. Marcada como no leída.",
  );
  await expect(recentRow(page, "activity-d")).toHaveAccessibleName(
    "Activity D. Necesita tu respuesta.",
  );
  await expect(recentRow(page, "activity-e")).toHaveAccessibleName(
    "Activity E. Necesita atención.",
  );
  await page.getByRole("button", { name: "Mostrar más en Hoy" }).click();
  await expect(recentRow(page, "activity-f")).toHaveAccessibleName(
    "Activity F. Consultando el estado.",
  );
  await captureEvidence(page, "21-es-desktop-activity-labels.png");
  expect(fixture.unexpectedRequests).toEqual([]);
});
