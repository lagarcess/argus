import { describe, expect, test } from "bun:test";

import type { Message } from "../components/chat/types";
import {
  ordinaryAnswerFailure,
  researchAnswerFailure,
} from "../e2e/support/private-alpha-canary-answers";
import {
  CheckFailure,
  isReasonCode,
  reasonCode,
  UNRECOGNIZED_REASON,
} from "../e2e/support/private-alpha-canary-reasons";

// Reasons reach logs and uploaded evidence, so no backend value that is not a
// code may shape one, however it is punctuated.

const uuid = crypto.randomUUID();
const NOT_CODES = [
  uuid,
  uuid.toUpperCase(),
  uuid.replaceAll("-", "_"),
  uuid.replaceAll("-", ""),
  `job_${uuid.replaceAll("-", "_")}`,
  "01J9ZQ3K7M2X8V4N6P5R3T1Y0W",
  "canary@example.com",
  "Profile said: Private Text",
  "market-data-unavailable",
  "",
];

describe("private-alpha canary reasons", () => {
  test("a backend value that is not a code never reaches a reason", () => {
    for (const value of NOT_CODES) {
      const reason = reasonCode("backtest_job", "failed", value);
      expect(reason).toBe("backtest_job_failed_unrecognized");
      expect(isReasonCode(reason)).toBe(true);
    }
    for (const status of [4242, -1, 1.5, Number.NaN, 99, 600]) {
      expect(reasonCode("messages_http", status)).toBe(
        "messages_http_unrecognized",
      );
    }
  });

  test("codes and HTTP statuses pass unchanged", () => {
    expect(reasonCode("profile_http", 401, "unauthorized")).toBe(
      "profile_http_401_unauthorized",
    );
    expect(reasonCode("messages_http", 0)).toBe("messages_http_0");
    expect(reasonCode("backtest_job", "failed", "market_data_unavailable")).toBe(
      "backtest_job_failed_market_data_unavailable",
    );
  });

  test("a check failure publishes only a reason code", () => {
    for (const value of NOT_CODES) {
      const failure = new CheckFailure(`backtest_job_failed_${value}`);
      expect(failure.reason).toBe(UNRECOGNIZED_REASON);
      expect(failure.message).toBe(UNRECOGNIZED_REASON);
    }
    expect(new CheckFailure("a".repeat(121)).reason).toBe(UNRECOGNIZED_REASON);
    expect(new CheckFailure("chat_turn_timed_out").reason).toBe(
      "chat_turn_timed_out",
    );
  });

  test("answer failures built from backend codes stay codes", () => {
    const answer = {
      id: "assistant-1",
      role: "ai",
      kind: "text",
      content: "Hola",
      researchSources: [
        { title: "Apple", domain: "example.com", url: "https://example.com" },
      ],
    } as unknown as Message;

    for (const value of NOT_CODES.filter(Boolean)) {
      expect(ordinaryAnswerFailure({ ...answer, assistantRecoveryCode: value })).toBe(
        "assistant_answer_recovery_unrecognized",
      );
      expect(researchAnswerFailure({ ...answer, researchDegradedCode: value })).toBe(
        "research_answer_degraded_unrecognized",
      );
    }
  });
});
