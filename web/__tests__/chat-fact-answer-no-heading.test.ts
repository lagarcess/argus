import { describe, expect, test } from "bun:test";

import { hydrateTextMessageFromApi } from "../lib/chat-message-hydration";
import type { ApiMessage } from "../lib/argus-api";

const ANSWERS = {
  en: {
    fact: "The worst drop ran from February 18, 2025 to August 1, 2025.",
    limitation: "This test does not store the date of the worst drop.",
  },
  "es-419": {
    fact: "La peor caída fue del 18 de febrero al 1 de agosto de 2025.",
    limitation: "Esta prueba no guarda la fecha de la peor caída.",
  },
};

function apiMessage(content: string, responseIntent: Record<string, unknown>): ApiMessage {
  return {
    id: "assistant-1",
    conversation_id: "conversation-1",
    role: "assistant",
    content,
    created_at: "2026-09-12T00:00:00Z",
    metadata: { response_intent: responseIntent },
  };
}

describe("answers after a result carry no heading", () => {
  for (const [language, answers] of Object.entries(ANSWERS)) {
    test(`a stored fact answer is only the answer (${language})`, () => {
      const message = hydrateTextMessageFromApi(
        apiMessage(answers.fact, {
          kind: "beginner_guidance",
          facts: { fact_key: "drawdown_date", drawdown_date: "2025-08-01" },
        }),
      );

      expect(message.content).toBe(answers.fact);
      expect(Object.keys(message)).not.toContain("resultFactHeadingKey");
    });

    test(`a fact the run does not store is only the answer (${language})`, () => {
      const message = hydrateTextMessageFromApi(
        apiMessage(answers.limitation, {
          kind: "unsupported_recovery",
          facts: {
            limitation_code: "latest_result_metric_unavailable",
            requested_metric: "drawdown_date",
          },
        }),
      );

      expect(message.content).toBe(answers.limitation);
      expect(message.recoveryDisplay).toBeNull();
      expect(Object.keys(message)).not.toContain("resultFactHeadingKey");
    });
  }
});
