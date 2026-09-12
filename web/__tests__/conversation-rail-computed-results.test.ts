import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { Message } from "@/components/chat/types";
import type { ToolResultCard } from "@/lib/tool-result-card";
import {
  computedAnswerCard,
  deriveConversationRailTicks,
} from "@/lib/conversation-rail";
import { hydrateMessagesFromApi } from "@/components/chat/chat-message-projection";
import type { ApiMessage } from "@/lib/argus-api";

/**
 * Cards and markers come from the real declarations through
 * scripts/dump_calculation_fixtures.py, never hand-written card JSON.
 */
const fixture = JSON.parse(
  readFileSync(join(import.meta.dir, "fixtures/calculation-cards.json"), "utf-8"),
) as { cards: Record<string, { card: ToolResultCard; computation: { kind: string; inputs: Record<string, unknown>; symbols?: string[] } | null }> };

function apiMessage(id: string, name: string, overrides: Partial<ApiMessage> = {}): ApiMessage {
  const { card, computation } = fixture.cards[name];
  const { metadata, ...rest } = overrides;
  return {
    id,
    conversation_id: "c1",
    role: "assistant",
    content: "",
    created_at: "2026-09-11T12:00:00Z",
    metadata: { tool_result_cards: [card], computation, ...(metadata ?? {}) },
    ...rest,
  };
}

function hydrated(messages: ApiMessage[]): Message[] {
  return hydrateMessagesFromApi(messages).messages;
}

describe("computed answers on the conversation rail", () => {
  test("a declared computation with a succeeded card is a result tick carrying its title and headline", () => {
    const messages = hydrated([
      { id: "u1", conversation_id: "c1", role: "user", content: "What is the payment?", created_at: "2026-09-11T11:59:00Z", metadata: {} },
      apiMessage("a1", "time_value"),
    ]);
    const ticks = deriveConversationRailTicks(messages);
    expect(ticks.map((tick) => [tick.messageId, tick.kind])).toEqual([["a1", "result"]]);
    expect(ticks[0].calculation?.kind).toBe("time_value");
    expect(ticks[0].calculation?.title.locale_key).toBe("tools.calc.time_value.title_borrow");
    expect(ticks[0].calculation?.headline?.name).toBe("payment");
    expect(ticks[0].calculation?.headline?.value).toBeCloseTo(1199.1, 2);
    expect(ticks[0].symbols).toEqual([]);
    expect(ticks[0].strategyTitle).toBeNull();
  });

  test("a decision saved on the answer supersedes the result tick", () => {
    const messages = hydrated([
      apiMessage("a1", "price_multiple", { metadata: { decision_note_id: "d1", decision_state: "watching" } }),
    ]);
    const [tick] = deriveConversationRailTicks(messages);
    expect(tick.kind).toBe("decision_saved");
    expect(tick.decisionState).toBe("watching");
    expect(tick.symbols).toEqual(["AAPL"]);
    expect(tick.calculation?.headline?.value).toBe(25);
  });

  test("an unsuccessful card needs attention and hands its outcome to the treatment owner", () => {
    const messages = hydrated([apiMessage("a1", "time_value_payment_below_interest")]);
    const [tick] = deriveConversationRailTicks(messages);
    expect(tick.kind).toBe("error_recovery");
    expect(tick.toolOutcome?.status).toBe("invalid");
    expect(tick.toolOutcome?.failure?.code).toBe("payment_below_interest");
    expect(tick.calculation).toBeUndefined();
  });

  test("a card without a backend-declared computation never ticks, however it reads", () => {
    const { card } = fixture.cards.time_value;
    const messages = hydrated([
      { id: "a1", conversation_id: "c1", role: "assistant", content: "Your payment is 1,199.10 a month.", created_at: "2026-09-11T12:00:00Z", metadata: { tool_result_cards: [card] } },
      { id: "a2", conversation_id: "c1", role: "assistant", content: "Research answer with sources.", created_at: "2026-09-11T12:01:00Z", metadata: { research: { schema_version: "argus_research/v1", sources: [{ url: "https://example.com", title: "Example" }] } } },
    ]);
    expect(deriveConversationRailTicks(messages)).toEqual([]);
    expect(computedAnswerCard(messages[0])).toBeNull();
  });

  test("a marker whose kind names no card on the message is not a result", () => {
    const messages = hydrated([
      apiMessage("a1", "time_value", { metadata: { computation: { kind: "growth_projection", inputs: {} } } }),
    ]);
    expect(deriveConversationRailTicks(messages)).toEqual([]);
  });
});
