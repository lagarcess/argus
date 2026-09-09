import { describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";

import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  ComputedAnswerDecision,
  computedAnswerAttachment,
  visibleDecisionState,
} from "../components/chat/DecisionAffordance";
import {
  hydrateMessagesFromApi,
  messagesWithSavedDecisionState,
} from "../components/chat/chat-message-projection";
import type { Message } from "../components/chat/types";
import type { ApiMessage } from "../lib/argus-api";
import {
  decisionComputationFromMetadata,
  decisionStateFromValue,
} from "../lib/decision-contract";
import {
  createMessageDecision,
  openDecision,
  rerunDecision,
  saveDecision,
} from "../lib/decisions-api";

const computation = {
  kind: "savings_projection",
  inputs: { monthly_amount: 5000, months: 9, target_amount: 60000 },
};

function apiMessage(overrides: Partial<ApiMessage>): ApiMessage {
  return {
    id: "answer-1",
    conversation_id: "conversation-1",
    role: "assistant",
    content: "Nine months of 5,000 a month is 45,000.",
    created_at: "2026-09-08T12:00:00Z",
    metadata: {},
    ...overrides,
  };
}

describe("computed answer decisions", () => {
  test("a computation is read only from the backend's typed declaration", () => {
    expect(decisionComputationFromMetadata({ computation })).toEqual(computation);
    expect(
      decisionComputationFromMetadata({ computation: { kind: "backtest" } }),
    ).toEqual({ kind: "backtest", inputs: {} });
    expect(decisionComputationFromMetadata({})).toBeNull();
    expect(decisionComputationFromMetadata(null)).toBeNull();
    expect(
      decisionComputationFromMetadata({ computation: { kind: "Not A Slug" } }),
    ).toBeNull();
    expect(
      decisionComputationFromMetadata({
        computation: { kind: "savings_projection", inputs: [1, 2] },
      }),
    ).toBeNull();
    expect(decisionStateFromValue("promising")).toBe("promising");
    expect(decisionStateFromValue("saved")).toBeNull();
  });

  test("hydration carries the computation and the backend-stamped decision", () => {
    const hydrated = hydrateMessagesFromApi([
      apiMessage({
        metadata: {
          computation,
          decision_note_id: "decision-1",
          decision_state: "promising",
        },
      }),
      apiMessage({ id: "plain-1", content: "Saving is a habit." }),
    ]).messages;

    expect(hydrated[0].computation).toEqual(computation);
    expect(hydrated[0].decisionNoteId).toBe("decision-1");
    expect(hydrated[0].decisionState).toBe("promising");
    expect(hydrated[0].content).toBe("Nine months of 5,000 a month is 45,000.");
    expect(hydrated[1].computation).toBeUndefined();
    expect(hydrated[1].decisionState).toBeUndefined();
  });

  test("a saved decision lands on the answer that carries the computation", () => {
    const messages: Message[] = [
      { id: "answer-1", role: "ai", kind: "text", computation },
      { id: "plain-1", role: "ai", kind: "text", content: "No computation here." },
    ];

    const saved = messagesWithSavedDecisionState(messages, "answer-1", "watching");
    const untouched = messagesWithSavedDecisionState(messages, "plain-1", "watching");

    expect(saved[0].decisionState).toBe("watching");
    expect(saved[1]).toBe(messages[1]);
    expect(untouched[1].decisionState).toBeUndefined();
  });

  test("the attachment follows the message and needs a conversation", () => {
    expect(
      computedAnswerAttachment({ id: "answer-1", computation }, "conversation-1"),
    ).toEqual({
      kind: "message",
      conversationId: "conversation-1",
      messageId: "answer-1",
    });
    expect(computedAnswerAttachment({ id: "answer-1", computation }, null)).toBeNull();
    expect(
      computedAnswerAttachment({ id: "plain-1", computation: null }, "conversation-1"),
    ).toBeNull();
  });

  test("a computed answer offers the decision and shows the stamped one", () => {
    const offered = renderToStaticMarkup(
      <ComputedAnswerDecision
        message={{ id: "answer-1", computation, decisionState: null }}
        conversationId="conversation-1"
      />,
    );
    const decided = renderToStaticMarkup(
      <ComputedAnswerDecision
        message={{ id: "answer-1", computation, decisionState: "promising" }}
        conversationId="conversation-1"
      />,
    );
    const plain = renderToStaticMarkup(
      <ComputedAnswerDecision
        message={{ id: "plain-1", computation: null, decisionState: null }}
        conversationId="conversation-1"
      />,
    );

    expect(offered).toContain('data-testid="computed-answer-decision"');
    expect(offered).toContain("Add decision");
    expect(decided).not.toContain("Add decision");
    expect(decided).toContain("chat.result_card.decision");
    expect(plain).toBe("");
  });

  test("the owner-derived prop always wins over the component's local copy", () => {
    // The transcript read derives decisionState from decision_notes; the local
    // copy only bridges a save until that refresh arrives.
    expect(visibleDecisionState(null, null)).toBeNull();
    expect(visibleDecisionState(undefined, "promising")).toBe("promising");
    expect(visibleDecisionState("watching", "promising")).toBe("watching");
    expect(visibleDecisionState("rejected", null)).toBe("rejected");

    // No DOM harness exists in this suite, so the resync itself is pinned at
    // the source: the copy follows the prop whenever the prop changes, exactly
    // as StrategyResultCard resyncs on result.decisionState.
    const affordance = readFileSync(
      join(import.meta.dir, "../components/chat/DecisionAffordance.tsx"),
      "utf-8",
    );
    const component = affordance.slice(
      affordance.indexOf("export function ComputedAnswerDecision("),
    );
    expect(component).toContain(
      "useEffect(() => {\n    setSavedState(message.decisionState ?? null);\n  }, [message.decisionState]);",
    );
    expect(component).toContain(
      "const visibleState = visibleDecisionState(message.decisionState, savedState);",
    );
    const card = readFileSync(
      join(import.meta.dir, "../components/chat/StrategyResultCard.tsx"),
      "utf-8",
    );
    expect(card).toContain(
      "useEffect(() => {\n    setSavedDecisionState(result.decisionState ?? null);\n  }, [result.decisionState]);",
    );
  });

  test("the client posts to the route the attachment names", async () => {
    const originalFetch = globalThis.fetch;
    const originalMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH;
    const calls: Array<{ url: string; init?: RequestInit }> = [];
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    globalThis.fetch = ((input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), init });
      return Promise.resolve(
        new Response(JSON.stringify({ decision: { id: "decision-1" } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }) as typeof fetch;
    try {
      await createMessageDecision("conversation-1", "answer-1", {
        decision_state: "watching",
        note: "Track it.",
      });
      await saveDecision(
        { kind: "evidence_artifact", artifactId: "artifact-1" },
        { decision_state: "promising" },
      );
      await saveDecision(
        { kind: "message", conversationId: "conversation-1", messageId: "answer-1" },
        { decision_state: "rejected" },
      );
      await openDecision("decision-1");
      await rerunDecision("decision-1", { months: 12 });
    } finally {
      globalThis.fetch = originalFetch;
      process.env.NEXT_PUBLIC_MOCK_AUTH = originalMockAuth;
    }

    expect(calls.map((call) => call.url.replace(/^.*\/api\/v1/, ""))).toEqual([
      "/conversations/conversation-1/messages/answer-1/decision",
      "/evidence-artifacts/artifact-1/decision",
      "/conversations/conversation-1/messages/answer-1/decision",
      "/decisions/decision-1",
      "/decisions/decision-1/rerun",
    ]);
    expect(calls[0].init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0].init?.body))).toEqual({
      decision_state: "watching",
      note: "Track it.",
    });
    expect(calls[3].init?.method).toBeUndefined();
    expect(JSON.parse(String(calls[4].init?.body))).toEqual({
      inputs: { months: 12 },
    });
  });
});
