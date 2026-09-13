import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { createInstance, type i18n } from "i18next";
import { I18nextProvider } from "react-i18next";

import ChatMessage from "../components/chat/ChatMessage";
import { hydrateMessagesFromApi } from "../components/chat/chat-message-projection";
import type { Message } from "../components/chat/types";
import type { ApiMessage } from "../lib/argus-api";
import { researchDegradedCodeFromMetadata } from "../lib/chat-discovery-sidecar";
import { mergeFinalTextMessage } from "../lib/chat-final-message";
import {
  type RecoveryDisplay,
  recoveryDisplayFromMetadata,
  recoveryDisplayText,
  retryableAssistantRecoveryCode,
  wearsQuietFailureNotice,
} from "../lib/chat-recovery-display";
import { retryLastTurnActionFromMetadata } from "../lib/chat-retry-actions";
import {
  quietNoticeContainerClass,
  retryableNoticeContainerClass,
} from "../lib/failure-treatment";

// Research provider failures (#609) reuse the retryable class: the amber notice
// and its Retry for a transient failure, the quiet notice for any other.

type Language = "en" | "es-419";

const root = join(import.meta.dir, "..");
const catalogs: Record<Language, Record<string, unknown>> = {
  en: JSON.parse(readFileSync(join(root, "public/locales/en/common.json"), "utf8")),
  "es-419": JSON.parse(
    readFileSync(join(root, "public/locales/es-419/common.json"), "utf8"),
  ),
};

async function localizedI18n(language: Language): Promise<i18n> {
  const instance = createInstance();
  await instance.init({
    lng: language,
    fallbackLng: "en",
    ns: ["common"],
    defaultNS: "common",
    interpolation: { escapeValue: false },
    resources: {
      en: { common: catalogs.en },
      "es-419": { common: catalogs["es-419"] },
    },
  });
  return instance;
}

const i18nByLanguage: Record<Language, i18n> = {
  en: await localizedI18n("en"),
  "es-419": await localizedI18n("es-419"),
};
const LANGUAGES: Language[] = ["en", "es-419"];
const RETRY_LABEL: Record<Language, string> = { en: "Retry", "es-419": "Reintentar" };

const TRANSIENT = "research_lookup_failed";
const QUIET = "research_lookup_unavailable";
const QUESTION = "What is Apple trading at right now?";

function recoveryCopy(language: Language, code: string): string {
  const chat = catalogs[language].chat as { recovery: Record<string, string> };
  return chat.recovery[code];
}

function render(message: Message, language: Language): string {
  return renderToStaticMarkup(
    React.createElement(
      I18nextProvider,
      { i18n: i18nByLanguage[language] },
      React.createElement(ChatMessage, { message }),
    ),
  );
}

/** Copy as static markup spells it: React escapes text such as apostrophes. */
function inMarkup(text: string): string {
  return renderToStaticMarkup(React.createElement(React.Fragment, null, text));
}

function researchSidecar(status: number): Record<string, unknown> {
  return {
    schema_version: "argus_research/v1",
    capability_class: "fast_quote",
    shape: "fast",
    sources: [],
    rows: [],
    retrieved_at: "2026-09-13T12:00:00+00:00",
    anchor_symbols: ["AAPL"],
    peers: [],
    usage: { invocations: 0, latency_ms: 0, cost_usd: null, cache_status: "bypass" },
    degraded: { code: "research_unavailable_http_error", status },
  };
}

const request: ApiMessage = {
  id: "request-1",
  conversation_id: "conversation-1",
  role: "user",
  content: QUESTION,
  created_at: "2026-09-13T12:00:00Z",
  metadata: {
    agent_runtime_turn: {
      status: "started",
      conversation_id: "conversation-1",
      request_id: "correlation-1",
    },
  },
};

// The persisted content is the backend's English compatibility text; readers
// see copy localized from the typed code.
function persistedFailure(transient: boolean): ApiMessage {
  const code = transient ? TRANSIENT : QUIET;
  return {
    id: "assistant-1",
    conversation_id: "conversation-1",
    role: "assistant",
    content: recoveryCopy("en", code),
    created_at: "2026-09-13T12:00:01Z",
    metadata: {
      agent_runtime_turn: {
        turn_id: request.id,
        request_id: "correlation-1",
        status: transient ? "recoverable_failed" : "completed",
        terminal: true,
        reconciled_outcome: null,
        failure_code: transient ? code : null,
        retryable: transient,
      },
      recovery: { code, retryable: transient },
      ...(transient
        ? { retry_last_turn: { request_message_id: request.id, message: QUESTION } }
        : {}),
      research: researchSidecar(transient ? 500 : 400),
    },
  };
}

function liveFailure(transient: boolean): Message {
  const code = transient ? TRANSIENT : QUIET;
  const payload: Record<string, unknown> = {
    stage_outcome: "ready_to_respond",
    assistant_response: recoveryCopy("en", code),
    message_id: "assistant-live",
    recovery: { code, retryable: transient },
    ...(transient ? { retry_last_turn: { message: QUESTION } } : {}),
    research: researchSidecar(transient ? 500 : 400),
  };
  const retry = retryLastTurnActionFromMetadata(payload, {
    assistantMessageId: "assistant-live",
  });
  return mergeFinalTextMessage(
    { id: "pending", role: "ai", kind: "text", content: "" },
    {
      assistantId: "pending",
      finalText: String(payload.assistant_response),
      finalActions: retry ? [retry] : [],
      recoveryDisplay: recoveryDisplayFromMetadata(payload),
      assistantRecoveryCode: retryableAssistantRecoveryCode(payload.recovery),
      researchDegradedCode: researchDegradedCodeFromMetadata(payload),
    },
  );
}

function hydratedFailure(transient: boolean): Message {
  const { messages } = hydrateMessagesFromApi([request, persistedFailure(transient)]);
  const assistant = messages.find((message) => message.id === "assistant-1");
  if (!assistant) throw new Error("the failure did not hydrate");
  return assistant;
}

describe("research lookup recovery (#609)", () => {
  test("both codes have their own copy in each language, with no em dash", () => {
    for (const code of [TRANSIENT, QUIET]) {
      const english = recoveryCopy("en", code);
      const spanish = recoveryCopy("es-419", code);
      expect(english.trim()).not.toBe("");
      expect(spanish.trim()).not.toBe("");
      expect(spanish).not.toBe(english);
      expect(`${english}${spanish}`).not.toContain("—");
    }
    expect(recoveryCopy("en", TRANSIENT)).not.toBe(recoveryCopy("en", QUIET));
  });

  test("only the non-retryable research code joins the quiet notice", () => {
    const cases: Array<[RecoveryDisplay | null, boolean]> = [
      [{ kind: "recovery_code", code: QUIET }, true],
      [{ kind: "artifact_action_recovery", status: "invalid_state" }, true],
      [{ kind: "recovery_code", code: TRANSIENT }, false],
      [{ kind: "recovery_code", code: "discovery_unavailable" }, false],
      [{ kind: "recovery_code", code: "discovery_target_missing" }, false],
      [null, false],
    ];
    for (const [display, quiet] of cases) {
      expect(wearsQuietFailureNotice(display)).toBe(quiet);
    }
  });

  test("a transient failure hydrates with a retry of the same persisted question", () => {
    const assistant = hydratedFailure(true);

    expect(assistant.assistantRecoveryCode).toBe(TRANSIENT);
    expect(assistant.recoveryDisplay).toEqual({
      kind: "recovery_code",
      code: TRANSIENT,
      values: undefined,
    });
    const retry = assistant.actions?.find((action) => action.type === "retry_last_turn");
    expect(retry?.payload).toMatchObject({
      message: QUESTION,
      request_message_id: request.id,
    });
    expect(assistant.nextExperiments).toBeUndefined();
    expect(assistant.nextSteps).toBeUndefined();
    expect(assistant.researchSources).toBeUndefined();
  });

  test("a transient failure wears the amber notice live and after reload", () => {
    for (const language of LANGUAGES) {
      for (const message of [liveFailure(true), hydratedFailure(true)]) {
        const markup = render(message, language);
        expect(markup).toContain(retryableNoticeContainerClass);
        expect(markup).toContain('role="status"');
        expect(markup).toContain(inMarkup(recoveryCopy(language, TRANSIENT)));
        expect(markup).toContain(`>${RETRY_LABEL[language]}</button>`);
        expect(markup).not.toContain('data-testid="recovery-failure-notice"');
      }
    }
  });

  test("a failure that cannot be retried wears the quiet notice live and after reload", () => {
    for (const language of LANGUAGES) {
      for (const message of [liveFailure(false), hydratedFailure(false)]) {
        expect(message.actions ?? []).toEqual([]);
        expect(message.assistantRecoveryCode ?? null).toBeNull();
        const markup = render(message, language);
        expect(markup).toContain('data-testid="recovery-failure-notice"');
        expect(markup).toContain(quietNoticeContainerClass);
        expect(markup).toContain(inMarkup(recoveryCopy(language, QUIET)));
        expect(markup).not.toContain(retryableNoticeContainerClass);
        expect(markup).not.toContain(`>${RETRY_LABEL[language]}</button>`);
      }
    }
  });

  test("the rendered copy never falls back to the persisted English in Spanish", () => {
    const markup = render(hydratedFailure(true), "es-419");
    expect(markup).toContain(inMarkup(recoveryCopy("es-419", TRANSIENT)));
    expect(markup).not.toContain(inMarkup(recoveryCopy("en", TRANSIENT)));
    expect(
      recoveryDisplayText(
        { kind: "recovery_code", code: TRANSIENT },
        i18nByLanguage["es-419"].t,
      ),
    ).toBe(recoveryCopy("es-419", TRANSIENT));
  });
});
