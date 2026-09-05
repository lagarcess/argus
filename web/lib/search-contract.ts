import type { DecisionState, RunDossier } from "./run-dossier-contract";
import type { ConversationPreview } from "./conversation-preview-display";

export type SearchConversationItem = {
  type: "conversation";
  id: string;
  title: string;
  archived: boolean;
  matched_text: string;
  preview?: ConversationPreview | null;
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
