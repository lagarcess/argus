import { describe, expect, test } from "bun:test";

import {
  hydrateResultActions,
  isVisibleResultAction,
} from "../lib/chat-result-actions";
import type { ChatActionOption } from "../components/chat/types";

describe("chat result actions", () => {
  test("hydrates only the supported visible result-card action set", () => {
    const actions: ChatActionOption[] = [
      {
        id: "explain-result",
        label: "Explain result",
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
    expect(isVisibleResultAction({ label: "Explain result", type: "show_breakdown" })).toBe(
      true,
    );
    expect(isVisibleResultAction({ label: "Refine idea", type: "refine_strategy" })).toBe(
      true,
    );
    expect(isVisibleResultAction({ label: "Save", type: "save_strategy" })).toBe(true);
  });
});
