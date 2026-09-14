import { describe, expect, test } from "bun:test";
import {
  latestAssistantMessage,
  ordinaryAnswerFailure,
  researchAnswerFailure,
} from "../e2e/support/private-alpha-canary-answers";

const RETRYABLE_RUNTIME_FAILURE = { code: "runtime_failure", retryable: true };
const PUBLISHED_RESEARCH = {
  schema_version: "argus_research/v1",
  shape: "balanced",
  sources: [
    {
      title: "Apple quarterly results",
      domain: "example.com",
      url: "https://example.com/apple-results",
      source_date: "2026-07-31",
    },
  ],
};

function assistant(
  metadata: Record<string, unknown>,
  content = "Puedo ayudarte a probar una idea de inversion con datos historicos.",
  createdAt = "2026-09-14T01:43:00Z",
) {
  return {
    id: `assistant-${createdAt}`,
    role: "assistant",
    content,
    metadata,
    created_at: createdAt,
  };
}

describe("private-alpha canary answers", () => {
  test("an ordinary answer passes, including one with a non-retryable typed code", () => {
    expect(ordinaryAnswerFailure(assistant({}))).toBeNull();
    expect(
      ordinaryAnswerFailure(
        assistant({ recovery: { code: "unsupported_asset", retryable: false } }),
      ),
    ).toBeNull();
  });

  test("an answer the chat renders as a failure never passes", () => {
    expect(
      ordinaryAnswerFailure(assistant({ recovery: RETRYABLE_RUNTIME_FAILURE })),
    ).toBe("assistant_answer_recovery_runtime_failure");
    expect(
      ordinaryAnswerFailure(assistant({ retry_last_turn: { message: "Hola" } })),
    ).toBe("assistant_answer_offered_retry");
    expect(ordinaryAnswerFailure(assistant({}, "   "))).toBe(
      "assistant_answer_empty",
    );
    expect(ordinaryAnswerFailure({ role: "user", content: "Hola" })).toBe(
      "assistant_answer_missing",
    );
    expect(ordinaryAnswerFailure(null)).toBe("assistant_answer_missing");
  });

  test("a research answer passes only when published with sources", () => {
    expect(
      researchAnswerFailure(assistant({ research: PUBLISHED_RESEARCH })),
    ).toBeNull();
    expect(
      researchAnswerFailure(
        assistant({
          research: { ...PUBLISHED_RESEARCH, degraded: { code: "provider_unavailable" } },
        }),
      ),
    ).toBe("research_answer_degraded_provider_unavailable");
    expect(
      researchAnswerFailure(
        assistant({ research: { ...PUBLISHED_RESEARCH, sources: [] } }),
      ),
    ).toBe("research_sources_missing");
    expect(researchAnswerFailure(assistant({}))).toBe("research_sources_missing");
    expect(
      researchAnswerFailure(
        assistant({
          research: PUBLISHED_RESEARCH,
          recovery: RETRYABLE_RUNTIME_FAILURE,
        }),
      ),
    ).toBe("assistant_answer_recovery_runtime_failure");
    expect(
      researchAnswerFailure(assistant({ research: PUBLISHED_RESEARCH }, "")),
    ).toBe("assistant_answer_empty");
  });

  test("the newest assistant message is the one judged", () => {
    const older = assistant({}, "Respuesta anterior", "2026-09-14T01:40:00Z");
    const newer = assistant(
      { recovery: RETRYABLE_RUNTIME_FAILURE },
      "No pude responder",
      "2026-09-14T01:41:00Z",
    );
    const user = {
      id: "user-turn",
      role: "user",
      content: "Hola",
      created_at: "2026-09-14T01:42:00Z",
    };

    expect(latestAssistantMessage({ items: [newer, user, older] })?.id).toBe(
      newer.id,
    );
    expect(latestAssistantMessage({ items: [user] })).toBeNull();
    expect(latestAssistantMessage(null)).toBeNull();
  });
});
