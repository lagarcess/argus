import type { DecisionState } from "./run-dossier-contract";

/** The decision a computed answer offers; it posts to the message route. */
export type AnswerDecisionAction = {
  type: "answer_decision";
  availability: "available" | "account_conversion_required";
  message_id: string;
  decision_state: DecisionState | null;
  note: string | null;
};

/**
 * A computed answer's dossier beside the run dossier: what was asked, one
 * card per calculation with what Argus used and what came out, the decision,
 * and recompute through the message computation route. The run dossier is
 * unchanged.
 */
export type AnswerDossier = {
  message_id: string;
  conversation_id: string;
  asked: string | null;
  computed_at: string;
  symbols: string[];
  /** 1 to 4 tool result cards, one per calculation, in marker order. */
  cards: Record<string, unknown>[];
  decision: { state: DecisionState; note: string | null; run_label?: string | null } | null;
  decision_id: string | null;
  actions: AnswerDecisionAction[];
};
