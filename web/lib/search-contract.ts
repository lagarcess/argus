import type { DecisionState, RunDossier } from "./run-dossier-contract";

export type SearchConversationItem = {
  type: "conversation";
  id: string;
  title: string;
  archived: boolean;
  matched_text: string;
  updated_at: string;
  conversation_id: string;
  match: {
    layer:
      "conversation" | "message" | "run" | "idea" | "evidence" | "decision";
    fragment: string;
    count: number;
    message_id?: string;
  };
  dossier: RunDossier | null;
  total_runs: number;
  decided_runs: number;
  decision_states: DecisionState[];
};
