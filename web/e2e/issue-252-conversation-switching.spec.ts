import { expect, test, type Page, type Route } from "@playwright/test";

const CREATED_AT = "2026-07-28T12:00:00Z";
const USER_ID = "issue-252-user";

const CONVERSATION_IDS = [
  "conversation-a",
  "conversation-b",
  "conversation-c",
  "conversation-d",
  "conversation-e",
  "conversation-f",
  "conversation-g",
  "conversation-h",
  "conversation-i",
  "conversation-j",
] as const;
type ConversationId = (typeof CONVERSATION_IDS)[number];

function suffix(conversationId: ConversationId) {
  return conversationId.at(-1)?.toUpperCase() ?? "?";
}

function title(conversationId: ConversationId) {
  return `Conversation ${suffix(conversationId)}`;
}

function transcript(conversationId: ConversationId, index = 0) {
  return index === 0
    ? `Transcript ${suffix(conversationId)}`
    : `Transcript ${suffix(conversationId)} · message ${index}`;
}

type FixtureOptions = {
  delaysMs?: Partial<Record<ConversationId, number | number[]>>;
  decisionResultConversation?: ConversationId;
  failingAttempts?: Partial<Record<ConversationId, number[]>>;
  failureStatuses?: Partial<Record<ConversationId, number>>;
  language?: "en" | "es-419";
  messageBodyLengths?: Partial<Record<ConversationId, number>>;
  messageCounts?: Partial<Record<ConversationId, number>>;
  versionedResponses?: ConversationId[];
};

type FixtureState = {
  decisionRequestCount: number;
  decisionState: "watching" | null;
  messageRequestCounts: Record<ConversationId, number>;
  messageResponseCounts: Record<ConversationId, number>;
  unexpectedRequests: string[];
  userId: string;
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function conversation(conversationId: ConversationId) {
  return {
    id: conversationId,
    title: title(conversationId),
    title_source: "user_renamed",
    pinned: false,
    archived: false,
    deleted_at: null,
    created_at: CREATED_AT,
    updated_at: CREATED_AT,
    last_message_preview: `History summary ${suffix(conversationId)}`,
    language: "en",
  };
}

function messageContent(
  conversationId: ConversationId,
  index: number,
  attempt: number,
  bodyLength?: number,
  versioned = false,
) {
  const responseSuffix =
    versioned && attempt > 1 && index === 0 ? ` · response ${attempt}` : "";
  const base = `${transcript(conversationId, index)}${responseSuffix}`;
  if (!bodyLength || base.length >= bodyLength) return base;
  return `${base} ${"x".repeat(bodyLength - base.length - 1)}`;
}

function message(
  conversationId: ConversationId,
  index = 0,
  options: Readonly<{
    attempt?: number;
    bodyLength?: number;
    versioned?: boolean;
  }> = {},
) {
  return {
    id: `${conversationId}-assistant-${index}`,
    conversation_id: conversationId,
    role: "assistant",
    content: messageContent(
      conversationId,
      index,
      options.attempt ?? 1,
      options.bodyLength,
      options.versioned,
    ),
    created_at: new Date(Date.parse(CREATED_AT) + index * 1000).toISOString(),
    metadata: {},
  };
}

function resultMessage(
  conversationId: ConversationId,
  decisionState: "watching" | null,
) {
  return {
    ...message(conversationId),
    metadata: {
      latest_run_id: `run-${conversationId}`,
      result_conversation_id: conversationId,
      result_run_id: `run-${conversationId}`,
      result_card: {
        actions: [],
        asset_class: "equity",
        assumptions: ["Long only"],
        benchmark_note: "AAPL finished 1.2 points ahead of SPY.",
        date_range: {
          display: "Jul 28, 2025 to Jul 28, 2026",
          end: "2026-07-28",
          start: "2025-07-28",
        },
        decision_state: decisionState,
        evidence_artifact_id: `evidence-${conversationId}`,
        rows: [
          { key: "ending_value", label: "Ending value", value: "$11,200" },
          { key: "total_return_pct", label: "Total return", value: "12.0%" },
        ],
        status_label: "Simulation complete",
        strategy_label: "Buy and hold",
        symbols: ["AAPL"],
        title: "AAPL buy and hold",
      },
    },
  };
}

async function installConversationFixture(
  page: Page,
  options: FixtureOptions = {},
): Promise<FixtureState> {
  const language = options.language ?? "en";
  const state: FixtureState = {
    decisionRequestCount: 0,
    decisionState: null,
    messageRequestCounts: Object.fromEntries(
      CONVERSATION_IDS.map((conversationId) => [conversationId, 0]),
    ) as Record<ConversationId, number>,
    messageResponseCounts: Object.fromEntries(
      CONVERSATION_IDS.map((conversationId) => [conversationId, 0]),
    ) as Record<ConversationId, number>,
    unexpectedRequests: [],
    userId: USER_ID,
  };
  await page.addInitScript(() => {
    window.localStorage.setItem("argus:sidebar_mode", "expanded");
    window.localStorage.setItem("i18nextLng", "en");
    const clock = window as typeof window & {
      __issue252NowOffsetMs: number;
    };
    const initialNow = Date.now();
    clock.__issue252NowOffsetMs = 0;
    Date.now = () => initialNow + clock.__issue252NowOffsetMs;
  });

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname.endsWith("/api/v1/me")) {
      return json(route, {
        user: {
          id: state.userId,
          email: "issue-252@example.com",
          username: "issue252",
          display_name: "Issue 252",
          language,
          locale: language === "es-419" ? "es-419" : "en-US",
          onboarding: {
            completed: true,
            stage: "completed",
            language_confirmed: true,
            primary_goal: null,
          },
        },
        account_kind: "registered",
        guest: null,
        capabilities: {
          can_create_additional_conversation: true,
          can_manage_conversation: true,
          can_save_decision: true,
          can_manage_account: true,
          can_use_omnisearch: true,
          can_search_current_workspace: true,
          can_use_grounded_discovery: true,
          can_submit_feedback: true,
        },
        public_account_access_enabled: false,
      });
    }
    const decisionMatch = url.pathname.match(
      /\/api\/v1\/evidence-artifacts\/(evidence-conversation-[a-j])\/decision$/,
    );
    if (decisionMatch && request.method() === "POST") {
      const payload = request.postDataJSON() as {
        decision_state?: string;
        note?: string | null;
      };
      if (payload.decision_state !== "watching") {
        state.unexpectedRequests.push(
          `${request.method()} ${url.pathname} invalid-decision-state`,
        );
        return json(route, { detail: "Unexpected decision state" }, 422);
      }
      state.decisionRequestCount += 1;
      state.decisionState = "watching";
      const evidenceArtifactId = decisionMatch[1];
      return json(route, {
        decision: {
          id: "decision-issue-252",
          idea_id: "idea-issue-252",
          idea_version_id: "idea-version-issue-252",
          evidence_artifact_id: evidenceArtifactId,
          source_conversation_id: options.decisionResultConversation,
          decision_state: state.decisionState,
          note: payload.note ?? null,
          created_at: CREATED_AT,
          updated_at: CREATED_AT,
        },
        evidence_artifact: {
          id: evidenceArtifactId,
          idea_id: "idea-issue-252",
          idea_version_id: "idea-version-issue-252",
          source_conversation_id: options.decisionResultConversation,
          source_run_id: `run-${options.decisionResultConversation}`,
          artifact_type: "backtest",
          lifecycle: "active",
          title: "AAPL buy and hold",
          digest: "issue-252-decision",
          payload: {},
          created_at: CREATED_AT,
          updated_at: CREATED_AT,
        },
      });
    }
    if (url.pathname.endsWith("/api/v1/conversations")) {
      return json(route, {
        items: CONVERSATION_IDS.map(conversation),
        next_cursor: null,
      });
    }
    const messageMatch = url.pathname.match(
      /\/api\/v1\/conversations\/(conversation-[a-j])\/messages$/,
    );
    if (messageMatch) {
      const conversationId = messageMatch[1] as ConversationId;
      const attempt = ++state.messageRequestCounts[conversationId];
      const configuredDelay = options.delaysMs?.[conversationId] ?? 0;
      const delay = Array.isArray(configuredDelay)
        ? (configuredDelay[attempt - 1] ?? configuredDelay.at(-1) ?? 0)
        : configuredDelay;
      if (delay > 0) {
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
      state.messageResponseCounts[conversationId] += 1;
      if (options.failingAttempts?.[conversationId]?.includes(attempt)) {
        return json(
          route,
          { detail: "Controlled transcript failure" },
          options.failureStatuses?.[conversationId] ?? 503,
        );
      }
      const messageCount = options.messageCounts?.[conversationId] ?? 1;
      return json(route, {
        items:
          options.decisionResultConversation === conversationId
            ? [resultMessage(conversationId, state.decisionState)]
            : Array.from({ length: messageCount }, (_, index) =>
                message(conversationId, index, {
                  attempt,
                  bodyLength: options.messageBodyLengths?.[conversationId],
                  versioned:
                    options.versionedResponses?.includes(conversationId) ??
                    false,
                }),
              ),
        next_cursor: null,
      });
    }
    if (
      url.pathname.endsWith("/api/v1/auth/logout") &&
      request.method() === "POST"
    ) {
      return json(route, { success: true });
    }
    state.unexpectedRequests.push(
      `${request.method()} ${url.pathname}${url.search}`,
    );
    return json(route, { detail: "Unexpected issue #252 fixture request" }, 501);
  });
  return state;
}

async function openConversation(page: Page, conversationId: ConversationId) {
  const row = page.locator(
    `[role="button"][data-conversation-id="${conversationId}"]`,
  );
  if (await row.count() === 0) {
    const showMore = page
      .getByRole("button", { name: /Show more in|Mostrar más en/ })
      .first();
    if (await showMore.count()) {
      await showMore.click();
    }
  }
  if (await row.count() === 0) {
    await page.getByRole("button", { name: /Recents|Recientes/ }).click();
  }
  if (await row.count() === 0) {
    await page
      .getByRole("button", { name: /Show more in|Mostrar más en/ })
      .first()
      .click();
  }
  await row.click();
  await expect(page).toHaveURL(
    new RegExp(`conversation=${conversationId}(?:&|$)`),
  );
}

function transcriptText(page: Page, conversationId: ConversationId) {
  return page
    .getByTestId("conversation-transcript-region")
    .getByText(transcript(conversationId), { exact: true });
}

async function expectConversationOwner(
  page: Page,
  conversationId: ConversationId,
) {
  await expect(page).toHaveURL(
    new RegExp(`conversation=${conversationId}(?:&|$)`),
  );
  const row = page.locator(
    `[role="button"][data-conversation-id="${conversationId}"]`,
  );
  if (await row.count() === 0) {
    await page.getByRole("button", { name: /Recents|Recientes/ }).click();
  }
  await expect(row).toHaveAttribute("aria-current", "page");
  await expect(
    page.getByRole("heading", { level: 1, name: title(conversationId) }),
  ).toBeVisible();
}

async function advanceCacheTime(page: Page, milliseconds: number) {
  await page.evaluate((offset) => {
    const clock = window as typeof window & {
      __issue252NowOffsetMs: number;
    };
    clock.__issue252NowOffsetMs += offset;
  }, milliseconds);
}

test("a cold destination removes the previous transcript immediately", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page, {
    delaysMs: { "conversation-b": 500 },
  });
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();

  await openConversation(page, "conversation-b");

  expect(await transcriptText(page, "conversation-a").count()).toBe(0);
  await expect(transcriptText(page, "conversation-b")).toBeVisible();
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("a retired delayed request cannot replace the newest conversation", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page, {
    delaysMs: {
      "conversation-b": 450,
      "conversation-c": 50,
    },
  });
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();

  await openConversation(page, "conversation-b");
  await openConversation(page, "conversation-c");
  await expect(transcriptText(page, "conversation-c")).toBeVisible();

  await page.waitForTimeout(500);
  await expect(page).toHaveURL(/conversation=conversation-c(?:&|$)/);
  await expect(transcriptText(page, "conversation-c")).toBeVisible();
  await expect(transcriptText(page, "conversation-b")).toHaveCount(0);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("a delayed bootstrap A cannot overwrite B after B becomes selected", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page, {
    delaysMs: {
      "conversation-a": 500,
      "conversation-b": 50,
    },
  });
  await page.goto("/chat?conversation=conversation-a");

  await openConversation(page, "conversation-b");
  await expectConversationOwner(page, "conversation-b");
  await expect(transcriptText(page, "conversation-b")).toBeVisible();

  await page.waitForTimeout(550);
  await expectConversationOwner(page, "conversation-b");
  await expect(transcriptText(page, "conversation-b")).toBeVisible();
  await expect(transcriptText(page, "conversation-a")).toHaveCount(0);
  expect(fixture.messageResponseCounts["conversation-a"]).toBe(1);
  expect(fixture.messageResponseCounts["conversation-b"]).toBe(1);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("a delayed A to B to C race commits only C after A and B finish", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page, {
    delaysMs: {
      "conversation-a": 550,
      "conversation-b": 400,
      "conversation-c": 50,
    },
  });
  await page.goto("/chat?conversation=conversation-a");

  await openConversation(page, "conversation-b");
  await openConversation(page, "conversation-c");
  await expectConversationOwner(page, "conversation-c");
  await expect(transcriptText(page, "conversation-c")).toBeVisible();

  await page.waitForTimeout(600);
  await expectConversationOwner(page, "conversation-c");
  await expect(transcriptText(page, "conversation-c")).toBeVisible();
  await expect(transcriptText(page, "conversation-a")).toHaveCount(0);
  await expect(transcriptText(page, "conversation-b")).toHaveCount(0);
  expect(fixture.messageResponseCounts["conversation-a"]).toBe(1);
  expect(fixture.messageResponseCounts["conversation-b"]).toBe(1);
  expect(fixture.messageResponseCounts["conversation-c"]).toBe(1);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("fresh A to B to A switching is immediate and performs no duplicate GET", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page);
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  await openConversation(page, "conversation-b");
  await expect(transcriptText(page, "conversation-b")).toBeVisible();

  await openConversation(page, "conversation-a");
  await expectConversationOwner(page, "conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  await expect(page.getByTestId("conversation-retrieval-state")).toHaveCount(0);
  await expect(page.getByTestId("chat-input")).toHaveAttribute(
    "aria-disabled",
    "false",
  );
  expect(fixture.messageRequestCounts["conversation-a"]).toBe(1);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("a saved decision evicts only its owning fresh transcript", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page, {
    decisionResultConversation: "conversation-a",
  });
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  await openConversation(page, "conversation-b");
  await expect(transcriptText(page, "conversation-b")).toBeVisible();
  await openConversation(page, "conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  expect(fixture.messageRequestCounts["conversation-a"]).toBe(1);
  expect(fixture.messageRequestCounts["conversation-b"]).toBe(1);

  await page.getByRole("button", { name: "Add decision" }).click();
  await page.getByRole("button", { name: "Watching", exact: true }).click();
  await page.getByRole("button", { name: "Save decision" }).click();
  await expect(
    page.getByText("Decision: Watching", { exact: true }),
  ).toBeVisible();
  expect(fixture.decisionRequestCount).toBe(1);

  await openConversation(page, "conversation-b");
  await expect(transcriptText(page, "conversation-b")).toBeVisible();
  expect(fixture.messageRequestCounts["conversation-b"]).toBe(1);
  await openConversation(page, "conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();

  await expect(
    page.getByText("Decision: Watching", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Add decision" }),
  ).toHaveCount(0);
  expect(fixture.messageRequestCounts["conversation-a"]).toBe(2);
  expect(fixture.messageRequestCounts["conversation-b"]).toBe(1);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("stale cache stays usable and deduplicates one background revalidation", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page, {
    delaysMs: { "conversation-a": [0, 400] },
    failingAttempts: { "conversation-a": [2] },
  });
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  await openConversation(page, "conversation-b");
  await expect(transcriptText(page, "conversation-b")).toBeVisible();
  await advanceCacheTime(page, 30_001);

  await openConversation(page, "conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  await expect(page.getByTestId("conversation-retrieval-state")).toHaveCount(0);
  await expect(page.getByTestId("chat-input")).toHaveAttribute(
    "aria-disabled",
    "false",
  );
  await openConversation(page, "conversation-a");
  await expect.poll(
    () => fixture.messageRequestCounts["conversation-a"],
  ).toBe(2);

  await page.waitForTimeout(450);
  await expectConversationOwner(page, "conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  await expect(
    page.getByText("Couldn’t open this conversation.", { exact: true }),
  ).toHaveCount(0);
  expect(fixture.messageRequestCounts["conversation-a"]).toBe(2);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("a cold response below 150 ms never flashes the retrieval state", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page, {
    delaysMs: { "conversation-b": 80 },
  });
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();

  await openConversation(page, "conversation-b");
  await expectConversationOwner(page, "conversation-b");
  await expect(transcriptText(page, "conversation-a")).toHaveCount(0);
  await expect(transcriptText(page, "conversation-b")).toBeVisible();
  await expect(page.getByTestId("conversation-retrieval-state")).toHaveCount(0);
  expect(fixture.messageRequestCounts["conversation-b"]).toBe(1);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("a cold response above 150 ms owns a truthful transient busy state", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page, {
    delaysMs: { "conversation-b": 1_000 },
  });
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();

  const navigationStartedAt = await page.evaluate(() => performance.now());
  await openConversation(page, "conversation-b");
  await expectConversationOwner(page, "conversation-b");
  await expect(transcriptText(page, "conversation-a")).toHaveCount(0);
  await expect(
    page.getByTestId("conversation-transcript-region"),
  ).toHaveAttribute("aria-busy", "true");
  await expect(page.getByTestId("chat-input")).toHaveAttribute(
    "aria-disabled",
    "true",
  );
  await expect(page.getByTestId("conversation-retrieval-state")).toBeVisible();
  const retrievalVisibleAfterMs = await page.evaluate(
    (startedAt) => performance.now() - startedAt,
    navigationStartedAt,
  );
  expect(retrievalVisibleAfterMs).toBeGreaterThanOrEqual(150);
  expect(retrievalVisibleAfterMs).toBeLessThan(1_000);
  await expect(
    page.getByTestId("conversation-retrieval-state"),
  ).toHaveText("Opening conversation…");
  await expect(
    page.getByTestId("conversation-retrieval-announcement"),
  ).toHaveText("Opening conversation…");

  await expect(transcriptText(page, "conversation-b")).toBeVisible();
  await expect(page.getByTestId("conversation-retrieval-state")).toHaveCount(0);
  await expect(
    page.getByTestId("conversation-transcript-region"),
  ).toHaveAttribute("aria-busy", "false");
  await expect(page.getByTestId("chat-input")).toHaveAttribute(
    "aria-disabled",
    "false",
  );
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("destination failure stays owned by the destination and Retry reloads only it", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page, {
    delaysMs: { "conversation-b": 200 },
    failingAttempts: { "conversation-b": [1] },
  });
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();

  await openConversation(page, "conversation-b");
  await expectConversationOwner(page, "conversation-b");
  await expect(transcriptText(page, "conversation-a")).toHaveCount(0);
  await expect(
    page.getByText("Couldn’t open this conversation.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByTestId("conversation-transcript-region"),
  ).toHaveAttribute("aria-busy", "false");
  await expect(page.getByRole("button", { name: "Retry" })).toBeVisible();
  expect(fixture.messageRequestCounts["conversation-a"]).toBe(1);
  expect(fixture.messageRequestCounts["conversation-b"]).toBe(1);

  await page.getByRole("button", { name: "Retry" }).click();
  await expect(transcriptText(page, "conversation-b")).toBeVisible();
  await expectConversationOwner(page, "conversation-b");
  expect(fixture.messageRequestCounts["conversation-a"]).toBe(1);
  expect(fixture.messageRequestCounts["conversation-b"]).toBe(2);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("an interactive missing destination keeps its selected row title and focus", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page, {
    delaysMs: { "conversation-b": 200 },
    failingAttempts: { "conversation-b": [1] },
    failureStatuses: { "conversation-b": 404 },
  });
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  const bRow = page.locator(
    '[role="button"][data-conversation-id="conversation-b"]',
  );
  if (await bRow.count() === 0) {
    await page.getByRole("button", { name: /Recents|Recientes/ }).click();
  }

  await bRow.focus();
  await bRow.press("Space");
  await expect(
    page.getByText("Couldn’t open this conversation.", { exact: true }),
  ).toBeVisible();

  await expectConversationOwner(page, "conversation-b");
  await expect(bRow).toBeFocused();
  await expect(bRow).toHaveAttribute("aria-current", "page");
  await expect(transcriptText(page, "conversation-a")).toHaveCount(0);
  expect(fixture.messageRequestCounts["conversation-b"]).toBe(1);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("fresh revisits restore independent per-conversation scroll positions", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page, {
    messageCounts: {
      "conversation-a": 40,
      "conversation-b": 40,
    },
  });
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  const transcriptRegion = page.getByTestId("conversation-transcript-region");
  const aScrollTop = await transcriptRegion.evaluate((element) => {
    element.scrollTop = 220;
    element.dispatchEvent(new Event("scroll"));
    return element.scrollTop;
  });

  await openConversation(page, "conversation-b");
  await expect(transcriptText(page, "conversation-b")).toBeVisible();
  const bScrollTop = await transcriptRegion.evaluate((element) => {
    element.scrollTop = 440;
    element.dispatchEvent(new Event("scroll"));
    return element.scrollTop;
  });

  await openConversation(page, "conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  await expect.poll(
    () => transcriptRegion.evaluate((element) => element.scrollTop),
  ).toBeCloseTo(aScrollTop, 0);

  await openConversation(page, "conversation-b");
  await expect(transcriptText(page, "conversation-b")).toBeVisible();
  await expect.poll(
    () => transcriptRegion.evaluate((element) => element.scrollTop),
  ).toBeCloseTo(bScrollTop, 0);
  expect(fixture.messageRequestCounts["conversation-a"]).toBe(1);
  expect(fixture.messageRequestCounts["conversation-b"]).toBe(1);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("reload starts a new memory-only transcript session", async ({ page }) => {
  const fixture = await installConversationFixture(page);
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  expect(fixture.messageRequestCounts["conversation-a"]).toBe(1);

  await page.reload();
  await expectConversationOwner(page, "conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  expect(fixture.messageRequestCounts["conversation-a"]).toBe(2);
  const durableLeak = await page.evaluate((sentinel) => {
    const localValues = Object.values(window.localStorage);
    const sessionValues = Object.values(window.sessionStorage);
    return [...localValues, ...sessionValues].some((value) =>
      String(value).includes(sentinel),
    );
  }, transcript("conversation-a"));
  expect(durableLeak).toBe(false);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("logout clears the session before another authenticated user re-enters chat", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page);
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  await openConversation(page, "conversation-b");
  await expect(transcriptText(page, "conversation-b")).toBeVisible();

  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByRole("button", { name: "Log out" }).click();
  await expect(page).toHaveURL(/\/$/);

  fixture.userId = "issue-252-user-2";
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  expect(fixture.messageRequestCounts["conversation-a"]).toBe(2);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("keyboard selection remains focused and usable during an interruptible cold load", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page, {
    delaysMs: {
      "conversation-b": 1_000,
      "conversation-c": 50,
    },
  });
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  const bRow = page.locator(
    '[role="button"][data-conversation-id="conversation-b"]',
  );
  if (await bRow.count() === 0) {
    await page.getByRole("button", { name: /Recents|Recientes/ }).click();
  }

  await bRow.focus();
  await bRow.press("Space");
  await expectConversationOwner(page, "conversation-b");
  await expect(bRow).toBeFocused();
  await expect(page.getByTestId("conversation-retrieval-state")).toBeVisible();
  const animatedDescendants = await page
    .getByTestId("conversation-retrieval-state")
    .locator("*")
    .evaluateAll((elements) =>
      elements.filter(
        (element) => getComputedStyle(element).animationName !== "none",
      ).length,
    );
  expect(animatedDescendants).toBe(0);

  const cRow = page.locator(
    '[role="button"][data-conversation-id="conversation-c"]',
  );
  await cRow.focus();
  await cRow.press("Enter");
  await expectConversationOwner(page, "conversation-c");
  await expect(cRow).toBeFocused();
  await expect(transcriptText(page, "conversation-c")).toBeVisible();
  await page.waitForTimeout(400);
  await expect(transcriptText(page, "conversation-b")).toHaveCount(0);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("Spanish cold retrieval and failure copy remain destination-owned on mobile", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const fixture = await installConversationFixture(page, {
    language: "es-419",
    delaysMs: { "conversation-b": 1_000 },
    failingAttempts: { "conversation-b": [1] },
  });
  await page.goto("/chat?conversation=conversation-a");
  await expect(page.locator("html")).toHaveAttribute("lang", "es-419");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();

  await openConversation(page, "conversation-b");
  await expectConversationOwner(page, "conversation-b");
  await expect(page.getByTestId("conversation-retrieval-state")).toHaveText(
    "Abriendo la conversación…",
  );
  await expect(
    page.getByText("No se pudo abrir esta conversación.", { exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Reintentar" }),
  ).toBeVisible();
  await expect(transcriptText(page, "conversation-a")).toHaveCount(0);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("the eight-entry LRU bound refetches the oldest while retaining the newest", async ({
  page,
}) => {
  const fixture = await installConversationFixture(page);
  await page.goto("/chat?conversation=conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();

  for (const conversationId of CONVERSATION_IDS.slice(1)) {
    await openConversation(page, conversationId);
    await expect(transcriptText(page, conversationId)).toBeVisible();
  }
  expect(fixture.messageRequestCounts["conversation-j"]).toBe(1);

  await openConversation(page, "conversation-j");
  await expect(transcriptText(page, "conversation-j")).toBeVisible();
  expect(fixture.messageRequestCounts["conversation-j"]).toBe(1);

  await openConversation(page, "conversation-a");
  await expect(transcriptText(page, "conversation-a")).toBeVisible();
  expect(fixture.messageRequestCounts["conversation-a"]).toBe(2);
  expect(fixture.unexpectedRequests).toEqual([]);
});

type PerformanceScenario = "cold" | "fresh" | "long" | "stale";

async function ensureRecentRows(page: Page) {
  const row = page.locator(
    '[role="button"][data-conversation-id="conversation-b"]',
  );
  if (await row.count() === 0) {
    await page.getByRole("button", { name: /Recents|Recientes/ }).click();
  }
  await expect(row).toBeVisible();
}

async function armSwitchTimer(page: Page, conversationId: ConversationId) {
  await page.evaluate((targetConversationId) => {
    const row = document.querySelector<HTMLElement>(
      `[role="button"][data-conversation-id="${targetConversationId}"]`,
    );
    if (!row) throw new Error(`Missing Recent row for ${targetConversationId}`);
    const timingWindow = window as typeof window & {
      __issue252SwitchStart?: number;
    };
    row.addEventListener(
      "pointerdown",
      () => {
        timingWindow.__issue252SwitchStart = performance.now();
      },
      { once: true },
    );
  }, conversationId);
}

async function switchElapsedMs(page: Page) {
  return page.evaluate(async () => {
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    );
    const timingWindow = window as typeof window & {
      __issue252SwitchStart?: number;
    };
    if (timingWindow.__issue252SwitchStart === undefined) {
      throw new Error("The issue #252 switch timer was not armed.");
    }
    return performance.now() - timingWindow.__issue252SwitchStart;
  });
}

function nearestRank(values: number[], percentile: number) {
  const sorted = [...values].sort((left, right) => left - right);
  return sorted[Math.ceil(percentile * sorted.length) - 1] ?? 0;
}

test("records issue #252 p50 and p95 switching measurements", async ({
  browser,
}, testInfo) => {
  test.skip(
    process.env.ISSUE_252_PERF !== "true",
    "Set ISSUE_252_PERF=true for the bounded production-build measurement run.",
  );
  test.setTimeout(15 * 60_000);

  const warmups = 5;
  const observations = 50;
  const scenarioSamples: Record<PerformanceScenario, number[]> = {
    cold: [],
    fresh: [],
    long: [],
    stale: [],
  };
  const staleRevalidationSamples: number[] = [];

  for (const scenario of [
    "cold",
    "fresh",
    "stale",
    "long",
  ] as const) {
    for (let index = 0; index < warmups + observations; index += 1) {
      const context = await browser.newContext({
        deviceScaleFactor: 1,
        viewport: { width: 1440, height: 900 },
      });
      const page = await context.newPage();
      const fixture =
        scenario === "cold"
          ? await installConversationFixture(page, {
              delaysMs: { "conversation-b": 200 },
            })
          : scenario === "stale"
            ? await installConversationFixture(page, {
                delaysMs: { "conversation-a": [0, 200] },
                versionedResponses: ["conversation-a"],
              })
            : scenario === "long"
              ? await installConversationFixture(page, {
                  messageBodyLengths: { "conversation-b": 256 },
                  messageCounts: { "conversation-b": 1_000 },
                })
              : await installConversationFixture(page);

      await page.goto("/chat?conversation=conversation-a");
      await expect(transcriptText(page, "conversation-a")).toBeVisible();
      await ensureRecentRows(page);

      let elapsed: number;
      if (scenario === "fresh") {
        await openConversation(page, "conversation-b");
        await expect(transcriptText(page, "conversation-b")).toBeVisible();
        await armSwitchTimer(page, "conversation-a");
        await openConversation(page, "conversation-a");
        await expect(transcriptText(page, "conversation-a")).toBeVisible();
        elapsed = await switchElapsedMs(page);
        expect(fixture.messageRequestCounts["conversation-a"]).toBe(1);
      } else if (scenario === "stale") {
        await openConversation(page, "conversation-b");
        await expect(transcriptText(page, "conversation-b")).toBeVisible();
        await advanceCacheTime(page, 30_001);
        await armSwitchTimer(page, "conversation-a");
        await openConversation(page, "conversation-a");
        await expect(transcriptText(page, "conversation-a")).toBeVisible();
        elapsed = await switchElapsedMs(page);
        await expect(
          page
            .getByTestId("conversation-transcript-region")
            .getByText("Transcript A · response 2", { exact: true }),
        ).toBeVisible();
        const revalidationElapsed = await switchElapsedMs(page);
        if (index >= warmups) {
          staleRevalidationSamples.push(revalidationElapsed);
        }
        expect(fixture.messageRequestCounts["conversation-a"]).toBe(2);
        expect(fixture.messageResponseCounts["conversation-a"]).toBe(2);
      } else if (scenario === "long") {
        await armSwitchTimer(page, "conversation-b");
        await openConversation(page, "conversation-b");
        await expect(
          page
            .getByTestId("conversation-transcript-region")
            .getByText(
              messageContent("conversation-b", 999, 1, 256),
              { exact: true },
            ),
        ).toBeVisible();
        elapsed = await switchElapsedMs(page);
      } else {
        await armSwitchTimer(page, "conversation-b");
        await openConversation(page, "conversation-b");
        await expect(transcriptText(page, "conversation-b")).toBeVisible();
        elapsed = await switchElapsedMs(page);
      }

      expect(fixture.unexpectedRequests).toEqual([]);
      if (index >= warmups) {
        scenarioSamples[scenario].push(elapsed);
      }
      await context.close();
    }
  }

  const summarized = Object.fromEntries(
    Object.entries({
      ...scenarioSamples,
      stale_revalidation: staleRevalidationSamples,
    }).map(([name, samples]) => [
      name,
      {
        p50_ms: nearestRank(samples, 0.5),
        p95_ms: nearestRank(samples, 0.95),
        samples_ms: samples,
      },
    ]),
  );
  const report = {
    candidate_sha:
      process.env.ISSUE_252_CANDIDATE_SHA ?? "uncommitted-working-tree",
    browser: browser.version(),
    platform: `${process.platform}-${process.arch}`,
    viewport: { width: 1440, height: 900, device_scale_factor: 1 },
    warmups,
    observations,
    fixtures: {
      cold_delay_ms: 200,
      fresh_network_requests_on_revisit: 0,
      stale_revalidation_delay_ms: 200,
      long_messages: 1_000,
      long_message_body_characters: 256,
    },
    measurements: summarized,
  };
  const reportJson = JSON.stringify(report, null, 2);
  await testInfo.attach("issue-252-performance.json", {
    body: reportJson,
    contentType: "application/json",
  });
  console.log(`ISSUE_252_PERFORMANCE=${reportJson}`);
});
