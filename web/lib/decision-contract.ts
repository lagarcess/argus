import type { DecisionState, SearchRetestAction } from "./run-dossier-contract";

/** What a decision can re-run: a registered kind and its typed inputs. */
export type DecisionComputation = {
  kind: string;
  inputs: Record<string, unknown>;
};

export type DecisionRerunStatus =
  | "computed"
  | "confirmation_required"
  | "unavailable";

export type DecisionRerunReasonCode =
  | "kernel_unavailable"
  | "invalid_inputs"
  | "inputs_not_editable"
  | "run_unavailable"
  | "retest_unavailable";

export type DecisionRerun = {
  kind: string;
  inputs: Record<string, unknown>;
  status: DecisionRerunStatus;
  result: Record<string, unknown> | null;
  retest: SearchRetestAction | null;
  reason_code: DecisionRerunReasonCode | null;
};

/**
 * A decision attaches to exactly one owner: a backtest's evidence artifact
 * (the ids travel together and `computation` is null), or a computed answer's
 * message (the ids are null and `computation` is stored).
 */
export type DecisionNote = {
  id: string;
  idea_id: string | null;
  idea_version_id: string | null;
  evidence_artifact_id: string | null;
  source_conversation_id?: string | null;
  source_message_id: string | null;
  computation: DecisionComputation | null;
  decision_state: DecisionState;
  note?: string | null;
  created_at: string;
  updated_at: string;
};

export type DecisionOpenResponse = {
  decision: DecisionNote;
  computation: DecisionComputation;
  rerun: DecisionRerun;
};

/** Where a decision affordance posts: the artifact route or the message route. */
export type DecisionAttachment =
  | { kind: "evidence_artifact"; artifactId: string }
  | { kind: "message"; conversationId: string; messageId: string };

const COMPUTATION_KIND = /^[a-z][a-z0-9_]*$/;

/**
 * The typed computation an assistant message declared under
 * `metadata.computation`, or null. The backend validates the same shape
 * before it records a decision; the client only decides whether to offer one.
 */
export function decisionComputationFromMetadata(
  metadata: Record<string, unknown> | null | undefined,
): DecisionComputation | null {
  const raw = metadata?.computation;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const { kind, inputs } = raw as { kind?: unknown; inputs?: unknown };
  if (typeof kind !== "string" || !COMPUTATION_KIND.test(kind)) return null;
  if (inputs !== undefined && (typeof inputs !== "object" || inputs === null || Array.isArray(inputs))) {
    return null;
  }
  return {
    kind,
    inputs: (inputs as Record<string, unknown> | undefined) ?? {},
  };
}

const DECISION_STATES: readonly DecisionState[] = [
  "watching",
  "promising",
  "rejected",
  "revisit_later",
];

/** A backend-stamped decision state, or null for anything else. */
export function decisionStateFromValue(value: unknown): DecisionState | null {
  return typeof value === "string" &&
    (DECISION_STATES as readonly string[]).includes(value)
    ? (value as DecisionState)
    : null;
}
