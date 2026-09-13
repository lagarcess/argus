/**
 * One ordered list of next steps under an answer (argus_next_steps/v1).
 *
 * A test step resolves to the message's typed Try next row and runs exactly as
 * that row does; a question step sends its text as an ordinary turn. A message
 * without the list offers its Try next rows alone. Steps render only from
 * typed metadata, never inferred from prose.
 */

import type { ChatActionOption } from "@/components/chat/types";
import type { NextExperimentRow } from "@/lib/chat-next-experiments";

export const NEXT_STEPS_VERSION = "argus_next_steps/v1";
const MAX_STEPS = 5;

export type NextStep =
  | { type: "test"; row: NextExperimentRow }
  | { type: "question"; text: string };

function stepOrNull(
  value: unknown,
  rowsByKind: Map<string, NextExperimentRow>,
): NextStep | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const item = value as Record<string, unknown>;
  if (item.type === "test" && typeof item.kind === "string") {
    const row = rowsByKind.get(item.kind);
    return row ? { type: "test", row } : null;
  }
  if (item.type === "question" && typeof item.text === "string") {
    const text = item.text.trim();
    return text ? { type: "question", text } : null;
  }
  return null;
}

export function nextStepsFromMetadata(
  metadata: Record<string, unknown> | null | undefined,
  rows: NextExperimentRow[] | null | undefined,
): NextStep[] | null {
  const sidecar = metadata?.next_steps;
  if (!sidecar || typeof sidecar !== "object" || Array.isArray(sidecar)) {
    return null;
  }
  const record = sidecar as Record<string, unknown>;
  if (record.version !== NEXT_STEPS_VERSION || !Array.isArray(record.items)) {
    return null;
  }
  const rowsByKind = new Map((rows ?? []).map((row) => [row.kind, row]));
  const seen = new Set<string>();
  const steps: NextStep[] = [];
  for (const entry of record.items) {
    const step = stepOrNull(entry, rowsByKind);
    if (!step) continue;
    const identity =
      step.type === "test" ? `test:${step.row.kind}` : `question:${step.text}`;
    if (seen.has(identity)) continue;
    seen.add(identity);
    steps.push(step);
  }
  return steps.length > 0 ? steps.slice(0, MAX_STEPS) : null;
}

/** The list a message shows: its ordered steps, or its Try next rows alone. */
export function messageNextSteps(message: {
  nextSteps?: NextStep[] | null;
  nextExperiments?: NextExperimentRow[] | null;
}): NextStep[] {
  if (message.nextSteps && message.nextSteps.length > 0) {
    return message.nextSteps;
  }
  return (message.nextExperiments ?? []).map((row) => ({ type: "test", row }));
}

/** Typeless: a typed option is validated against the latest turn and rejected as stale. */
export function nextStepQuestionAction(text: string): ChatActionOption {
  return { label: text, value: text };
}
