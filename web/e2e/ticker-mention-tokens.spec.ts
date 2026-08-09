import { mkdirSync, writeFileSync } from "node:fs";
import { expect, test, type Locator, type Page, type Route } from "@playwright/test";

const CONVERSATION_ID = "ticker-mention-conversation";
const NOW = "2026-08-09T12:00:00.000Z";
const EVIDENCE_DIR = process.env.TICKER_MENTION_EVIDENCE_DIR;
const MESSAGE = "Compare AAPL to AAPL when RSI falls";

type JsonRecord = Record<string, unknown>;

type ApiMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  metadata: JsonRecord;
};

type StreamRequest = {
  conversation_id: string;
  message: string;
  language: string;
  mentions?: Array<{
    id: string;
    type: "asset" | "indicator";
    insert_text: string;
    message_range?: { start: number; end: number };
  }>;
};

type Fixture = {
  streamRequests: StreamRequest[];
  unexpectedRequests: string[];
  showResult: () => void;
};

const asset = {
  id: "asset:equity:AAPL",
  type: "asset",
  label: "AAPL · Apple Inc.",
  symbol: "AAPL",
  asset_class: "equity",
  description: "Apple Inc.",
  insert_text: "AAPL",
  provider: "alpaca",
  support_status: "supported",
};

const indicator = {
  id: "indicator:rsi",
  type: "indicator",
  label: "RSI",
  symbol: "rsi",
  description: "Relative Strength Index",
  insert_text: "RSI",
  provider: "pandas-ta-classic",
  support_status: "supported",
};

const confirmation = {
  confirmation_id: "ticker-mention-confirmation",
  confirmation_state: "active",
  title: "AAPL relative-strength setup",
  summary: "Buy AAPL when RSI reaches the selected threshold.",
  status: "ready_to_run",
  statusLabel: "Ready to run",
  strategy_type: "indicator_strategy",
  asset_class: "equity",
  date_range: {
    start: "2024-01-01",
    end: "2024-12-31",
    display: "January 1, 2024 to December 31, 2024",
  },
  rows: [
    { key: "assets", label: "Assets", value: "AAPL" },
    { key: "strategy", label: "Strategy", value: "RSI strategy" },
    { key: "benchmark", label: "Benchmark", value: "SPY" },
  ],
  display_facts: { benchmark_symbol: "SPY" },
  assumptions: ["Long-only", "Benchmark: SPY"],
  actions: [],
};

const result = {
  title: "AAPL relative-strength result",
  symbols: ["AAPL"],
  strategy_label: "RSI strategy",
  asset_class: "equity",
  date_range: {
    start: "2024-01-01",
    end: "2024-12-31",
    display: "January 1, 2024 to December 31, 2024",
  },
  status_label: "Simulation Complete",
  rows: [
    { key: "ending_value", label: "Ending value", value: "$11,420" },
    { key: "total_return_pct", label: "Total return", value: "14.2%" },
    { key: "benchmark_delta_pct", label: "Vs benchmark", value: "2.3 pts" },
    { key: "max_drawdown_pct", label: "Max drawdown", value: "-8.4%" },
  ],
  benchmark_note: "AAPL finished 2.3 percentage points ahead of SPY.",
  assumptions: ["Long-only", "Benchmark: SPY"],
  actions: [],
  chart: null,
};

function json(route: Route, body: unknown, status = 200) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function sse(frames: Array<JsonRecord | "[DONE]">) {
  return frames
    .map((frame) =>
      frame === "[DONE]"
        ? "data: [DONE]\\n\\n"
        : `data: ${JSON.stringify(frame)}\\n\\n`,
    )
    .join("");
}

function fulfillSse(route: Route, frames: Array<JsonRecord | "[DONE]">) {
  return route.fulfill({
    status: 200,
    contentType: "text/event-stream",
    headers: { "x-request-id": "ticker-mention-test-request" },
    body: sse(frames),
  });
}

function conversation(language: "en" | "es-419") {
  return {
    id: CONVERSATION_ID,
    title: "Ticker mention tokens",
    title_source: "ai_generated",
    pinned: false,
    archived: false,
    language,
    created_at: NOW,
    updated_at: NOW,
  };
}

function userMessage(metadata: JsonRecord): ApiMessage {
  return {
    id: "ticker-mention-user-message",
    conversation_id: CONVERSATION_ID,
    role: "user",
    content: MESSAGE,
    created_at: NOW,
    metadata,
  };
}

async function capture(
  frame: Locator,
  filename: string,
  options: { topInset?: number } = {},
) {
  if (!EVIDENCE_DIR) return;
  mkdirSync(EVIDENCE_DIR, { recursive: true });
  await frame.scrollIntoViewIfNeeded();
  if (options.topInset) {
    await frame.evaluate((element, topInset) => {
      const transcript = element.closest(
        '[data-testid="conversation-transcript-region"]',
      );
      if (!transcript) return;

      const elementTop =
        element.getBoundingClientRect().top -
        transcript.getBoundingClientRect().top;
      const offset = Math.min(
        Math.max(0, topInset - elementTop),
        transcript.scrollTop,
      );
      transcript.scrollTop -= offset;
    }, options.topInset);
    await frame.evaluate(
      () => new Promise<void>((resolve) => requestAnimationFrame(() => resolve())),
    );
  }
  await frame.screenshot({
    path: `${EVIDENCE_DIR}/${filename}`,
  });
  writeFileSync(
    `${EVIDENCE_DIR}/${filename.replace(/\.png$/, ".txt")}`,
    `${await frame.innerText()}\n`,
    "utf8",
  );
}

async function installFixture(
  page: Page,
  language: "en" | "es-419",
): Promise<Fixture> {
  const messages: ApiMessage[] = [
    {
      id: "ticker-mention-seed-message",
      conversation_id: CONVERSATION_ID,
      role: "assistant",
      content: "Select AAPL and RSI for this mock setup.",
      created_at: NOW,
      metadata: {},
    },
  ];
  const streamRequests: StreamRequest[] = [];
  const unexpectedRequests: string[] = [];

  await page.addInitScript((locale) => {
    window.localStorage.setItem("i18nextLng", locale);
  }, language);

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (path === "/api/v1/me") {
      return json(route, {
        user: {
          id: "ticker-mention-user",
          email: "ticker-mention@example.com",
          username: "ticker-mention-user",
          display_name: "Ticker mention user",
          language,
          locale: language === "en" ? "en-US" : "es-419",
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
    if (path === `/api/v1/conversations/${CONVERSATION_ID}/messages`) {
      return json(route, { items: messages, next_cursor: null });
    }
    if (path === `/api/v1/conversations/${CONVERSATION_ID}/activity`) {
      return json(route, {
        operation: { status: "idle", kind: null, updated_at: null },
        attention: { status: "none", cursor: null },
      });
    }
    if (path === "/api/v1/conversations") {
      return json(route, {
        ...(request.method() === "POST"
          ? { conversation: conversation(language) }
          : { items: [conversation(language)], next_cursor: null }),
      });
    }
    if (path === "/api/v1/history") {
      return json(route, {
        items: [
          {
            type: "chat",
            id: CONVERSATION_ID,
            conversation_id: CONVERSATION_ID,
            title: "Ticker mention tokens",
            subtitle: "Ticker mention tokens",
            pinned: false,
            created_at: NOW,
          },
        ],
        next_cursor: null,
      });
    }
    if (path === "/api/v1/search") {
      return json(route, { items: [], next_cursor: null, ledger_groups: [] });
    }
    if (path === "/api/v1/chat/starter-prompts") {
      return json(route, { prompts: [] });
    }
    if (path === "/api/v1/memory/availability") {
      return json(route, { available: false, reason: "disabled" });
    }
    if (path === "/api/v1/discovery/assets") {
      return json(route, {
        items: url.searchParams.get("q")?.toLowerCase().includes("aapl")
          ? [asset]
          : [],
      });
    }
    if (path === "/api/v1/discovery/indicators") {
      return json(route, {
        items: url.searchParams.get("q")?.toLowerCase().includes("rsi")
          ? [indicator]
          : [],
      });
    }
    if (path === "/api/v1/chat/stream") {
      const body = request.postDataJSON() as StreamRequest;
      streamRequests.push(body);
      messages.splice(
        0,
        messages.length,
        userMessage({ mentions: body.mentions ?? [] }),
        {
          id: "ticker-mention-assistant-message",
          conversation_id: CONVERSATION_ID,
          role: "assistant",
          content: "I prepared the selected AAPL setup.",
          created_at: NOW,
          metadata: { confirmation_card: confirmation },
        },
      );
      return fulfillSse(route, [
        { type: "stage_start", stage: "confirm" },
        {
          type: "final",
          payload: {
            stage_outcome: "ready_for_confirmation",
            confirmation,
            message_id: "ticker-mention-assistant-message",
          },
        },
        "[DONE]",
      ]);
    }

    unexpectedRequests.push(`${request.method()} ${path}`);
    return json(route, { detail: "Unexpected fixture request" }, 501);
  });

  return {
    streamRequests,
    unexpectedRequests,
    showResult: () => {
      messages.splice(
        0,
        messages.length,
        userMessage({ mentions: streamRequests[0]?.mentions ?? [] }),
        {
          id: "ticker-mention-result-message",
          conversation_id: CONVERSATION_ID,
          role: "assistant",
          content: "AAPL finished ahead of the benchmark in this mock result.",
          created_at: NOW,
          metadata: {
            latest_run_id: "ticker-mention-result-run",
            result_conversation_id: CONVERSATION_ID,
            result_run_id: "ticker-mention-result-run",
            result_card: result,
          },
        },
      );
    },
  };
}

async function selectAssetAndIndicator(page: Page) {
  const composer = page.getByTestId("chat-input");
  await composer.fill("Compare @aapl");
  await expect(
    page.locator("#chat-discovery-option-asset-equity-AAPL"),
  ).toBeVisible();
  await page.locator("#chat-discovery-option-asset-equity-AAPL").click();
  await composer.pressSequentially("to AAPL when @rsi");
  await expect(
    page.locator("#chat-discovery-option-indicator-rsi"),
  ).toBeVisible();
  await page.locator("#chat-discovery-option-indicator-rsi").click();
  await composer.pressSequentially("falls");

  await expect(
    composer.locator('[data-entity-token-kind="asset"]'),
  ).toHaveCount(1);
  await expect(
    composer.locator('[data-entity-token-kind="indicator"]'),
  ).toHaveCount(1);

  await composer.evaluate((root) => {
    const token = root.querySelector<HTMLElement>(
      '[data-entity-token-kind="asset"]',
    );
    if (!token) throw new Error("Asset token was not rendered in the composer.");
    root.focus();
    const selection = window.getSelection();
    if (!selection) throw new Error("Selection API is unavailable.");
    const range = document.createRange();
    range.setStartAfter(token);
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    root.dispatchEvent(new KeyboardEvent("keyup", { bubbles: true, key: "ArrowRight" }));
  });
  await expect(
    composer.locator('[data-entity-token-kind="asset"]'),
  ).toHaveAttribute("data-entity-token-focused", "true");
}

const cases = [
  {
    name: "English desktop",
    language: "en" as const,
    viewport: { width: 1280, height: 900 },
    framePrefix: "en-desktop",
  },
  {
    name: "English mobile",
    language: "en" as const,
    viewport: { width: 390, height: 844 },
    framePrefix: "en-mobile",
  },
  {
    name: "Spanish desktop",
    language: "es-419" as const,
    viewport: { width: 1280, height: 900 },
    framePrefix: "es-419-desktop",
  },
  {
    name: "Spanish mobile",
    language: "es-419" as const,
    viewport: { width: 390, height: 844 },
    framePrefix: "es-419-mobile",
  },
];

test.describe("exact ticker mention entity tags", () => {
  for (const scenario of cases) {
    test(`${scenario.name} preserves only selected text through reload`, async ({ page }) => {
      await page.setViewportSize(scenario.viewport);
      const fixture = await installFixture(page, scenario.language);

      await page.goto(`/chat?conversation=${CONVERSATION_ID}`, {
        waitUntil: "networkidle",
      });
      await expect(page.getByTestId("chat-input")).toBeVisible({
        timeout: 15_000,
      });
      await expect(
        page.getByTestId("conversation-transcript-region"),
      ).toHaveAttribute("data-conversation-id", CONVERSATION_ID);
      await expect(
        page.getByTestId("conversation-transcript-region"),
      ).toHaveAttribute("aria-busy", "false");

      await selectAssetAndIndicator(page);
      await page.getByTestId("chat-send").click();
      await expect(
        page.locator('[data-confirmation-status="ready_to_run"]'),
      ).toBeVisible();

      await expect.poll(() => fixture.streamRequests.length).toBe(1);
      expect(fixture.streamRequests[0]).toMatchObject({
        conversation_id: CONVERSATION_ID,
        message: MESSAGE,
        mentions: [
          {
            id: asset.id,
            insert_text: "AAPL",
            message_range: { start: 8, end: 12 },
          },
          {
            id: indicator.id,
            insert_text: "RSI",
            message_range: { start: 26, end: 29 },
          },
        ],
      });

      const transcriptTokens = page.locator(
        '[data-entity-token-surface="transcript"]',
      );
      await expect(transcriptTokens).toHaveCount(2);
      await expect(
        page.locator(
          '[data-entity-token-surface="transcript"][data-entity-token-kind="asset"]',
        ),
      ).toHaveCount(1);
      await expect(
        page.locator(
          '[data-entity-token-surface="transcript"][data-entity-token-kind="indicator"]',
        ),
      ).toHaveCount(1);
      await expect(
        page.locator('[data-entity-token-surface="card"][data-entity-token-kind="asset"]'),
      ).toHaveCount(1);

      await page.reload({ waitUntil: "networkidle" });
      await expect(transcriptTokens).toHaveCount(2);
      await expect(
        page.locator(
          '[data-entity-token-surface="transcript"][data-entity-token-kind="asset"]',
        ),
      ).toHaveCount(1);
      await expect(
        page.locator(
          '[data-entity-token-surface="transcript"][data-entity-token-kind="indicator"]',
        ),
      ).toHaveCount(1);
      await expect(
        page.getByText(MESSAGE, { exact: true }),
      ).toBeVisible();
      await capture(
        page.getByText(MESSAGE, { exact: true }),
        `${scenario.framePrefix}-message.png`,
      );
      await capture(
        page
          .locator('[data-confirmation-status="ready_to_run"]')
          .locator("xpath=ancestor::section[1]"),
        `${scenario.framePrefix}-confirmation.png`,
      );

      fixture.showResult();
      await page.reload({ waitUntil: "networkidle" });
      const resultCard = page.getByRole("region", {
        name: "Hero + Delta Evidence Card",
      });
      await expect(resultCard).toBeVisible();
      await expect(
        resultCard.locator(
          '[data-entity-token-surface="card"][data-entity-token-kind="asset"]',
        ),
      ).toHaveCount(1);
      await resultCard.evaluate((element) =>
        Promise.all(element.getAnimations().map((animation) => animation.finished)),
      );
      await capture(resultCard, `${scenario.framePrefix}-result.png`, {
        topInset: 104,
      });

      expect(fixture.unexpectedRequests).toEqual([]);
    });
  }
});
