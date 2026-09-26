import { expect, type Page } from "@playwright/test";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import {
  FREEZE_CSS,
  installBreakpointFixture,
  type Account,
  type Language,
} from "../support/breakpoint-fixture";

// Keep the shared guest fixture's August 14 expiry in the future.
export const RECEIVED_AT = new Date("2026-08-13T18:17:32Z");
const nextMidnight = new Date(RECEIVED_AT);
nextMidnight.setUTCHours(24, 0, 0, 0);
export const MIDNIGHT_RETRY_AFTER = String(
  (nextMidnight.getTime() - RECEIVED_AT.getTime()) / 1_000,
);
export const RAW_SERVER_DETAIL = "Argus could not start this turn. Please try again.";
export const VIEWPORTS = [
  { name: "mobile", width: 360, height: 800 },
  { name: "desktop", width: 1280, height: 900 },
] as const;

export const COPY = {
  en: {
    prompt: "Compare Apple with SPY",
    claimError: "Argus could not start this turn. Try again in a moment.",
    capError: "You've reached today's question limit. It resets at 8:00 PM.",
    retrySoon: /Retry in \d+ seconds?/,
    retry: "Retry",
    success: "Let's test that idea.",
  },
  "es-419": {
    prompt: "Compara Apple con SPY",
    claimError: "Argus no pudo iniciar este turno. Inténtalo de nuevo en un momento.",
    capError: "Llegaste al límite de preguntas de hoy. Se reinicia a las 8:00 PM.",
    retrySoon: /Reintentar en \d+ segundos?/,
    retry: "Reintentar",
    success: "Probemos esa idea.",
  },
} as const;

export async function installComputeLimitJourney(
  page: Page,
  options: {
    account: Account;
    language: Language;
    status: 429 | 503;
    failures?: number;
    retryAfter?: string;
    newConversation?: boolean;
  },
) {
  const evidence = { sentMessages: [] as string[], streamStatuses: [] as number[] };
  if (options.status === 429) {
    await page.clock.setFixedTime(RECEIVED_AT);
  } else {
    await page.clock.install({ time: RECEIVED_AT });
  }
  await installBreakpointFixture(page, { ...options, emptyChat: true, theme: "light" });
  await page.route("**/api/v1/conversations/*/messages**", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ items: options.newConversation ? [] : [
        { id: "prior-user", role: "user", content: options.language === "en" ? "Hello" : "Hola", created_at: RECEIVED_AT.toISOString(), metadata: {} },
        { id: "prior-answer", role: "assistant", content: options.language === "en" ? "What would you like to test?" : "¿Qué te gustaría probar?", created_at: RECEIVED_AT.toISOString(), metadata: {} },
      ], next_cursor: null }),
    });
  });
  await page.route("**/api/v1/conversations", async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        conversation: {
          id: "conversation-alpha",
          title: "New idea",
          title_source: "system_default",
          pinned: false,
          archived: false,
          created_at: RECEIVED_AT.toISOString(),
          updated_at: RECEIVED_AT.toISOString(),
          language: options.language,
        },
      }),
    });
  });
  await page.route("**/api/v1/chat/stream", async (route) => {
    const body = route.request().postDataJSON() as { message?: string };
    evidence.sentMessages.push(body.message ?? "");
    if (evidence.sentMessages.length <= (options.failures ?? 1)) {
      evidence.streamStatuses.push(options.status);
      await route.fulfill({
        status: options.status,
        contentType: "application/problem+json",
        headers: {
          ...(options.retryAfter === undefined ? {} : { "Retry-After": options.retryAfter }),
          "Access-Control-Allow-Origin": new URL(page.url()).origin,
          "Access-Control-Allow-Credentials": "true",
          "Access-Control-Expose-Headers": "Retry-After, X-Request-Id",
        },
        body: JSON.stringify({
          type: "about:blank",
          title: options.status === 503 ? "Service Temporarily Unavailable" : "Too Many Requests",
          status: options.status,
          code: options.status === 503 ? `${options.account}_compute_claim_unavailable` : "too_many_requests",
          detail: RAW_SERVER_DETAIL,
        }),
      });
      return;
    }
    evidence.streamStatuses.push(200);
    const success = COPY[options.language].success;
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream",
      body: [
        'data: {"type":"stage_start","stage":"clarify"}',
        "",
        `data: ${JSON.stringify({ type: "token", content: success })}`,
        "",
        `data: ${JSON.stringify({ type: "final", payload: {
          stage_outcome: "ready_to_respond",
          assistant_response: success,
          message_id: "message-success",
          conversation_id: "conversation-alpha",
        } })}`,
        "",
        "data: [DONE]",
        "",
      ].join("\n"),
    });
  });
  return evidence;
}

export async function sendQuestion(page: Page, language: Language, newConversation = false) {
  await page.goto(newConversation ? "/chat" : "/chat?conversation=conversation-alpha", { waitUntil: "networkidle" });
  const composer = page.getByTestId("chat-input");
  await expect(composer).toBeVisible({ timeout: 15_000 });
  await expect(composer).toBeEnabled();
  await page.addStyleTag({ content: FREEZE_CSS });
  await composer.fill(COPY[language].prompt);
  await composer.press("Enter");
}

export async function captureEvidence(page: Page, name: string) {
  const directory = process.env.COMPUTE_LIMIT_SHOT_DIR;
  if (!directory) return;
  await mkdir(directory, { recursive: true });
  await page.screenshot({ path: join(directory, `${name}.png`), animations: "disabled" });
}
