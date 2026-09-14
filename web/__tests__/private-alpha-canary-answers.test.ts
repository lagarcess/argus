import { describe, expect, test } from "bun:test";

import type { ApiMessage } from "../lib/argus-api";
import {
  latestAssistantMessage,
  ordinaryAnswerFailure,
  researchAnswerFailure,
} from "../e2e/support/private-alpha-canary-answers";

// Fixtures are messages API pages, judged through the transcript projection
// the chat renders, so an answer passes only if a reader sees an answer.

const PROMPT = "Hola, ¿qué puedes hacer por mí?";
const ANSWER = "Puedo ayudarte a probar una idea de inversion con datos historicos.";
const RETRYABLE_RUNTIME_FAILURE = { code: "runtime_failure", retryable: true };
const SOURCE = {
  title: "Apple quarterly results",
  domain: "example.com",
  url: "https://example.com/apple-results",
  source_date: "2026-07-31",
};

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

const answerFailure = (payload: unknown) =>
  ordinaryAnswerFailure(latestAssistantMessage(payload));
const researchFailure = (payload: unknown) =>
  researchAnswerFailure(latestAssistantMessage(payload));

describe("private-alpha canary answers judge the rendered transcript", () => {
  test("a plain answer bubble passes", () => {
    expect(answerFailure(turn({}))).toBeNull();
  });

  test("anything the chat renders other than a plain answer is refused", () => {
    expect(answerFailure(turn({ recovery: RETRYABLE_RUNTIME_FAILURE }))).toBe(
      "assistant_answer_recovery_runtime_failure",
    );
    expect(
      answerFailure(
        turn({
          response_intent: {
            kind: "artifact_action_recovery",
            facts: {
              status: "inactive",
              user_safe_message: "Esa accion ya no esta disponible.",
            },
          },
        }),
      ),
    ).toBe("assistant_answer_rendered_as_artifact_action_recovery");
    expect(answerFailure(turn({ artifact_presentation_kind: "result" }))).toBe(
      "assistant_answer_rendered_as_result_readout",
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
