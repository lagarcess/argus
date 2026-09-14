import { expect, test, type Locator, type Page, type Route } from "@playwright/test";

// Issue #609: a research provider failure reuses the retryable class. A
// transient failure shows the amber notice whose Retry asks the same question
// again, live and after a reload; any other failure shows the quiet notice. An
// answer given without the lookup keeps its content, with the notice under it.
// Every API response is scripted in the browser; no provider is called.

const CONVERSATION_ID = "issue-609-conversation";
const CREATED_AT = "2026-09-13T12:00:00Z";

type Locale = "en" | "es-419";
type Outcome = "transient" | "refused";
type Theme = "light" | "dark";
type Viewport = "desktop" | "mobile";

type ApiMessage = {
  id: string;
  conversation_id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  metadata: Record<string, unknown>;
};

type QaCase = {
  locale: Locale;
  outcome: Outcome;
  theme: Theme;
  viewport: Viewport;
  // The no-search answer ran: the reply is that answer, the notice under it.
  answered?: boolean;
};

const RECOVERY_CODE: Record<Outcome, string> = {
  transient: "research_lookup_failed",
  refused: "research_lookup_unavailable",
};
const PROVIDER_STATUS: Record<Outcome, number> = { transient: 500, refused: 400 };

// What the backend persists: English compatibility text beside the typed code.
const PERSISTED_TEXT: Record<Outcome, string> = {
  transient: "I couldn't finish looking that up just now. Try again in a moment.",
  refused: "I can't look that up right now.",
};

const copy = {
  en: {
    greeting: "Hi",
    greetingAnswer: "Hi. Ask me about a stock, or describe an idea to test.",
    prompt: "What is Apple trading at right now?",
    answer: "Apple closed at $312.41 on 2026-08-06.",
    noLookupAnswer: "From Argus market data, Apple last closed at $311.80 on 2026-08-05.",
    retry: "Retry",
    recovery: PERSISTED_TEXT,
  },
  "es-419": {
    greeting: "Hola",
    greetingAnswer: "Hola. Pregúntame por una acción, o describe una idea para probar.",
    prompt: "¿A cuánto cotiza Apple ahora mismo?",
    answer: "Apple cerró en $312.41 el 2026-08-06.",
    noLookupAnswer:
      "Con datos de mercado de Argus, Apple cerró por última vez en $311.80 el 2026-08-05.",
    retry: "Reintentar",
    recovery: {
      transient: "No pude terminar de buscar eso en este momento. Intenta de nuevo en un momento.",
      refused: "No puedo buscar eso ahora.",
    },
  },
} as const;

const cases: QaCase[] = [
  { locale: "en", outcome: "transient", theme: "light", viewport: "desktop" },
  { locale: "es-419", outcome: "transient", theme: "dark", viewport: "mobile" },
  { locale: "en", outcome: "refused", theme: "dark", viewport: "desktop" },
  { locale: "es-419", outcome: "refused", theme: "light", viewport: "mobile" },
  { locale: "en", outcome: "transient", theme: "dark", viewport: "mobile", answered: true },
  { locale: "es-419", outcome: "refused", theme: "light", viewport: "desktop", answered: true },
];

function json(route: Route, body: unknown, status = 200): Promise<void> {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function sseFinal(route: Route, payload: Record<string, unknown>): Promise<void> {
  return route.fulfill({
    status: 200,
    contentType: "text/event-stream",
    body: `data: ${JSON.stringify({ type: "final", payload })}\n\ndata: [DONE]\n\n`,
  });
}

function message(
  id: string,
  role: ApiMessage["role"],
  content: string,
  index: number,
  metadata: Record<string, unknown> = {},
): ApiMessage {
  return {
    id,
    conversation_id: CONVERSATION_ID,
    role,
    content,
    created_at: new Date(Date.parse(CREATED_AT) + index * 1000).toISOString(),
    metadata,
  };
}

function researchSidecar(outcome: Outcome): Record<string, unknown> {
  return {
    schema_version: "argus_research/v1",
    capability_class: "fast_quote",
    shape: "fast",
    sources: [],
    rows: [],
    retrieved_at: CREATED_AT,
    anchor_symbols: ["AAPL"],
    peers: [],
    usage: { invocations: 0, latency_ms: 0, cost_usd: null, cache_status: "bypass" },
    degraded: {
      code: "research_unavailable_http_error",
      status: PROVIDER_STATUS[outcome],
    },
  };
}

async function installFixture(page: Page, qaCase: QaCase) {
  const { locale, outcome, theme, answered = false } = qaCase;
  const text = copy[locale];
  const code = RECOVERY_CODE[outcome];
  const transient = outcome === "transient";
  // An answered reply persists the answer beside a recovery marked under it.
  const failureContent = answered ? text.noLookupAnswer : PERSISTED_TEXT[outcome];
  const recovery = {
    code,
    retryable: transient,
    ...(answered ? { under_answer: true } : {}),
  };
  const messages: ApiMessage[] = [
    message("greeting-request", "user", text.greeting, 0),
    message("greeting-answer", "assistant", text.greetingAnswer, 1),
  ];
  const streamedMessages: string[] = [];
  const consoleErrors: string[] = [];
  const unexpected: string[] = [];

  page.on("console", (entry) => {
    if (entry.type() === "error") consoleErrors.push(entry.text());
  });
  await page.addInitScript(
    ({ language, selectedTheme }) => {
      window.localStorage.setItem("i18nextLng", language);
      window.localStorage.setItem("argus-theme", selectedTheme);
      window.localStorage.setItem("argus:sidebar_mode", "collapsed");
    },
    { language: locale, selectedTheme: theme },
  );

  await page.route("**/api/v1/**", async (route) => {
    const request = route.request();
    const path = new URL(request.url()).pathname;
    if (path.endsWith("/api/v1/me")) {
      return json(route, {
        user: {
          id: "issue-609-user",
          email: "issue-609@example.com",
          username: "issue609",
          display_name: "Issue 609 QA",
          language: locale,
          locale: locale === "es-419" ? "es-419" : "en-US",
          theme,
        },
      });
    }
    if (path.endsWith(`/api/v1/conversations/${CONVERSATION_ID}/messages`)) {
      return json(route, { items: messages, next_cursor: null });
    }
    if (path.endsWith("/api/v1/conversations")) {
      return json(route, {
        items: [
          {
            id: CONVERSATION_ID,
            title: "Issue 609 research recovery QA",
            title_source: "user_renamed",
            pinned: false,
            archived: false,
            deleted_at: null,
            created_at: CREATED_AT,
            updated_at: CREATED_AT,
            language: locale,
          },
        ],
        next_cursor: null,
      });
    }
    if (path.endsWith(`/api/v1/conversations/${CONVERSATION_ID}/activity`)) {
      return json(route, {
        operation: { status: "idle", kind: null, updated_at: CREATED_AT },
        attention: { status: "none", cursor: null },
      });
    }
    if (path.endsWith("/api/v1/memory/availability")) {
      return json(route, { available: false, reason: "disabled" });
    }
    if (path.endsWith("/api/v1/history") || path.endsWith("/api/v1/search")) {
      return json(route, { items: [], next_cursor: null });
    }
    if (path.endsWith("/api/v1/chat/stream")) {
      const body = request.postDataJSON() as { message?: string };
      streamedMessages.push(String(body.message ?? ""));
      if (streamedMessages.length === 1) {
        messages.push(
          message("research-request", "user", text.prompt, 2),
          message("research-failure", "assistant", failureContent, 3, {
            agent_runtime_turn: {
              turn_id: "research-request",
              request_id: "correlation-609",
              status: transient ? "recoverable_failed" : "completed",
              terminal: true,
              reconciled_outcome: null,
              failure_code: transient ? code : null,
              retryable: transient,
            },
            recovery,
            ...(transient
              ? {
                  retry_last_turn: {
                    request_message_id: "research-request",
                    message: text.prompt,
                  },
                }
              : {}),
            research: researchSidecar(outcome),
          }),
        );
        return sseFinal(route, {
          stage_outcome: "ready_to_respond",
          assistant_response: failureContent,
          message_id: "research-failure",
          recovery,
          ...(transient ? { retry_last_turn: { message: text.prompt } } : {}),
          research: researchSidecar(outcome),
        });
      }
      // The retry: the failure it replaces is superseded, the same question
      // is asked again, and this time the lookup answers.
      const failure = messages.find((item) => item.id === "research-failure");
      if (failure) {
        failure.metadata = {
          ...failure.metadata,
          agent_runtime_failure_superseded: true,
          recovery: { ...recovery, retryable: false },
        };
        delete failure.metadata.retry_last_turn;
      }
      messages.push(
        message("retry-request", "user", text.prompt, 4),
        message("retry-answer", "assistant", text.answer, 5, {
          agent_runtime_turn: {
            turn_id: "retry-request",
            request_id: "correlation-609-retry",
            status: "completed",
            terminal: true,
            retryable: false,
          },
        }),
      );
      return sseFinal(route, {
        stage_outcome: "ready_to_respond",
        assistant_response: text.answer,
        message_id: "retry-answer",
      });
    }
    unexpected.push(`${request.method()} ${path}`);
    return json(route, { detail: "Unexpected issue #609 QA request" }, 501);
  });

  return { consoleErrors, streamedMessages, unexpected };
}

async function screenshot(page: Page, name: string, outputPath: string) {
  const evidenceDir = process.env.ARGUS_EVIDENCE_DIR;
  // Park the pointer at an empty edge so no hover tooltip covers the notice.
  const size = page.viewportSize();
  await page.mouse.move((size?.width ?? 2) - 2, (size?.height ?? 2) / 2);
  await page.screenshot({
    path: evidenceDir ? `${evidenceDir}/${name}` : outputPath,
    fullPage: false,
  });
}

for (const qaCase of cases) {
  const label = `${qaCase.locale}-${qaCase.viewport}-${qaCase.theme}-${qaCase.outcome}${
    qaCase.answered ? "-answered" : ""
  }`;
  test.describe(label, () => {
    test.use({
      colorScheme: qaCase.theme,
      viewport:
        qaCase.viewport === "desktop"
          ? { width: 1280, height: 900 }
          : { width: 390, height: 844 },
    });

    test("a research lookup failure wears its notice live and after reload", async ({
      page,
    }, testInfo) => {
      const evidence = await installFixture(page, qaCase);
      const text = copy[qaCase.locale];
      const recoveryText = text.recovery[qaCase.outcome];
      const transient = qaCase.outcome === "transient";
      const noLookupAnswer = page.getByText(text.noLookupAnswer, { exact: true });
      // An answer given without the lookup keeps its content, the notice under it.
      const expectNoticePlacement = async (notice: Locator) => {
        if (!qaCase.answered) {
          await expect(noLookupAnswer).toHaveCount(0);
          return;
        }
        await expect(noLookupAnswer).toBeVisible();
        const answerBox = await noLookupAnswer.boundingBox();
        const noticeBox = await notice.boundingBox();
        expect(answerBox).not.toBeNull();
        expect(noticeBox?.y ?? 0).toBeGreaterThan(
          answerBox?.y ?? Number.POSITIVE_INFINITY,
        );
      };

      await page.goto(`/chat?conversation=${CONVERSATION_ID}`, {
        waitUntil: "networkidle",
      });
      await expect(page.getByTestId("chat-input")).toBeVisible({ timeout: 15_000 });
      await expect(page.locator("html")).toHaveAttribute("lang", qaCase.locale);

      await page.getByTestId("chat-input").fill(text.prompt);
      await page.getByTestId("chat-send").click();

      const notice = transient
        ? page.getByRole("status").filter({ hasText: recoveryText })
        : page.getByTestId("recovery-failure-notice");
      await expect(notice).toHaveCount(1);
      await expect(notice).toContainText(recoveryText);
      await expectNoticePlacement(notice);
      const retry = notice.getByRole("button", { name: text.retry, exact: true });
      if (transient) {
        await expect(retry).toBeVisible();
        await expect(notice).toHaveClass(/border-amber-700\/25/);
      } else {
        await expect(retry).toHaveCount(0);
        await expect(notice).not.toHaveClass(/border-amber/);
      }
      await screenshot(page, `${label}-live.png`, testInfo.outputPath(`${label}-live.png`));

      await page.reload({ waitUntil: "networkidle" });

      const hydratedRow = page.locator('[data-message-id="research-failure"]');
      const hydrated = transient
        ? hydratedRow.getByRole("status")
        : hydratedRow.getByTestId("recovery-failure-notice");
      await expect(hydrated).toHaveCount(1);
      await expect(hydrated).toContainText(recoveryText);
      await expectNoticePlacement(hydrated);
      if (qaCase.locale === "es-419") {
        await expect(page.getByText(PERSISTED_TEXT[qaCase.outcome])).toHaveCount(0);
      }
      const hydratedRetry = hydrated.getByRole("button", {
        name: text.retry,
        exact: true,
      });
      await screenshot(
        page,
        `${label}-reloaded.png`,
        testInfo.outputPath(`${label}-reloaded.png`),
      );

      if (!transient) {
        await expect(hydratedRetry).toHaveCount(0);
        expect(evidence.streamedMessages).toEqual([text.prompt]);
      } else {
        await expect(hydratedRetry).toBeVisible();
        await hydratedRetry.click();

        await expect(page.getByText(text.answer, { exact: true })).toBeVisible();
        // Retry asked the same persisted question, and the failure it replaced,
        // with any answer above its notice, is gone without duplicating the
        // user's turn.
        expect(evidence.streamedMessages).toEqual([text.prompt, text.prompt]);
        await expect(page.getByText(recoveryText, { exact: true })).toHaveCount(0);
        await expect(noLookupAnswer).toHaveCount(0);
        await expect(page.getByText(text.prompt, { exact: true })).toHaveCount(1);
        await screenshot(
          page,
          `${label}-retried.png`,
          testInfo.outputPath(`${label}-retried.png`),
        );

        await page.reload({ waitUntil: "networkidle" });
        await expect(page.getByText(text.answer, { exact: true })).toBeVisible();
        await expect(page.getByText(text.prompt, { exact: true })).toHaveCount(1);
        await expect(page.getByText(recoveryText, { exact: true })).toHaveCount(0);
        await expect(noLookupAnswer).toHaveCount(0);
      }

      expect(evidence.unexpected).toEqual([]);
      expect(evidence.consoleErrors).toEqual([]);
    });
  });
}
