import {
  expect,
  test,
  type Locator,
  type Page,
  type Route,
} from "@playwright/test";
import type {
  ConversationActivity,
  ConversationActivityPatch,
} from "../lib/argus-api";

const TODAY = "2026-07-28T16:00:00.000Z";
const CURSOR = "issue-245-page-2";
const EVIDENCE_DIR = process.env.ISSUE_245_EVIDENCE_DIR;

type FixtureState = {
  activityMutations: Array<{
    conversationId: string;
    body: ConversationActivityPatch;
  }>;
  conversationRequests: string[];
  historyRequests: string[];
  messageRequests: string[];
  mutations: Array<{
    method: "DELETE" | "PATCH";
    conversationId: string;
    body?: Record<string, unknown>;
  }>;
  streamRequests: Array<Record<string, unknown>>;
  unexpectedRequests: string[];
};

type ConversationRecord = ReturnType<typeof conversation>;
type ShortcutPlatform = "mac" | "other";

type FixtureOptions = {
  darkMode?: boolean;
  firstPage?: ConversationRecord[];
  firstPageDelayMs?: number;
  firstPageDelayOnRequest?: number;
  language?: "en" | "es-419";
  secondPage?: ConversationRecord[];
  secondPageDelayMs?: number;
  secondPageFailures?: number;
  shortcutPlatform?: ShortcutPlatform;
  streamDelayMs?: number;
};

const activity = (
  operation: ConversationActivity["operation"]["status"] = "idle",
  attention: ConversationActivity["attention"]["status"] = "none",
  cursor: string | null = null,
  kind: ConversationActivity["operation"]["kind"] =
    operation === "idle" ? null : "chat_turn",
): ConversationActivity => ({
  operation: {
    status: operation,
    kind,
    updated_at: operation === "idle" ? null : TODAY,
  },
  attention: { status: attention, cursor },
});

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function conversation(
  id: string,
  updatedAt = TODAY,
  lastMessagePreview: string | null = `Summary ${id}`,
  conversationActivity: ConversationActivity = activity(),
) {
  return {
    id,
    title: `Conversation ${id}`,
    title_source: "user_renamed",
    pinned: false,
    archived: false,
    deleted_at: null,
    created_at: updatedAt,
    updated_at: updatedAt,
    last_message_preview: lastMessagePreview,
    language: "en",
    activity: conversationActivity,
  };
}

function historyItem(item: ReturnType<typeof conversation>) {
  return {
    type: "chat",
    id: item.id,
    title: item.title,
    title_source: item.title_source,
    subtitle: item.last_message_preview,
    pinned: item.pinned,
    created_at: item.updated_at,
    conversation_id: item.id,
    activity: item.activity,
  };
}

async function installRecentsFixture(
  page: Page,
  options: FixtureOptions = {},
): Promise<FixtureState> {
  await page.clock.setFixedTime(new Date(TODAY));
  const language = options.language ?? "en";
  const firstPage =
    options.firstPage ??
    Array.from({ length: 6 }, (_, index) =>
      conversation(`today-${index + 1}`),
    );
  const secondPage =
    options.secondPage ??
    [
      conversation("older-1", "2026-06-18T16:00:00.000Z"),
      conversation("older-2", "2026-05-18T16:00:00.000Z"),
    ];
  const records = new Map(
    [...firstPage, ...secondPage].map((item) => [item.id, { ...item }]),
  );
  const state: FixtureState = {
    activityMutations: [],
    conversationRequests: [],
    historyRequests: [],
    messageRequests: [],
    mutations: [],
    streamRequests: [],
    unexpectedRequests: [],
  };

  await page.addInitScript(
    ({ fixtureLanguage, shortcutPlatform, useDarkMode }) => {
      window.localStorage.setItem("argus:sidebar_mode", "expanded");
      window.localStorage.setItem("i18nextLng", fixtureLanguage);
      if (useDarkMode) {
        window.localStorage.setItem("argus-theme", "dark");
      }
      if (shortcutPlatform) {
        Object.defineProperty(window.navigator, "userAgent", {
          configurable: true,
          value:
            shortcutPlatform === "mac"
              ? "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/138 Safari/537.36"
              : "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/138 Safari/537.36",
        });
      }
    },
    {
      fixtureLanguage: language,
      shortcutPlatform: options.shortcutPlatform,
      useDarkMode: options.darkMode ?? false,
    },
  );

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (url.pathname.endsWith("/api/v1/me")) {
      return json(route, {
        user: {
          id: "issue-245-user",
          email: "issue-245@example.com",
          username: "issue245",
          display_name: "Issue 245",
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

    if (
      url.pathname.endsWith("/api/v1/conversations") &&
      request.method() === "GET"
    ) {
      state.conversationRequests.push(`${url.pathname}${url.search}`);
      const isSecondPage = url.searchParams.get("cursor") === CURSOR;
      const firstPageAttempt = state.conversationRequests.filter(
        (path) => !path.includes("cursor="),
      ).length;
      const secondPageAttempt = state.conversationRequests.filter(
        (path) => path.includes(`cursor=${CURSOR}`),
      ).length;
      const pageIds = (isSecondPage ? secondPage : firstPage).map(
        (item) => item.id,
      );
      const items = pageIds
        .map((id) => records.get(id))
        .filter(
          (item): item is ConversationRecord =>
            Boolean(item && !item.archived && item.deleted_at === null),
        )
        .map((item) => ({ ...item }));
      if (
        !isSecondPage &&
        firstPageAttempt === options.firstPageDelayOnRequest &&
        options.firstPageDelayMs
      ) {
        await new Promise((resolve) =>
          setTimeout(resolve, options.firstPageDelayMs),
        );
      }
      if (isSecondPage && options.secondPageDelayMs) {
        await new Promise((resolve) =>
          setTimeout(resolve, options.secondPageDelayMs),
        );
      }
      if (
        isSecondPage &&
        secondPageAttempt <= (options.secondPageFailures ?? 0)
      ) {
        return json(route, { detail: "Controlled older-page failure" }, 503);
      }
      return json(route, {
        items,
        next_cursor:
          isSecondPage || secondPage.length === 0 ? null : CURSOR,
      });
    }

    // Temporary compatibility response: the assertions below prove that the
    // issue #245 implementation retires this mixed-history request.
    if (
      url.pathname.endsWith("/api/v1/history") &&
      request.method() === "GET"
    ) {
      state.historyRequests.push(`${url.pathname}${url.search}`);
      const isSecondPage = url.searchParams.get("cursor") === CURSOR;
      const items = (isSecondPage ? secondPage : firstPage)
        .map((item) => records.get(item.id))
        .filter(
          (item): item is ConversationRecord =>
            Boolean(item && !item.archived && item.deleted_at === null),
        )
        .map(historyItem);
      return json(route, {
        items,
        next_cursor:
          isSecondPage || secondPage.length === 0 ? null : CURSOR,
      });
    }

    const messageMatch = url.pathname.match(
      /\/api\/v1\/conversations\/([^/]+)\/messages$/,
    );
    if (messageMatch && request.method() === "GET") {
      const conversationId = decodeURIComponent(messageMatch[1]);
      state.messageRequests.push(conversationId);
      return json(route, {
        items: [
          {
            id: `${conversationId}-assistant`,
            conversation_id: conversationId,
            role: "assistant",
            content: `Transcript ${conversationId}`,
            created_at: TODAY,
            metadata: {},
          },
        ],
        next_cursor: null,
      });
    }

    const activityMatch = url.pathname.match(
      /\/api\/v1\/conversations\/([^/]+)\/activity$/,
    );
    if (activityMatch) {
      const conversationId = decodeURIComponent(activityMatch[1]);
      const item = records.get(conversationId);
      if (!item) {
        return json(route, { detail: "Conversation not found" }, 404);
      }
      if (request.method() === "GET") {
        return json(route, item.activity);
      }
      if (request.method() === "PATCH") {
        const body = request.postDataJSON() as ConversationActivityPatch;
        state.activityMutations.push({ conversationId, body });
        if (body.action === "mark_unread") {
          item.activity = activity(
            item.activity.operation.status,
            "manual_unread",
            item.activity.attention.cursor ?? null,
            item.activity.operation.kind ?? null,
          );
        } else if (
          body.through_attention_cursor === null ||
          body.through_attention_cursor === item.activity.attention.cursor
        ) {
          item.activity = activity(
            item.activity.operation.status,
            "none",
            null,
            item.activity.operation.kind ?? null,
          );
        }
        return json(route, item.activity);
      }
    }

    const mutationMatch = url.pathname.match(
      /\/api\/v1\/conversations\/([^/]+)$/,
    );
    if (
      mutationMatch &&
      (request.method() === "PATCH" || request.method() === "DELETE")
    ) {
      const conversationId = decodeURIComponent(mutationMatch[1]);
      const item = records.get(conversationId);
      if (!item) {
        return json(route, { detail: "Conversation not found" }, 404);
      }
      if (request.method() === "PATCH") {
        const body = request.postDataJSON() as Record<string, unknown>;
        Object.assign(item, body, { updated_at: TODAY });
        state.mutations.push({
          method: "PATCH",
          conversationId,
          body,
        });
        return json(route, { conversation: item });
      }
      item.deleted_at = TODAY;
      state.mutations.push({ method: "DELETE", conversationId });
      return json(route, { success: true });
    }

    if (
      url.pathname.endsWith("/api/v1/chat/stream") &&
      request.method() === "POST"
    ) {
      const body = request.postDataJSON() as Record<string, unknown>;
      state.streamRequests.push(body);
      const conversationId = String(body.conversation_id ?? "today-1");
      const item = records.get(conversationId);
      if (item) {
        item.activity = activity("running", "none", null, "chat_turn");
      }
      if (options.streamDelayMs) {
        await new Promise((resolve) =>
          setTimeout(resolve, options.streamDelayMs),
        );
      }
      if (item) {
        item.activity = activity(
          "idle",
          "new_activity",
          `chat_turn:${conversationId}-settled`,
        );
      }
      return route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: [
          'data: {"type":"stage_start","stage":"clarify"}',
          "",
          'data: {"type":"token","content":"Attention settled."}',
          "",
          `data: ${JSON.stringify({
            type: "final",
            payload: {
              stage_outcome: "ready_to_respond",
              assistant_response: "Attention settled.",
              message_id: `${conversationId}-settled-assistant`,
              conversation_id: conversationId,
            },
          })}`,
          "",
          "data: [DONE]",
          "",
        ].join("\n"),
      });
    }

    state.unexpectedRequests.push(
      `${request.method()} ${url.pathname}${url.search}`,
    );
    return json(route, { detail: "Unexpected issue #245 fixture request" }, 501);
  });

  return state;
}

function recentRow(page: Page, conversationId: string) {
  return page.locator(
    `[role="button"][data-conversation-id="${conversationId}"]`,
  );
}

function recentRowsWithPrefix(page: Page, prefix: string) {
  return page.locator(
    `[role="button"][data-conversation-id^="${prefix}"]`,
  );
}

async function captureEvidence(page: Page, filename: string) {
  if (!EVIDENCE_DIR) return;
  await page.screenshot({
    path: `${EVIDENCE_DIR}/${filename}`,
    fullPage: true,
  });
}

async function requiredBoundingBox(locator: Locator) {
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  return box!;
}

async function holdQuickJumpModifier(
  page: Page,
  platform: ShortcutPlatform,
) {
  if (platform === "mac") {
    await page.keyboard.down("Meta");
    return;
  }
  await page.keyboard.down("Control");
  await page.keyboard.down("Shift");
}

async function releaseQuickJumpModifier(
  page: Page,
  platform: ShortcutPlatform,
) {
  if (platform === "mac") {
    await page.keyboard.up("Meta");
    return;
  }
  await page.keyboard.up("Shift");
  await page.keyboard.up("Control");
}

async function pressQuickJumpNumber(
  page: Page,
  platform: ShortcutPlatform,
  number: number,
) {
  await holdQuickJumpModifier(page, platform);
  if (platform === "mac") await page.keyboard.down("Alt");
  await page.keyboard.press(String(number));
  if (platform === "mac") await page.keyboard.up("Alt");
  await releaseQuickJumpModifier(page, platform);
}

function expectedQuickJumpHint(
  platform: ShortcutPlatform,
  number: number,
) {
  return platform === "mac" ? `⌘⌥${number}` : `Ctrl+Shift+${number}`;
}

async function openRecents(
  page: Page,
  language: "en" | "es-419" = "en",
) {
  await page
    .getByRole("button", {
      name: language === "es-419" ? "Recientes" : "Recents",
    })
    .click();
}

test("Recents uses bounded chat pages and loads older chats only on request", async ({
  page,
}) => {
  const fixture = await installRecentsFixture(page);

  await page.goto("/chat");
  await page.getByRole("button", { name: "Recents" }).click();
  await expect(page.getByText("Today", { exact: true })).toBeVisible();

  await expect
    .poll(
      () =>
        fixture.conversationRequests.filter((path) => !path.includes("cursor="))
          .length,
    )
    .toBeGreaterThanOrEqual(1);
  const bootstrapRequestCount = fixture.conversationRequests.length;
  expect(
    fixture.conversationRequests.every(
      (path) =>
        path === "/api/v1/conversations?limit=30&archived=false&deleted=false",
    ),
  ).toBe(true);
  expect(fixture.historyRequests).toEqual([]);

  const todayRows = recentRowsWithPrefix(page, "today-");
  await expect(todayRows).toHaveCount(5);
  await expect(
    page.getByRole("button", { name: "Show more in Today" }),
  ).toBeVisible();

  await page.locator("aside").hover();
  await page.mouse.wheel(0, 2_000);
  await page.waitForTimeout(250);
  expect(fixture.conversationRequests).toHaveLength(bootstrapRequestCount);

  await page.getByRole("button", { name: "Load older" }).click();
  await expect
    .poll(
      () =>
        fixture.conversationRequests.filter((path) =>
          path.includes(`cursor=${CURSOR}`),
        ).length,
    )
    .toBe(1);
  await expect(
    page.locator('[data-conversation-id="older-1"]'),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "No older chats" }),
  ).toBeDisabled();
  await captureEvidence(page, "01-en-desktop-page-two-exhausted.png");
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("an empty visible page keeps explicit access to an older chat page", async ({
  page,
}) => {
  const fixture = await installRecentsFixture(page, {
    firstPage: [conversation("blank-chat", TODAY, null)],
    secondPage: [
      conversation("older-visible", "2026-05-18T16:00:00.000Z"),
    ],
  });

  await page.goto("/chat");
  await openRecents(page);
  await expect(
    page.getByText("No recent chats yet.", { exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Load older" }).click();
  await expect(recentRow(page, "older-visible")).toBeVisible();
  await expect(recentRow(page, "blank-chat")).toHaveCount(0);
  expect(
    fixture.conversationRequests.filter((path) => path.includes(`cursor=${CURSOR}`)),
  ).toHaveLength(1);
  expect(fixture.historyRequests).toEqual([]);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("each time group discloses independently and keeps the selected chat visible", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  const pinned = Array.from({ length: 6 }, (_, index) => ({
    ...conversation(`pinned-${index + 1}`, "2026-05-18T16:00:00.000Z"),
    pinned: true,
  }));
  const today = Array.from({ length: 7 }, (_, index) =>
    conversation(`today-${index + 1}`),
  );
  const last7Days = Array.from({ length: 6 }, (_, index) =>
    conversation(`week-${index + 1}`, "2026-07-24T16:00:00.000Z"),
  );
  const fixture = await installRecentsFixture(page, {
    firstPage: [...pinned, ...today, ...last7Days],
    secondPage: [],
  });

  await page.goto("/chat?conversation=today-7");
  await openRecents(page);
  await expect(recentRow(page, "today-7")).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(page.getByText("Transcript today-7")).toBeVisible();

  await expect(
    recentRowsWithPrefix(page, "pinned-"),
  ).toHaveCount(6);
  await expect(
    page.getByRole("button", { name: "Show more in Pinned" }),
  ).toHaveCount(0);
  await expect(
    recentRowsWithPrefix(page, "today-"),
  ).toHaveCount(5);
  await expect(recentRow(page, "today-5")).toHaveCount(0);
  await expect(recentRow(page, "today-7")).toBeVisible();
  await expect(
    recentRowsWithPrefix(page, "week-"),
  ).toHaveCount(5);

  const showMoreToday = page.getByRole("button", {
    name: "Show more in Today",
  });
  await expect(showMoreToday).toHaveAttribute("aria-expanded", "false");
  const todayItemsId = await showMoreToday.getAttribute("aria-controls");
  expect(todayItemsId).toBe("recents-today-items");
  await showMoreToday.focus();
  await showMoreToday.press("Enter");
  const showLessToday = page.getByRole("button", {
    name: "Show less in Today",
  });
  await expect(showLessToday).toBeFocused();
  await expect(showLessToday).toHaveAttribute("aria-expanded", "true");
  await expect(
    recentRowsWithPrefix(page, "today-"),
  ).toHaveCount(7);
  await expect(
    recentRowsWithPrefix(page, "week-"),
  ).toHaveCount(5);

  const showMoreWeek = page.getByRole("button", {
    name: "Show more in Last 7 days",
  });
  await showMoreWeek.focus();
  await showMoreWeek.press(" ");
  await expect(
    page.getByRole("button", { name: "Show less in Last 7 days" }),
  ).toHaveAttribute("aria-expanded", "true");
  await expect(
    recentRowsWithPrefix(page, "week-"),
  ).toHaveCount(6);
  await expect(
    recentRowsWithPrefix(page, "today-"),
  ).toHaveCount(7);

  await showLessToday.click();
  await expect(
    recentRowsWithPrefix(page, "today-"),
  ).toHaveCount(5);
  await expect(recentRow(page, "today-7")).toBeVisible();
  await expect(
    recentRowsWithPrefix(page, "week-"),
  ).toHaveCount(6);

  await page.reload();
  await openRecents(page);
  await expect(recentRowsWithPrefix(page, "today-")).toHaveCount(5);
  await expect(recentRow(page, "today-7")).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(
    page.getByRole("button", { name: "Show more in Today" }),
  ).toHaveAttribute("aria-expanded", "false");
  await expect(page.getByText("Transcript today-7")).toBeVisible();
  await captureEvidence(page, "02-en-desktop-selected-after-reload.png");
  expect(fixture.historyRequests).toEqual([]);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("a rapid Load older double-click admits one cursor request and exhausts it", async ({
  page,
}) => {
  const firstPage = Array.from({ length: 6 }, (_, index) =>
    conversation(`today-${index + 1}`),
  );
  const fixture = await installRecentsFixture(page, {
    firstPage,
    secondPage: [
      firstPage[0],
      conversation("older-1", "2026-06-18T16:00:00.000Z"),
      conversation("older-2", "2026-05-18T16:00:00.000Z"),
    ],
    secondPageDelayMs: 300,
  });

  await page.goto("/chat");
  await openRecents(page);
  const loadOlder = page.getByRole("button", { name: "Load older" });
  await expect(loadOlder).toBeVisible();
  await loadOlder.evaluate((button: HTMLButtonElement) => {
    button.click();
    button.click();
  });

  await expect
    .poll(
      () =>
        fixture.conversationRequests.filter((path) =>
          path.includes(`cursor=${CURSOR}`),
        ).length,
    )
    .toBe(1);
  await expect(
    page.getByRole("button", { name: "Loading older chats…" }),
  ).toHaveAttribute("aria-busy", "true");
  await expect(recentRow(page, "older-1")).toBeVisible();
  await expect(page.getByText("Earlier", { exact: true })).toBeVisible();
  await expect(recentRow(page, "today-1")).toHaveCount(1);
  await expect(
    page.getByRole("button", { name: "No older chats" }),
  ).toBeDisabled();

  const olderRequests = fixture.conversationRequests.filter((path) =>
    path.includes(`cursor=${CURSOR}`),
  );
  expect(olderRequests).toHaveLength(1);
  expect(olderRequests[0]).toContain("archived=false");
  expect(olderRequests[0]).toContain("deleted=false");
  expect(fixture.historyRequests).toEqual([]);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("a failed older-page request reports the error and remains retryable", async ({
  page,
}) => {
  const fixture = await installRecentsFixture(page, {
    secondPageFailures: 1,
  });

  await page.goto("/chat");
  await openRecents(page);
  await page.getByRole("button", { name: "Load older" }).click();
  await expect(
    page.getByText("Couldn’t load older chats. Try again.", {
      exact: true,
    }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Load older" }),
  ).toBeEnabled();

  await page.getByRole("button", { name: "Load older" }).click();
  await expect(recentRow(page, "older-1")).toBeVisible();
  await expect(
    page.getByText("Couldn’t load older chats. Try again.", {
      exact: true,
    }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("button", { name: "No older chats" }),
  ).toBeDisabled();
  expect(
    fixture.conversationRequests.filter((path) => path.includes(`cursor=${CURSOR}`)),
  ).toHaveLength(2);
  expect(fixture.historyRequests).toEqual([]);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("a completed mutation queues a fresh first-page request behind an in-flight refresh", async ({
  page,
}) => {
  const fixture = await installRecentsFixture(page, {
    firstPage: [conversation("today-1"), conversation("today-2")],
    firstPageDelayMs: 1_000,
    firstPageDelayOnRequest: 2,
    secondPage: [],
  });

  await page.goto("/chat?conversation=today-1");
  await openRecents(page);
  const row = recentRow(page, "today-1");
  await expect(row).toBeVisible();
  await expect
    .poll(
      () =>
        fixture.conversationRequests.filter((path) => !path.includes("cursor="))
          .length,
    )
    .toBeGreaterThanOrEqual(2);
  const inFlightRefreshCount = fixture.conversationRequests.length;

  await row.getByRole("button", { name: "More" }).click();
  await page.getByRole("menuitem", { name: "Pin" }).click();
  expect(fixture.conversationRequests).toHaveLength(inFlightRefreshCount);

  await row.getByRole("button", { name: "More" }).click();
  await page.getByRole("menuitem", { name: "Rename" }).click();
  const renameInput = row.locator("input");
  await renameInput.fill("Renamed during refresh");
  await renameInput.press("Enter");

  await expect(
    row.getByText("Renamed during refresh", { exact: true }),
  ).toBeVisible();
  await expect
    .poll(() => fixture.conversationRequests.length)
    .toBe(inFlightRefreshCount + 1);
  expect(fixture.mutations).toEqual([
    {
      method: "PATCH",
      conversationId: "today-1",
      body: { pinned: true },
    },
    {
      method: "PATCH",
      conversationId: "today-1",
      body: { title: "Renamed during refresh" },
    },
  ]);
  expect(fixture.historyRequests).toEqual([]);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("rename, pin, unpin, selection, and delete keep their conversation identity", async ({
  page,
}) => {
  const fixture = await installRecentsFixture(page, {
    firstPage: [conversation("today-1"), conversation("today-2")],
    secondPage: [],
  });

  await page.goto("/chat?conversation=today-1");
  await openRecents(page);
  await expect(recentRow(page, "today-1")).toHaveAttribute(
    "aria-current",
    "page",
  );

  await recentRow(page, "today-1")
    .getByRole("button", { name: "More" })
    .click();
  await page.getByRole("menuitem", { name: "Rename" }).click();
  const renameInput = recentRow(page, "today-1").locator("input");
  await renameInput.fill("Renamed conversation");
  await renameInput.press("Enter");
  await expect(
    recentRow(page, "today-1").getByText("Renamed conversation"),
  ).toBeVisible();

  await recentRow(page, "today-1")
    .getByRole("button", { name: "More" })
    .click();
  await page.getByRole("menuitem", { name: "Pin" }).click();
  await expect(page.getByText("Pinned", { exact: true })).toBeVisible();
  await expect(recentRow(page, "today-1")).toHaveAttribute(
    "aria-current",
    "page",
  );

  await recentRow(page, "today-1")
    .getByRole("button", { name: "More" })
    .click();
  await page.getByRole("menuitem", { name: "Unpin" }).click();
  await expect(page.getByText("Pinned", { exact: true })).toHaveCount(0);

  const secondRow = recentRow(page, "today-2");
  await secondRow.focus();
  await secondRow.press(" ");
  await expect(page).toHaveURL(/conversation=today-2(?:&|$)/);
  await expect(secondRow).toBeFocused();
  await expect(secondRow).toHaveAttribute("aria-current", "page");
  await expect(page.getByText("Transcript today-2")).toBeVisible();

  await secondRow.getByRole("button", { name: "More" }).click();
  await page.getByRole("menuitem", { name: "Delete" }).click();
  await page
    .getByRole("button", { name: "Delete conversation" })
    .click();
  await expect(recentRow(page, "today-2")).toHaveCount(0);
  await captureEvidence(page, "03-en-desktop-mutations.png");

  expect(fixture.mutations).toEqual([
    {
      method: "PATCH",
      conversationId: "today-1",
      body: { title: "Renamed conversation" },
    },
    {
      method: "PATCH",
      conversationId: "today-1",
      body: { pinned: true },
    },
    {
      method: "PATCH",
      conversationId: "today-1",
      body: { pinned: false },
    },
    { method: "DELETE", conversationId: "today-2" },
  ]);
  expect(fixture.messageRequests).toEqual(["today-1", "today-2"]);
  expect(fixture.historyRequests).toEqual([]);
  expect(fixture.unexpectedRequests).toEqual([]);
});

for (const scenario of [
  {
    language: "en" as const,
    platform: "mac" as const,
    attentionLabel: "New activity",
  },
  {
    language: "es-419" as const,
    platform: "other" as const,
    attentionLabel: "Actividad nueva",
  },
]) {
  test(`${scenario.language} ${scenario.platform} quick-jump keeps attention and row alignment until open`, async ({
    page,
  }) => {
    const fixture = await installRecentsFixture(page, {
      darkMode: true,
      firstPage: [conversation("today-1"), conversation("today-2")],
      language: scenario.language,
      secondPage: [],
      shortcutPlatform: scenario.platform,
      streamDelayMs: 350,
    });

    await page.goto("/chat?conversation=today-1");
    await openRecents(page, scenario.language);
    await page.getByTestId("chat-input").fill("Settle this turn later");
    await page.getByTestId("chat-send").click();
    await recentRow(page, "today-2").click();
    await expect(page).toHaveURL(/conversation=today-2(?:&|$)/);

    const row = recentRow(page, "today-1");
    const title = row.getByText("Conversation today-1", { exact: true });
    const subtitle = row.getByText("Summary today-1", { exact: true });
    await expect(
      row.locator('[data-conversation-activity="new_activity"]'),
    ).toBeVisible();
    await expect(row).toHaveAccessibleName(
      new RegExp(`Conversation today-1\\. ${scenario.attentionLabel}\\.`),
    );
    const rowBefore = await requiredBoundingBox(row);
    const titleBefore = await requiredBoundingBox(title);
    const subtitleBefore = await requiredBoundingBox(subtitle);
    if (scenario.language === "en") {
      await captureEvidence(page, "01-en-mac-recents-attention-rest.png");
    }

    await holdQuickJumpModifier(page, scenario.platform);
    const hint = row.locator('[data-quick-jump-hint="1"]');
    await expect(hint).toBeVisible();
    await expect(hint).toContainText(
      expectedQuickJumpHint(scenario.platform, 1),
    );
    await expect(
      row.locator('[data-conversation-activity="new_activity"]'),
    ).toBeVisible();
    await expect(row).toHaveAccessibleName(
      new RegExp(`Conversation today-1\\. ${scenario.attentionLabel}\\.`),
    );

    const rowAfter = await requiredBoundingBox(row);
    const titleAfter = await requiredBoundingBox(title);
    const subtitleAfter = await requiredBoundingBox(subtitle);
    const attentionDot = await requiredBoundingBox(
      row.locator('[data-conversation-activity="new_activity"]'),
    );
    const hintBox = await requiredBoundingBox(hint);
    expect(rowAfter.height).toBeCloseTo(rowBefore.height, 1);
    expect(titleAfter.x).toBeCloseTo(titleBefore.x, 1);
    expect(subtitleAfter.x).toBeCloseTo(subtitleBefore.x, 1);
    expect(attentionDot.x + attentionDot.width).toBeLessThan(hintBox.x);
    expect(hintBox.x + hintBox.width).toBeLessThanOrEqual(
      rowAfter.x + rowAfter.width,
    );
    await captureEvidence(
      page,
      scenario.language === "en"
        ? "02-en-mac-recents-attention-shortcut.png"
        : "05-es-other-recents-attention-shortcut.png",
    );

    await releaseQuickJumpModifier(page, scenario.platform);
    await expect(hint).toHaveCount(0);
    await expect(
      row.locator('[data-conversation-activity="new_activity"]'),
    ).toBeVisible();

    await pressQuickJumpNumber(page, scenario.platform, 1);
    await expect(row).toHaveAttribute("aria-current", "page");
    await expect
      .poll(() => fixture.activityMutations)
      .toContainEqual({
        conversationId: "today-1",
        body: {
          action: "mark_read",
          through_attention_cursor: "chat_turn:today-1-settled",
        },
      });
    await expect(row.locator("[data-conversation-activity]")).toHaveCount(0);
    expect(fixture.streamRequests).toHaveLength(1);
    expect(fixture.historyRequests).toEqual([]);
    expect(fixture.unexpectedRequests).toEqual([]);
  });
}

test("an open or focused Recents action keeps precedence over quick-jump", async ({
  page,
}) => {
  const fixture = await installRecentsFixture(page, {
    darkMode: true,
    firstPage: [conversation("today-1"), conversation("today-2")],
    secondPage: [],
    shortcutPlatform: "mac",
  });

  await page.goto("/chat?conversation=today-2");
  await openRecents(page);
  const row = recentRow(page, "today-1");
  const more = row.getByRole("button", { name: "More" });
  await row.hover();
  await more.click();
  await expect(page.getByRole("menu")).toBeVisible();

  await holdQuickJumpModifier(page, "mac");
  await expect(more).toBeVisible();
  await expect(more).toHaveAttribute("aria-expanded", "true");
  await expect(row.locator('[data-quick-jump-hint="1"]')).toHaveCount(0);
  await expect(page.getByRole("menu")).toBeVisible();
  await releaseQuickJumpModifier(page, "mac");

  await page.keyboard.press("Escape");
  await expect(page.getByRole("menu")).toHaveCount(0);
  await more.focus();
  await holdQuickJumpModifier(page, "mac");
  await expect(more).toBeFocused();
  await expect(row.locator('[data-quick-jump-hint="1"]')).toHaveCount(0);
  await row.focus();
  await expect(row.locator('[data-quick-jump-hint="1"]')).toBeVisible();
  await releaseQuickJumpModifier(page, "mac");
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("nested Recents menu keys open the menu while row keys still navigate", async ({
  page,
}) => {
  const fixture = await installRecentsFixture(page, {
    firstPage: [conversation("today-1"), conversation("today-2")],
    secondPage: [],
  });

  await page.goto("/chat?conversation=today-2");
  await openRecents(page);
  const firstRow = recentRow(page, "today-1");
  const firstMore = firstRow.getByRole("button", { name: "More" });

  await firstMore.focus();
  await firstMore.press("Enter");
  await expect(page.getByRole("menu")).toBeVisible();
  await expect(page).toHaveURL(/conversation=today-2(?:&|$)/);
  await page.keyboard.press("Escape");

  await firstMore.press(" ");
  await expect(page.getByRole("menu")).toBeVisible();
  await expect(page).toHaveURL(/conversation=today-2(?:&|$)/);
  await page.keyboard.press("Escape");

  await firstRow.focus();
  await firstRow.press("Enter");
  await expect(page).toHaveURL(/conversation=today-1(?:&|$)/);

  const secondRow = recentRow(page, "today-2");
  await secondRow.focus();
  await secondRow.press(" ");
  await expect(page).toHaveURL(/conversation=today-2(?:&|$)/);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("Recents Quick Peek right-aligns exact-chord hints without moving titles", async ({
  page,
}) => {
  const fixture = await installRecentsFixture(page, {
    darkMode: true,
    firstPage: [conversation("today-1"), conversation("today-2")],
    secondPage: [],
    shortcutPlatform: "mac",
  });

  await page.goto("/chat");
  await expect
    .poll(() => fixture.conversationRequests.length)
    .toBeGreaterThanOrEqual(1);
  await expect(page.getByRole("button", { name: "Recents" })).toBeVisible();
  await page.keyboard.press("Meta+Shift+Comma");
  const dialog = page.getByRole("dialog", { name: "Recents" });
  const row = dialog.getByRole("button", { name: /Conversation today-1/ });
  const title = row.getByText("Conversation today-1", { exact: true });
  const rowBefore = await requiredBoundingBox(row);
  const titleBefore = await requiredBoundingBox(title);

  await holdQuickJumpModifier(page, "mac");
  const hint = row.locator('[data-quick-jump-hint="1"]');
  await expect(hint).toBeVisible();
  await expect(hint).toContainText("⌘⌥1");
  const rowAfter = await requiredBoundingBox(row);
  const titleAfter = await requiredBoundingBox(title);
  const hintBox = await requiredBoundingBox(hint);
  expect(rowAfter.height).toBeCloseTo(rowBefore.height, 1);
  expect(titleAfter.x).toBeCloseTo(titleBefore.x, 1);
  expect(hintBox.x).toBeGreaterThan(titleAfter.x);
  await captureEvidence(page, "03-en-mac-recents-quick-peek.png");
  await releaseQuickJumpModifier(page, "mac");

  await pressQuickJumpNumber(page, "mac", 1);
  await expect(dialog).toHaveCount(0);
  await expect(page).toHaveURL(/conversation=today-1(?:&|$)/);
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("Settings keeps the exact-chord keycap convention used by Recents", async ({
  page,
}) => {
  const fixture = await installRecentsFixture(page, {
    darkMode: true,
    firstPage: [conversation("today-1"), conversation("today-2")],
    secondPage: [],
    shortcutPlatform: "mac",
  });

  await page.goto("/chat");
  await expect
    .poll(() => fixture.conversationRequests.length)
    .toBeGreaterThanOrEqual(1);
  await page.getByRole("button", { name: "Settings" }).click();
  await page.getByRole("button", { name: /Preferences/ }).click();
  const preferences = page.locator('[aria-label="Preferences"]');
  await expect(preferences).toBeVisible();
  const appearance = preferences.getByRole("button", { name: /Appearance/ });

  await holdQuickJumpModifier(page, "mac");
  await page.keyboard.down("Alt");
  await expect(appearance).toContainText("⌘⌥1");
  await captureEvidence(page, "04-en-mac-settings-comparison.png");
  await page.keyboard.up("Alt");
  await releaseQuickJumpModifier(page, "mac");
  expect(fixture.unexpectedRequests).toEqual([]);
});

test("Spanish mobile Recents exposes localized disclosure labels and bounded layout", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const fixture = await installRecentsFixture(page, {
    language: "es-419",
    firstPage: Array.from({ length: 6 }, (_, index) =>
      conversation(`today-${index + 1}`),
    ),
    secondPage: [
      conversation("older-mobile", "2026-05-18T16:00:00.000Z"),
    ],
  });

  await page.goto("/chat?conversation=today-6");
  await openRecents(page, "es-419");
  await expect(page.locator("html")).toHaveAttribute("lang", "es-419");
  await expect(
    recentRowsWithPrefix(page, "today-"),
  ).toHaveCount(5);
  await expect(recentRow(page, "today-6")).toBeVisible();

  const showMore = page.getByRole("button", {
    name: "Mostrar más en Hoy",
  });
  await expect(showMore).toHaveAttribute("aria-expanded", "false");
  const showMoreBox = await showMore.boundingBox();
  expect(showMoreBox?.height ?? 0).toBeGreaterThanOrEqual(44);
  await showMore.click();
  await expect(
    page.getByRole("button", { name: "Mostrar menos en Hoy" }),
  ).toHaveAttribute("aria-expanded", "true");

  await page
    .getByRole("button", { name: "Cargar chats anteriores" })
    .click();
  await expect(recentRow(page, "older-mobile")).toBeVisible();
  await expect(page.getByText("Anteriores", { exact: true })).toBeVisible();
  await expect(
    page.getByRole("button", { name: "No hay chats anteriores" }),
  ).toBeDisabled();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
  const sidebarBox = await page.locator("aside").boundingBox();
  expect(sidebarBox?.width ?? 0).toBeLessThanOrEqual(390);
  await captureEvidence(page, "04-es-mobile-expanded.png");
  expect(fixture.historyRequests).toEqual([]);
  expect(fixture.unexpectedRequests).toEqual([]);
});
