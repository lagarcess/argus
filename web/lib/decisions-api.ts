import { apiFetch } from "./argus-api-transport";
import type {
  DecisionAttachment,
  DecisionNote,
  DecisionOpenResponse,
} from "./decision-contract";
import type { DecisionState } from "./run-dossier-contract";

export type DecisionDraftPayload = {
  decision_state: DecisionState;
  note?: string | null;
};

/** Record or update the current decision on a computed answer. */
export async function createMessageDecision(
  conversationId: string,
  messageId: string,
  payload: DecisionDraftPayload,
): Promise<{ decision: DecisionNote }> {
  return apiFetch<{ decision: DecisionNote }>(
    `/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}/decision`,
    { method: "POST", body: JSON.stringify(payload) },
  );
}

/**
 * Save a decision wherever it attaches. A backtest decision keeps the
 * evidence-artifact route; a computed answer uses the message route.
 */
export async function saveDecision(
  attachment: DecisionAttachment,
  payload: DecisionDraftPayload,
): Promise<{ decision: DecisionNote }> {
  if (attachment.kind === "evidence_artifact") {
    return apiFetch<{ decision: DecisionNote }>(
      `/evidence-artifacts/${encodeURIComponent(attachment.artifactId)}/decision`,
      { method: "POST", body: JSON.stringify(payload) },
    );
  }
  return createMessageDecision(
    attachment.conversationId,
    attachment.messageId,
    payload,
  );
}

/** Open a decision: the backend re-runs its computation from the stored inputs. */
export async function openDecision(
  decisionId: string,
): Promise<DecisionOpenResponse> {
  return apiFetch<DecisionOpenResponse>(
    `/decisions/${encodeURIComponent(decisionId)}`,
  );
}

/** Re-run a decision's computation with input overrides; the decision is unchanged. */
export async function rerunDecision(
  decisionId: string,
  inputs: Record<string, unknown>,
): Promise<DecisionOpenResponse> {
  return apiFetch<DecisionOpenResponse>(
    `/decisions/${encodeURIComponent(decisionId)}/rerun`,
    { method: "POST", body: JSON.stringify({ inputs }) },
  );
}
