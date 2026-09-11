/**
 * Questions the model wrote for this conversation, offered to tap under an
 * answer about a result. They render only from the typed sidecar, and a tap
 * sends the question as an ordinary user turn.
 */

import type { ChatActionOption } from "@/components/chat/types";

export const SUGGESTED_QUESTIONS_VERSION = "argus_suggested_questions/v1";
const MAX_QUESTIONS = 3;

export function suggestedQuestionsFromMetadata(
  metadata: Record<string, unknown> | null | undefined,
): string[] | null {
  const sidecar = metadata?.suggested_questions;
  if (!sidecar || typeof sidecar !== "object" || Array.isArray(sidecar)) {
    return null;
  }
  const record = sidecar as Record<string, unknown>;
  if (
    record.version !== SUGGESTED_QUESTIONS_VERSION ||
    !Array.isArray(record.questions)
  ) {
    return null;
  }
  const questions = record.questions
    .map((question) => (typeof question === "string" ? question.trim() : ""))
    .filter((question) => question.length > 0)
    .slice(0, MAX_QUESTIONS);
  return questions.length > 0 ? questions : null;
}

/** Typeless: a typed option is validated against the latest turn and rejected as stale. */
export function suggestedQuestionAction(question: string): ChatActionOption {
  return { label: question, value: question };
}
