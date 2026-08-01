import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import type { ApiMessage } from "../lib/argus-api";
import {
  RETEST_ACTION_LABEL_KEY,
  RETEST_CONTRACT_VERSION,
  RETEST_WINDOW_POLICY,
  applyRetestReceipt,
  retestActionOption,
  retestReceiptContextLine,
  retestReceiptFromFinalPayload,
  retestReceiptFromMetadata,
} from "../lib/chat-retest";
import { hydrateMessagesFromApi } from "../components/chat/chat-message-projection";
import { omnisearchActionHandlers } from "../components/chat/omnisearch-actions";
import {
  normalizeDurableRetryActionHistory,
  retryLastTurnActionFromMetadata,
  retryLastTurnChatActionFromAction,
} from "../lib/chat-retry-actions";
import {
  recoveryDisplayFromMetadata,
  retryableAssistantRecoveryCode,
} from "../lib/chat-recovery-display";
import type { ChatActionOption, Message } from "../components/chat/types";

const root = join(import.meta.dir, "..");
const RECEIPT_METADATA = {
  contract_version: RETEST_CONTRACT_VERSION,
  window_policy: RETEST_WINDOW_POLICY,
  source_run_id: "run-42",
  symbols: ["GLD"],
  strategy_family: "buy_and_hold",
  timeframe: "1D",
  duration_days: 365,
  duration: { unit: "year", count: 1 },
};
const PERSISTED_ACTION = {
  type: "retest_run",
  label: null,
  labelKey: RETEST_ACTION_LABEL_KEY,
  payload: {
    source_run_id: "run-42",
    window_policy: RETEST_WINDOW_POLICY,
    contract_version: RETEST_CONTRACT_VERSION,
  },
  presentation: null,
};

function localeStrings(language: "en" | "es-419"): Record<string, string> {
  const bundle = JSON.parse(
    readFileSync(join(root, `public/locales/${language}/common.json`), "utf-8"),
  );
  const flat: Record<string, string> = {};
  const walk = (value: unknown, prefix: string) => {
    if (typeof value === "string") {
      flat[prefix] = value;
      return;
    }
    if (typeof value === "object" && value !== null) {
      for (const [key, nested] of Object.entries(value)) {
        walk(nested, prefix ? `${prefix}.${key}` : key);
      }
    }
  };
  walk(bundle, "");
  return flat;
}

function translator(language: "en" | "es-419") {
  const strings = localeStrings(language);
  return (key: string, defaultValue: string, options?: Record<string, unknown>) => {
    const count = typeof options?.count === "number" ? options.count : null;
    const resolved =
      (count !== null
        ? strings[`${key}_${count === 1 ? "one" : "other"}`]
        : undefined) ??
      strings[key] ??
      defaultValue;
    return resolved.replace(/\{\{count\}\}/g, String(count ?? ""));
  };
}

function userActionMessage(overrides: Partial<ApiMessage> = {}): ApiMessage {
  return {
    id: "user-retest-1",
    conversation_id: "conversation-1",
    role: "user",
    content: "Retest with current data",
    created_at: "2026-07-31T00:00:00Z",
    metadata: {
      chat_action: PERSISTED_ACTION,
      retest_receipt: RECEIPT_METADATA,
    },
    ...overrides,
  } as ApiMessage;
}

describe("typed retest transport", () => {
  test("submitted action carries identity and policy only", () => {
    const action = retestActionOption("run-42");

    expect(action.type).toBe("retest_run");
    expect(action.labelKey).toBe(RETEST_ACTION_LABEL_KEY);
    expect(action.payload).toEqual({
      source_run_id: "run-42",
      window_policy: RETEST_WINDOW_POLICY,
      contract_version: RETEST_CONTRACT_VERSION,
    });
    expect(Object.keys(action.payload ?? {})).toHaveLength(3);
  });

  test("retest submits only after the source conversation is ready", async () => {
    const sent: Array<[string, ChatActionOption | undefined]> = [];
    let ready = true;
    const handlers = omnisearchActionHandlers(() => ({
      closeOverlay: () => {},
      loadConversation: async () => {},
      send: (text, action) => {
        sent.push([text, action]);
        return true;
      },
      isSourceConversationReady: () => ready,
    }));

    await handlers.retest("conversation-1", "run-42");
    ready = false;
    await handlers.retest("conversation-1", "run-99");

    expect(sent).toHaveLength(1);
    expect(sent[0][1]?.payload?.source_run_id).toBe("run-42");
  });
});

describe("retest receipt projection", () => {
  test("receipt hydrates from persisted structured metadata", () => {
    const receipt = retestReceiptFromMetadata({
      retest_receipt: RECEIPT_METADATA,
    });

    expect(receipt).toEqual({
      sourceRunId: "run-42",
      symbols: ["GLD"],
      strategyFamily: "buy_and_hold",
      durationDays: 365,
      duration: { unit: "year", count: 1 },
      cadence: null,
      timeframe: "1D",
    });
  });

  test("incomplete receipt metadata renders no second line", () => {
    expect(retestReceiptFromMetadata({})).toBeNull();
    expect(
      retestReceiptFromMetadata({
        retest_receipt: { source_run_id: "run-42" },
      }),
    ).toBeNull();
  });

  test("EN and es-419 context lines hydrate equivalently", () => {
    const receipt = retestReceiptFromMetadata({
      retest_receipt: RECEIPT_METADATA,
    })!;

    expect(retestReceiptContextLine(receipt, translator("en"))).toBe(
      "GLD · Buy and hold · same 1-year duration",
    );
    expect(retestReceiptContextLine(receipt, translator("es-419"))).toBe(
      "GLD · Comprar y mantener · misma duración de 1 año",
    );
  });

  test("reload renders the receipt, never the old generated prompt", () => {
    const { messages } = hydrateMessagesFromApi([userActionMessage()]);

    expect(messages).toHaveLength(1);
    expect(messages[0].kind).toBe("action");
    expect(messages[0].retestReceipt?.sourceRunId).toBe("run-42");
    expect(messages[0].content).not.toContain("Test this exact supported setup");
    expect(messages[0].selectedAction?.labelKey).toBe(RETEST_ACTION_LABEL_KEY);
  });

  test("the turn's own response supplies the optimistic receipt", () => {
    const optimistic: Message[] = [
      { id: "user-retest-1", role: "user", kind: "action", content: "Retest with current data" },
    ];

    const unchanged = applyRetestReceipt(optimistic, "user-retest-1", null);
    const patched = applyRetestReceipt(
      optimistic,
      "user-retest-1",
      retestReceiptFromFinalPayload({ retest_receipt: RECEIPT_METADATA }),
    );

    expect(unchanged).toBe(optimistic);
    expect(patched[0].retestReceipt?.symbols).toEqual(["GLD"]);
  });
});

describe("retest failure recovery", () => {
  test("durable retry replays the typed action, not display prose", () => {
    const retryAction: ChatActionOption = {
      label: "Retry",
      type: "retry_last_turn",
      payload: {
        message: "Retest with current data",
        request_message_id: "user-retest-1",
        chat_action: PERSISTED_ACTION,
      },
    };

    const replay = retryLastTurnChatActionFromAction(retryAction);

    expect(replay?.type).toBe("retest_run");
    expect(replay?.payload).toEqual(PERSISTED_ACTION.payload);
  });

  test("the live failure frame keeps the amber assistant recovery block", () => {
    // Mirrors ChatInterface's `final` branch for the retest failure payload.
    const finalPayload = {
      stage_outcome: "ready_to_respond",
      assistant_response:
        "Something went wrong. Your conversation is saved. Please try again.",
      message_id: "assistant-failed",
      recovery: { code: "runtime_failure", retryable: true },
      retry_last_turn: {
        message: "Retest with current data",
        action: PERSISTED_ACTION,
      },
    };
    const retry = retryLastTurnActionFromMetadata(finalPayload, {
      assistantMessageId: "assistant-failed",
    });
    const rendered = normalizeDurableRetryActionHistory([
      { id: "user-retest-1", role: "user", kind: "action", content: "Retest with current data" },
      {
        id: "assistant-failed",
        role: "ai",
        kind: "text",
        content: finalPayload.assistant_response,
        recoveryDisplay: recoveryDisplayFromMetadata(finalPayload),
        assistantRecoveryCode: retryableAssistantRecoveryCode(finalPayload.recovery),
        actions: retry ? [retry] : undefined,
      },
    ]);

    expect(rendered).toHaveLength(2);
    expect(rendered[1].assistantRecoveryCode).toBe("runtime_failure");
    expect(
      retryLastTurnChatActionFromAction(rendered[1].actions?.[0])?.type,
    ).toBe("retest_run");
  });

  test("a retried receipt turn stays a single visible receipt", () => {
    const { messages } = hydrateMessagesFromApi([
      userActionMessage(),
      {
        id: "assistant-failed-1",
        conversation_id: "conversation-1",
        role: "assistant",
        content: "Something went wrong. Your conversation is saved. Please try again.",
        created_at: "2026-07-31T00:00:01Z",
        metadata: {
          // Server-side reconciliation retires the failure once the retry
          // lands an authoritative artifact in the same segment.
          agent_runtime_failure_superseded: true,
          recovery: { code: "runtime_failure", retryable: true },
        },
      } as ApiMessage,
      userActionMessage({ id: "user-retest-2" }),
      {
        id: "assistant-confirmation-1",
        conversation_id: "conversation-1",
        role: "assistant",
        content: "Ready to test buy-and-hold for GLD over the last year.",
        created_at: "2026-07-31T00:00:02Z",
        metadata: {
          confirmation_card: {
            confirmation_id: "confirmation-1",
            confirmation_state: "active",
            status: "ready_to_run",
            title: "GLD buy and hold",
            summary: "Ready to test buy-and-hold for GLD over the last year.",
            rows: [{ key: "assets", label: "Assets", value: "GLD" }],
            actions: [],
          },
        },
      } as ApiMessage,
    ]);

    // One receipt survives the replay. Since #318 the transcript keeps the
    // original user row and aliases the replay id, so Omnisearch can still
    // focus the projected row.
    const receipts = messages.filter((message) => message.retestReceipt);
    expect(receipts).toHaveLength(1);
    expect(receipts[0].id).toBe("user-retest-1");
    expect(receipts[0].transcriptAnchorIds).toContain("user-retest-2");
    expect(messages.map((message) => message.id)).toEqual([
      "user-retest-1",
      "assistant-confirmation-1",
    ]);
    expect(messages.at(-1)?.kind).toBe("strategy_confirmation");
  });
});
