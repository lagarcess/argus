import {
  expect,
  test,
  type Locator,
  type Page,
  type Route,
} from "@playwright/test";

const CONVERSATION_ID = "issue-313-conversation";
const CREATED_AT = "2026-07-31T12:00:00Z";

type Locale = "en" | "es-419";
type Producer =
  | "result-follow-up"
  | "composition"
  | "discovery"
  | "retest";
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
  producer: Producer;
  theme: Theme;
  viewport: Viewport;
  screenshot?: string;
};

const copy = {
  en: {
    capability: "I can test one asset class at a time.",
    clarification: "Which date range should I use?",
    nonRetryable:
      "I cannot look up current source-backed candidates yet, and I will not guess from memory. Name a symbol or company you already have in mind and I can test it. Everything in this chat is unchanged.",
    retry: "Retry",
  },
  "es-419": {
    capability: "Puedo probar una clase de activo a la vez.",
    clarification: "¿Qué rango de fechas quieres usar?",
    nonRetryable:
      "Todavía no puedo buscar candidatos respaldados por fuentes actuales, y no voy a adivinar de memoria. Dime un símbolo o una empresa que tengas en mente y puedo probarla. Todo en este chat sigue igual.",
    retry: "Reintentar",
  },
} as const;

const producerCopy: Record<
  Producer,
  {
    code: string;
    prompt: Record<Locale, string>;
    recovery: Record<Locale, string>;
  }
> = {
  "result-follow-up": {
    code: "latest_result_followup_unavailable",
    prompt: {
      en: "What was the worst drawdown?",
      "es-419": "¿Cuál fue la peor caída?",
    },
    recovery: {
      en: "I still have the latest result in this chat, but I could not safely answer that follow-up. Please retry in a moment.",
      "es-419": "Todavía tengo el resultado más reciente en este chat, pero no pude responder ese seguimiento con confianza. Intenta de nuevo en un momento.",
    },
  },
  composition: {
    code: "runtime_failure",
    prompt: {
      en: "Compare that result with SPY.",
      "es-419": "Compara ese resultado con SPY.",
    },
    recovery: {
      en: "Something went wrong. Your conversation is saved. Please try again.",
      "es-419": "Algo salió mal. Tu conversación está guardada. Intenta de nuevo.",
    },
  },
  discovery: {
    code: "discovery_search_failed",
    prompt: {
      en: "Find current cybersecurity stocks.",
      "es-419": "Busca acciones actuales de ciberseguridad.",
    },
    recovery: {
      en: "I could not complete a source-backed lookup just now, and I will not guess names from memory. Everything in this chat is unchanged; ask again in a moment or name a symbol and I can test it.",
      "es-419": "No pude completar la búsqueda respaldada por fuentes en este momento, y no voy a adivinar nombres de memoria. Todo en este chat sigue igual; intenta de nuevo en un momento o dime un símbolo y puedo probarlo.",
    },
  },
  retest: {
    code: "runtime_failure",
    prompt: {
      en: "Retest with current data",
      "es-419": "Volver a probar con datos actuales",
    },
    recovery: {
      en: "Something went wrong. Your conversation is saved. Please try again.",
      "es-419": "Algo salió mal. Tu conversación está guardada. Intenta de nuevo.",
    },
  },
};

const cases: QaCase[] = [
  {
    locale: "en",
    producer: "result-follow-up",
    theme: "light",
    viewport: "desktop",
    screenshot: "en-desktop-light-result-follow-up.png",
  },
  {
    locale: "en",
    producer: "composition",
    theme: "dark",
    viewport: "desktop",
  },
  {
    locale: "en",
    producer: "discovery",
    theme: "light",
    viewport: "mobile",
  },
  {
    locale: "en",
    producer: "retest",
    theme: "dark",
    viewport: "mobile",
    screenshot: "en-mobile-dark-retest.png",
  },
  {
    locale: "es-419",
    producer: "result-follow-up",
    theme: "light",
    viewport: "desktop",
  },
  {
    locale: "es-419",
    producer: "composition",
    theme: "dark",
    viewport: "desktop",
    screenshot: "es-desktop-dark-composition.png",
  },
  {
    locale: "es-419",
    producer: "discovery",
    theme: "light",
    viewport: "mobile",
    screenshot: "es-mobile-light-discovery.png",
  },
  {
    locale: "es-419",
    producer: "retest",
    theme: "dark",
    viewport: "mobile",
  },
];

function json(route: Route, body: unknown, status = 200): Promise<void> {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

function sseFinal(
  route: Route,
  payload: Record<string, unknown>,
): Promise<void> {
  return route.fulfill({
    status: 200,
    contentType: "text/event-stream",
    body: `data: ${JSON.stringify({ type: "final", payload })}\n\ndata: [DONE]\n\n`,
  });
}

function userMessage(id: string, content: string, index: number): ApiMessage {
  return {
    id,
    conversation_id: CONVERSATION_ID,
    role: "user",
    content,
    created_at: new Date(Date.parse(CREATED_AT) + index * 1000).toISOString(),
    metadata: {},
  };
}

function assistantMessage(
  id: string,
  content: string,
  index: number,
  metadata: Record<string, unknown> = {},
): ApiMessage {
  return {
    id,
    conversation_id: CONVERSATION_ID,
    role: "assistant",
    content,
    created_at: new Date(Date.parse(CREATED_AT) + index * 1000).toISOString(),
    metadata,
  };
}

function baselineMessages(locale: Locale): ApiMessage[] {
  return [
    userMessage("clarification-request", "Clarify the dates", 0),
    assistantMessage(
      "clarification-answer",
      copy[locale].clarification,
      1,
      {
        response_intent: {
          kind: "clarification",
          requested_fields: ["date_range"],
        },
      },
    ),
    userMessage("capability-request", "Can I mix stocks and crypto?", 2),
    assistantMessage("capability-answer", copy[locale].capability, 3),
    userMessage("non-retryable-request", "Discover an unsupported target", 4),
    assistantMessage(
      "non-retryable-answer",
      copy[locale].nonRetryable,
      5,
      {
        recovery: {
          code: "discovery_unavailable",
          retryable: false,
        },
      },
    ),
  ];
}

async function installFixture(
  page: Page,
  qaCase: QaCase,
): Promise<{ consoleErrors: string[]; requestUrls: string[]; unexpected: string[] }> {
  const { locale, producer, theme } = qaCase;
  const producerFixture = producerCopy[producer];
  const messages = baselineMessages(locale);
  const consoleErrors: string[] = [];
  const requestUrls: string[] = [];
  const unexpected: string[] = [];

  page.on("console", (message) => {
    if (message.type() === "error") consoleErrors.push(message.text());
  });
  page.on("request", (request) => requestUrls.push(request.url()));
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
    const url = new URL(request.url());
    const path = url.pathname;
    if (path.endsWith("/api/v1/me")) {
      return json(route, {
        user: {
          id: "issue-313-user",
          email: "issue-313@example.com",
          username: "issue313",
          display_name: "Issue 313 QA",
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
            title: "Issue 313 recovery QA",
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
    if (path.endsWith("/api/v1/history")) {
      return json(route, { items: [], next_cursor: null });
    }
    if (path.endsWith("/api/v1/search")) {
      return json(route, { items: [], next_cursor: null });
    }
    if (path.endsWith("/api/v1/chat/stream")) {
      const requestId = `request-${producer}`;
      const assistantId = `assistant-${producer}`;
      messages.push(
        userMessage(requestId, producerFixture.prompt[locale], 6),
        assistantMessage(
          assistantId,
          producerFixture.recovery[locale],
          7,
          {
            agent_runtime_turn: {
              turn_id: requestId,
              request_id: `correlation-${producer}`,
              status: "recoverable_failed",
              terminal: true,
              failure_code: producerFixture.code,
              retryable: true,
            },
            recovery: {
              code: producerFixture.code,
              retryable: true,
            },
            retry_last_turn: {
              request_message_id: requestId,
              message: producerFixture.prompt[locale],
            },
          },
        ),
      );
      return sseFinal(route, {
        stage_outcome: "ready_to_respond",
        assistant_response: producerFixture.recovery[locale],
        message_id: assistantId,
        retry_last_turn: {
          message: producerFixture.prompt[locale],
        },
        recovery: {
          code: producerFixture.code,
          retryable: true,
          language: locale,
        },
      });
    }
    unexpected.push(`${request.method()} ${path}`);
    return json(route, { detail: "Unexpected issue #313 QA request" }, 501);
  });

  return { consoleErrors, requestUrls, unexpected };
}

async function visualTreatment(locator: Locator) {
  return locator.evaluate((element) => {
    const style = window.getComputedStyle(element);
    const warning = element.querySelector(".lucide-message-square-warning");
    const warningStyle = warning ? window.getComputedStyle(warning) : null;
    return {
      backgroundColor: style.backgroundColor,
      borderColor: style.borderTopColor,
      borderRadius: style.borderRadius,
      borderWidth: style.borderTopWidth,
      paddingInline: `${style.paddingLeft}|${style.paddingRight}`,
      paddingBlock: `${style.paddingTop}|${style.paddingBottom}`,
      warningColor: warningStyle?.color ?? null,
    };
  });
}

for (const qaCase of cases) {
  test.describe(
    `${qaCase.locale} ${qaCase.viewport} ${qaCase.theme} ${qaCase.producer}`,
    () => {
      test.use({
        colorScheme: qaCase.theme,
        viewport:
          qaCase.viewport === "desktop"
            ? { width: 1280, height: 900 }
            : { width: 390, height: 844 },
      });

      test("keeps the retryable failure equally visible live and after reload", async ({
        page,
      }, testInfo) => {
        const evidence = await installFixture(page, qaCase);
        const fixture = producerCopy[qaCase.producer];
        const recoveryText = fixture.recovery[qaCase.locale];
        const retryLabel = copy[qaCase.locale].retry;

        await page.goto(`/chat?conversation=${CONVERSATION_ID}`, {
          waitUntil: "networkidle",
        });
        await expect(page.getByTestId("chat-input")).toBeVisible({
          timeout: 15_000,
        });
        await expect(page.locator("html")).toHaveAttribute("lang", qaCase.locale);
        if (qaCase.theme === "dark") {
          await expect(page.locator("html")).toHaveClass(/dark/);
        } else {
          await expect(page.locator("html")).not.toHaveClass(/dark/);
        }

        for (const ordinaryText of [
          copy[qaCase.locale].clarification,
          copy[qaCase.locale].capability,
          copy[qaCase.locale].nonRetryable,
        ]) {
          const ordinary = page.getByText(ordinaryText, { exact: true });
          await expect(ordinary).toBeVisible();
          expect(
            await ordinary.evaluate(
              (element) => element.closest('[role="status"]') === null,
            ),
          ).toBe(true);
        }

        await page.getByTestId("chat-input").fill(fixture.prompt[qaCase.locale]);
        await page.getByTestId("chat-send").click();

        const liveRecovery = page
          .getByRole("status")
          .filter({ hasText: recoveryText });
        await expect(liveRecovery).toHaveCount(1);
        await expect(liveRecovery).toBeVisible();
        await expect(
          liveRecovery.getByRole("button", { name: retryLabel, exact: true }),
        ).toBeVisible();
        const liveTreatment = await visualTreatment(liveRecovery);

        await page.reload({ waitUntil: "networkidle" });

        const hydratedRecovery = page.getByTestId("user-turn-recovery");
        await expect(hydratedRecovery).toHaveCount(1);
        await expect(hydratedRecovery).toBeVisible();
        await expect(hydratedRecovery).toContainText(recoveryText);
        await expect(
          hydratedRecovery.getByRole("button", {
            name: retryLabel,
            exact: true,
          }),
        ).toBeVisible();
        await expect(
          hydratedRecovery.locator(".lucide-message-square-warning"),
        ).toHaveCount(1);
        expect(await visualTreatment(hydratedRecovery)).toEqual(liveTreatment);
        expect(
          await hydratedRecovery.evaluate(
            (element) =>
              element.previousElementSibling?.textContent?.trim() ?? null,
          ),
        ).toBe(fixture.prompt[qaCase.locale]);

        if (qaCase.screenshot) {
          await page.screenshot({
            path: testInfo.outputPath(qaCase.screenshot),
            fullPage: false,
          });
        }

        expect(evidence.unexpected).toEqual([]);
        expect(evidence.consoleErrors).toEqual([]);
        const allowedOrigins = new Set([
          "http://127.0.0.1:3313",
          "http://127.0.0.1:4313",
        ]);
        expect(
          evidence.requestUrls.filter(
            (url) => !allowedOrigins.has(new URL(url).origin),
          ),
        ).toEqual([]);
      });
    },
  );
}
