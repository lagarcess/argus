import { describe, expect, test } from "bun:test";
import i18next from "i18next";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";

import ChatMessage from "../components/chat/ChatMessage";
import type { Message } from "../components/chat/types";
import type { ApiMessage } from "../lib/argus-api";
import type { ToolResultCard } from "../lib/tool-result-card";
import {
  ANNOUNCEMENT_ROLES,
  latestAssistantMessage,
  ordinaryAnswerFailure,
  researchAnswerFailure,
} from "../e2e/support/private-alpha-canary-answers";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";
import { toolCardFixture } from "./fixtures/tool-result-card";

// Fixtures are messages API pages. Each is judged as the canary judges it in
// the browser: through the transcript projection, then as ChatMessage renders it.

const PROMPT = "Hola, ¿qué puedes hacer por mí?";
const ANSWER = "Puedo ayudarte a probar una idea de inversion con datos historicos.";
const RETRYABLE_RUNTIME_FAILURE = { code: "runtime_failure", retryable: true };
const ARTIFACT_ACTION_RECOVERY = {
  kind: "artifact_action_recovery",
  facts: {
    status: "inactive",
    user_safe_message: "Esa accion ya no esta disponible.",
  },
};
const FAILED_TOOL_CARD = toolCardFixture({
  outcome: {
    status: "unavailable",
    result: null,
    failure: { code: "tool_unavailable", fields: [] },
  },
  presentation: { ...toolCardFixture().presentation, answer: null },
} as Partial<ToolResultCard>);
const SOURCE = {
  title: "Apple quarterly results",
  domain: "example.com",
  url: "https://example.com/apple-results",
  source_date: "2026-07-31",
};

const i18n = i18next.createInstance();
await i18n.init({
  lng: "es-419",
  fallbackLng: "en",
  interpolation: { escapeValue: false },
  resources: { en: { translation: en }, "es-419": { translation: es } },
});

function message(
  overrides: Partial<ApiMessage> & Pick<ApiMessage, "id" | "role" | "created_at">,
): ApiMessage {
  return {
    conversation_id: "conversation-1",
    content: overrides.role === "user" ? PROMPT : ANSWER,
    metadata: {},
    ...overrides,
  };
}

function turn(metadata: Record<string, unknown>, content = ANSWER) {
  return {
    items: [
      message({ id: "user-1", role: "user", created_at: "2026-09-14T01:42:00Z" }),
      message({
        id: "assistant-1",
        role: "assistant",
        created_at: "2026-09-14T01:42:05Z",
        content,
        metadata,
      }),
    ],
  };
}

function research(options: { degraded?: { code: string }; sources?: unknown[] } = {}) {
  return {
    research: {
      schema_version: "argus_research/v1",
      capability_class: "balanced_lookup",
      shape: "balanced",
      sources: options.sources ?? [SOURCE],
      rows: [],
      retrieved_at: "2026-09-14T01:42:04Z",
      ...(options.degraded ? { degraded: options.degraded } : {}),
    },
  };
}

function projected(payload: unknown): Message {
  const latest = latestAssistantMessage(payload);
  if (!latest) throw new Error("fixture has no assistant message");
  return latest;
}

function announces(answer: Message): boolean {
  const markup = renderToStaticMarkup(
    createElement(I18nextProvider, { i18n }, createElement(ChatMessage, { message: answer })),
  );
  return ANNOUNCEMENT_ROLES.some((role) => markup.includes(`role="${role}"`));
}

const answerFailure = (payload: unknown) =>
  ordinaryAnswerFailure(latestAssistantMessage(payload));
const researchFailure = (payload: unknown) =>
  researchAnswerFailure(latestAssistantMessage(payload));

describe("private-alpha canary answers", () => {
  test("a plain answer and a published research answer pass both judges", () => {
    const answer = projected(turn({}));
    const researched = projected(turn(research()));

    expect(ordinaryAnswerFailure(answer)).toBeNull();
    expect(researchAnswerFailure(researched)).toBeNull();
    expect(announces(answer)).toBe(false);
    expect(announces(researched)).toBe(false);
  });

  test("every failure the chat presents inside an answer is announced", () => {
    const presented: Record<string, Record<string, unknown>> = {
      unavailable_tool_results: {
        ...research(),
        tool_result_cards: [{ kind: "tool_result" }],
      },
      failed_tool_card: { tool_result_cards: [FAILED_TOOL_CARD] },
      failed_tool_job: {
        tool_jobs: [
          {
            call_id: "call-job-1",
            tool_name: "run_backtest",
            artifact_id: "artifact-job-1",
            job: { id: "job-1", conversation_id: "conversation-1", status: "failed" },
          },
        ],
      },
      retryable_recovery: { recovery: RETRYABLE_RUNTIME_FAILURE },
      artifact_action_recovery: { response_intent: ARTIFACT_ACTION_RECOVERY },
    };

    expect(
      projected(turn(presented.failed_tool_card)).toolResultCards?.[0]?.outcome.status,
    ).toBe("unavailable");
    expect(projected(turn(presented.failed_tool_job)).toolJobs?.[0]?.job.status).toBe(
      "failed",
    );
    expect(
      Object.fromEntries(
        Object.entries(presented).map(([name, metadata]) => [
          name,
          announces(projected(turn(metadata))),
        ]),
      ),
    ).toEqual({
      unavailable_tool_results: true,
      failed_tool_card: true,
      failed_tool_job: true,
      retryable_recovery: true,
      artifact_action_recovery: true,
    });
  });

  test("the projection refuses turns that are not an ordinary answer", () => {
    const textRecovery = turn({ recovery: { code: "runtime_failure", retryable: false } });

    // A recovery the chat draws as plain text announces nothing, so the
    // projection's recovery declaration is what refuses it.
    expect(announces(projected(textRecovery))).toBe(false);
    expect(answerFailure(textRecovery)).toBe("assistant_answer_recovery_recovery_code");
    expect(answerFailure(turn({ recovery: RETRYABLE_RUNTIME_FAILURE }))).toBe(
      "assistant_answer_recovery_runtime_failure",
    );
    expect(answerFailure(turn({ response_intent: ARTIFACT_ACTION_RECOVERY }))).toBe(
      "assistant_answer_recovery_artifact_action_recovery",
    );
    expect(answerFailure(turn({ retry_last_turn: { message: PROMPT } }))).toBe(
      "assistant_answer_offered_retry",
    );
    expect(answerFailure(turn({}, "   "))).toBe("assistant_answer_empty");
    expect(answerFailure({ items: [] })).toBe("assistant_answer_missing");
    expect(answerFailure(null)).toBe("assistant_answer_missing");
  });

  test("a research answer passes only when published with sources", () => {
    expect(researchFailure(turn(research()))).toBeNull();
    expect(
      researchFailure(
        turn(research({ degraded: { code: "survey_synthesis_incomplete" } })),
      ),
    ).toBe("research_answer_degraded_survey_synthesis_incomplete");
    expect(researchFailure(turn(research({ sources: [] })))).toBe(
      "research_sources_missing",
    );
    expect(
      researchFailure(
        turn({ ...research(), recovery: RETRYABLE_RUNTIME_FAILURE }),
      ),
    ).toBe("assistant_answer_recovery_runtime_failure");
  });

  test("the newest assistant message is the one judged", () => {
    const earlierFailure = message({
      id: "assistant-older",
      role: "assistant",
      created_at: "2026-09-14T01:40:05Z",
      content: "No pude responder.",
      metadata: { recovery: RETRYABLE_RUNTIME_FAILURE },
    });
    const laterAnswer = message({
      id: "assistant-newer",
      role: "assistant",
      created_at: "2026-09-14T01:41:05Z",
    });

    expect(
      answerFailure({
        items: [
          message({ id: "user-older", role: "user", created_at: "2026-09-14T01:40:00Z", content: "Primera pregunta" }),
          earlierFailure,
          message({ id: "user-newer", role: "user", created_at: "2026-09-14T01:41:00Z" }),
          laterAnswer,
        ],
      }),
    ).toBeNull();
    expect(latestAssistantMessage({ items: [earlierFailure, laterAnswer] })?.id).toBe(
      "assistant-newer",
    );
  });
});
