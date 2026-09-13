import type { ApiMessage } from "../../lib/argus-api";
import type { ToolResultCard } from "../../lib/tool-result-card";

// Test-only typed echo presentation, never a product calculator.
export function toolCardFixture(overrides: Partial<ToolResultCard> = {}): ToolResultCard {
  return {
    kind: "tool_result", schema_version: 1, tool_name: "test_echo", call_id: "call-1",
    artifact_id: "artifact-1", input_revision: 0, card_type: "test_echo", card_version: 1,
    artifact_state: "active", arguments: { known: 0, unknown: null },
    outcome: { status: "succeeded", result: { value: 0 }, failure: null },
    presentation: {
      title: { locale_key: "tools.card.title", interpolation_args: {} },
      answer: { name: "answer", label: { locale_key: "tools.card.solved_value", interpolation_args: {} }, value: 0, unit: null },
      rows: [], notes: [],
      inputs: [
        { name: "known", label: { locale_key: "tools.card.input", interpolation_args: {} }, value: 0, unit: null, editable: true, unknown: false, visibility: "public" },
        { name: "unknown", label: { locale_key: "tools.card.solved_value", interpolation_args: {} }, value: null, unit: null, editable: false, unknown: true, visibility: "public" },
      ],
    },
    ...overrides,
  };
}

export function toolMessageFixture(cards: ToolResultCard[]): ApiMessage {
  return { id: "tool-message", conversation_id: "conversation-alpha", role: "assistant", content: "", created_at: "2026-09-09T15:10:00Z", metadata: { tool_result_cards: cards } };
}
