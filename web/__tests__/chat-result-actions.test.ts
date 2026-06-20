import { describe, expect, test } from "bun:test";

import {
  hydrateResultActions,
  isVisibleResultAction,
} from "../lib/chat-result-actions";
import { resultCardFromConversationCard } from "../lib/argus-api";
import type { ChatActionOption } from "../components/chat/types";

describe("chat result actions", () => {
  test("hydrates only the supported visible result-card action set", () => {
    const actions: ChatActionOption[] = [
      {
        id: "explain-result",
        label: "Explain result",
        labelKey: "chat.result_card.explain_result",
        type: "show_breakdown",
        presentation: "result",
      },
      {
        id: "legacy-next-experiment",
        label: "Try next",
        type: "next_experiment" as ChatActionOption["type"],
        presentation: "result",
      },
      {
        id: "legacy-try-next",
        label: "Try next",
        type: "try_next" as ChatActionOption["type"],
        presentation: "result",
      },
      {
        id: "refine-idea",
        label: "Refine idea",
        type: "refine_strategy",
        presentation: "result",
      },
      {
        id: "save-strategy",
        label: "Save",
        type: "save_strategy",
        presentation: "result",
      },
    ];

    const hydrated = hydrateResultActions(actions, {
      runId: "run-1",
      conversationId: "conversation-1",
      strategyId: null,
      strategyName: "AAPL buy and hold",
      symbols: ["AAPL"],
    });

    expect(hydrated.map((action) => action.type)).toEqual([
      "show_breakdown",
      "refine_strategy",
      "save_strategy",
    ]);
    expect(hydrated[0]?.labelKey).toBe("chat.result_card.explain_result");
    expect(hydrated.map((action) => action.label)).not.toContain("Try next");
  });

  test("treats legacy next-step metadata as follow-up data, not visible card actions", () => {
    expect(
      isVisibleResultAction({
        label: "Try next",
        type: "next_experiment" as ChatActionOption["type"],
      }),
    ).toBe(false);
    expect(
      isVisibleResultAction({
        label: "Try next",
        type: "try_next" as ChatActionOption["type"],
      }),
    ).toBe(false);
    expect(
      isVisibleResultAction({
        label: "Explain result",
        type: "show_breakdown",
      }),
    ).toBe(true);
    expect(
      isVisibleResultAction({ label: "Refine idea", type: "refine_strategy" }),
    ).toBe(true);
    expect(
      isVisibleResultAction({ label: "Save", type: "save_strategy" }),
    ).toBe(true);
  });

  test("hydrates evidence and decision metadata without parsing display prose", () => {
    const card = resultCardFromConversationCard({
      title: "AAPL Buy and Hold",
      symbols: ["AAPL"],
      date_range: {
        start: "2025-01-01",
        end: "2025-12-31",
        display: "Jan 1, 2025 -> Dec 31, 2025",
      },
      status_label: "Simulation Complete",
      rows: [],
      assumptions: [],
      actions: [],
      evidence_artifact_id: "artifact-1",
      evidence_lifecycle: "decided",
      decision_note_id: "decision-1",
      decision_state: "promising",
    });

    expect(card.evidenceArtifactId).toBe("artifact-1");
    expect(card.evidenceLifecycle).toBe("decided");
    expect(card.decisionNoteId).toBe("decision-1");
    expect(card.decisionState).toBe("promising");
  });
});
