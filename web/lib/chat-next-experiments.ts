/**
 * Typed Try next rows for a completed result (issue #249).
 *
 * The backend's Stage-0 policy composes `next_experiments` metadata; a
 * tapped row sends its localized label as an ordinary conversational
 * turn (a type-less action takes the plain send path — the response-
 * option claim contract is for typed field edits, not experiments).
 * Rows render only from typed metadata — never inferred from prose.
 */

import type { ChatActionOption } from "@/components/chat/types";

export const NEXT_EXPERIMENTS_VERSION = "argus_next_experiments/v1";
const MAX_ROWS = 3;

export type NextExperimentReason = {
  code: string;
  params: Record<string, unknown>;
};

export type NextExperimentRow = {
  kind: string;
  label: string;
  labelKey: string;
  detail: string | null;
  sendText: string | null;
  why: NextExperimentReason | null;
};

function recordOrNull(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function rowOrNull(value: unknown): NextExperimentRow | null {
  const raw = recordOrNull(value);
  if (!raw) return null;
  const kind = typeof raw.kind === "string" ? raw.kind.trim() : "";
  const label = typeof raw.label === "string" ? raw.label.trim() : "";
  const labelKey = typeof raw.label_key === "string" ? raw.label_key.trim() : "";
  if (!kind || !label || !labelKey) return null;
  const why = recordOrNull(raw.why);
  const whyCode = why && typeof why.code === "string" ? why.code : "";
  const detail = typeof raw.detail === "string" ? raw.detail.trim() : "";
  const sendText = typeof raw.send_text === "string" ? raw.send_text.trim() : "";
  return {
    kind,
    label,
    labelKey,
    detail: detail || null,
    sendText: sendText || null,
    why: whyCode
      ? { code: whyCode, params: recordOrNull(why?.params) ?? {} }
      : null,
  };
}

export function nextExperimentRowsFromMetadata(
  metadata: Record<string, unknown>,
): NextExperimentRow[] | null {
  const sidecar = recordOrNull(metadata.next_experiments);
  if (!sidecar || sidecar.version !== NEXT_EXPERIMENTS_VERSION) return null;
  if (!Array.isArray(sidecar.rows)) return null;
  const rows = sidecar.rows
    .map(rowOrNull)
    .filter((row): row is NextExperimentRow => row !== null)
    .slice(0, MAX_ROWS);
  return rows.length > 0 ? rows : null;
}

export function nextExperimentAction(
  row: NextExperimentRow,
  localizedLabel?: string,
): ChatActionOption {
  // A prebaked row sends its fully specified ask; nothing is missing, so
  // the normal lifecycle answers with the next confirmation card.
  const send = row.sendText || localizedLabel || row.label;
  return {
    label: send,
    labelKey: row.sendText ? undefined : row.labelKey,
    value: send,
  };
}
