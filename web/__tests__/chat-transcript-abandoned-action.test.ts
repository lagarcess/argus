import { describe, expect, test } from "bun:test";

import { hydrateMessagesFromApi } from "../components/chat/transcript-hydration";
import type { ApiMessage } from "../lib/argus-api";

// #240: structured abandoned actions must not bypass recovery during the
// canonical full-transcript hydration. The action-row presentation stays
// intact while the abandoned recovery attaches with its identity-bound retry.

function abandonedActionMessage(overrides: Partial<ApiMessage> = {}): ApiMessage {
  return {
    id: "user-action-1",
    conversation_id: "conversation-1",
    role: "user",
    content: "Change dates",
    created_at: "2026-07-18T00:00:00Z",
    metadata: {
      chat_action: {
        type: "change_dates",
        label: "Change dates",
        payload: { confirmation_id: "confirmation-9" },
      },
      agent_runtime_turn: {
        turn_id: "user-action-1",
        request_id: "req-action-1",
        status: "abandoned",
        terminal: true,
        reconciled_outcome: null,
        failure_code: "turn_abandoned",
        retryable: true,
      },
      recovery: { code: "turn_abandoned", retryable: true },
      retry_last_turn: {
        request_message_id: "user-action-1",
        message: "Change dates",
        action: {
          type: "change_dates",
          label: "Change dates",
          payload: { confirmation_id: "confirmation-9" },
        },
      },
    },
    ...overrides,
  };
}

describe("canonical hydration of abandoned structured actions", () => {
  test("keeps the action row and attaches the identity-bound recovery", () => {
    const { messages } = hydrateMessagesFromApi([abandonedActionMessage()]);

    expect(messages).toHaveLength(1);
    const hydrated = messages[0];
    // Action-row presentation is intact…
    expect(hydrated.kind).toBe("action");
    expect(hydrated.selectedAction?.type).toBe("change_dates");
    // …and the abandoned recovery is attached with its bound retry.
    expect(hydrated.abandonedRecovery?.display).toEqual({
      kind: "recovery_code",
      code: "turn_abandoned",
      values: undefined,
    });
    expect(hydrated.abandonedRecovery?.action?.id).toBe(
      "retry-last-turn-user-action-1",
    );
    expect(
      hydrated.abandonedRecovery?.action?.payload?.request_message_id,
    ).toBe("user-action-1");
  });

  test("a mismatched identity renders recovery with no actionable retry", () => {
    const { messages } = hydrateMessagesFromApi([
      abandonedActionMessage({
        metadata: {
          ...abandonedActionMessage().metadata,
          retry_last_turn: {
            request_message_id: "user-action-OTHER",
            message: "Change dates",
          },
        },
      }),
    ]);

    const hydrated = messages[0];
    expect(hydrated.kind).toBe("action");
    expect(hydrated.abandonedRecovery?.display).toBeDefined();
    expect(hydrated.abandonedRecovery?.action).toBeNull();
  });
});
