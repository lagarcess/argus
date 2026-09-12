/**
 * Computed answers outside a chat turn: listed, compared, continued and
 * refreshed. Every figure and every difference is computed by the backend;
 * the web only formats what it receives.
 */
import type { DecisionComputation, DecisionRerun } from "./decision-contract";

type ComputationText = { locale_key: string; interpolation_args: Record<string, string | number | boolean | null> };

export type ComputedAnswerRef = { conversation_id: string; message_id: string };
export type ComputedAnswerSummary = {
  conversation_id: string; message_id: string; kind: string; asked: string | null; computed_at: string; symbols: string[];
};
export type ComparedAnswer = {
  conversation_id: string; message_id: string; asked: string | null; computed_at: string; card: Record<string, unknown>;
};
export type ComputationDifference = {
  section: "answer" | "row" | "input"; name: string; label: ComputationText; unit: ComputationText | null;
  left: number; right: number; difference: number;
};
export type ComputationComparison = { kind: string; left: ComparedAnswer; right: ComparedAnswer; differences: ComputationDifference[] };
export type ContinuedResult = { conversation: { id: string; title: string }; message_id: string };
export type ComputationRefresh = {
  computation: DecisionComputation; status: "refreshed" | "inputs_not_found"; rerun: DecisionRerun | null; sources: Record<string, unknown>[];
};
export type ContinuedFrom = { conversationId: string; messageId: string };

/** The source of a result continued in a new chat, read from backend metadata only. */
export function continuedFromMetadata(metadata: Record<string, unknown> | null | undefined): ContinuedFrom | null {
  const raw = metadata?.continued_from;
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  const { conversation_id: conversationId, message_id: messageId } = raw as Record<string, unknown>;
  return typeof conversationId === "string" && conversationId && typeof messageId === "string" && messageId
    ? { conversationId, messageId }
    : null;
}
