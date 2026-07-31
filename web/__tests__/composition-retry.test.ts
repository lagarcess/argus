import { describe, expect, test } from "bun:test";

import { retireSupersededFailures } from "@/lib/chat-retry-action-history";
import {
  hydrateTextMessageFromApi,
  precedingUserMessageForRetryableRecovery,
} from "@/lib/chat-message-hydration";
import type { Message } from "@/components/chat/types";
import type { ApiMessage } from "@/lib/argus-api";

const failureMetadata = {
  recovery: {
    code: "latest_result_followup_unavailable",
    retryable: true,
  },
};

describe("composition-failure retry contract (issue #249)", () => {
  test("a completed retry keeps the original user turn and hides its durable duplicate", () => {
    const messages = [
      { id: "u1", role: "user", kind: "text", content: "What was the worst drop?" },
      {
        id: "a1",
        role: "ai",
        kind: "text",
        content: "could not safely answer",
        contentPresentation: "superseded_runtime_failure",
      },
      { id: "u2", role: "user", kind: "text", content: "What was the worst drop?" },
      { id: "a2", role: "ai", kind: "text", content: "could not safely answer" },
    ] as Message[];

    const retired = retireSupersededFailures(messages);

    expect(retired.map((message) => message.id)).toEqual(["u1", "a2"]);
    expect(retired.filter((message) => message.role === "user")).toHaveLength(1);
    expect(retired[0].transcriptAnchorIds).toEqual(["u2"]);
  });

  test("an unsuperseded failure keeps rendering", () => {
    const messages = [
      { id: "u1", role: "user", kind: "text", content: "hi" },
      { id: "a1", role: "ai", kind: "text", content: "could not safely answer" },
    ] as Message[];

    expect(retireSupersededFailures(messages)).toHaveLength(2);
  });

  test("a persisted retryable failure hydrates a Retry from the preceding user turn", () => {
    const items = [
      { id: "u1", role: "user", content: "What was the worst drop?", metadata: {} },
      { id: "a1", role: "assistant", content: "failure", metadata: failureMetadata },
    ] as ApiMessage[];

    const request = precedingUserMessageForRetryableRecovery(items, items[1]);
    expect(request?.id).toBe("u1");

    const hydrated = hydrateTextMessageFromApi(items[1], {
      retryRequestMessage: request,
    });
    const retry = hydrated.actions?.find(
      (action) => action.type === "retry_last_turn",
    );
    expect(retry).toBeTruthy();
    expect(retry?.payload?.message).toBe("What was the worst drop?");
    expect(retry?.payload?.failed_assistant_id).toBe("a1");
    expect(hydrated.assistantRecoveryCode).toBe(
      "latest_result_followup_unavailable",
    );
  });

  test("a non-retryable recovery hydrates no retry and no failure code", () => {
    const items = [
      { id: "u1", role: "user", content: "hi", metadata: {} },
      {
        id: "a1",
        role: "assistant",
        content: "terminal",
        metadata: { recovery: { code: "x", retryable: false } },
      },
    ] as ApiMessage[];

    expect(precedingUserMessageForRetryableRecovery(items, items[1])).toBeNull();
    const hydrated = hydrateTextMessageFromApi(items[1], {});
    expect(hydrated.assistantRecoveryCode).toBeNull();
  });
});
