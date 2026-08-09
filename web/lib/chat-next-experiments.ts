/**
 * Typed Try next rows for a completed result (issue #249).
 *
 * The backend's Stage-0 policy composes `next_experiments` metadata; a
 * Most rows send their localized label as an ordinary conversational turn.
 * The two issue-345 continuity rows carry a typed refine action anchored to
 * the source run, so their labels remain presentation rather than semantics.
 * Rows render only from typed metadata — never inferred from prose.
 */

import type { ChatActionOption } from "@/components/chat/types";

export const NEXT_EXPERIMENTS_VERSION = "argus_next_experiments/v1";
const MAX_ROWS = 3;
const CONTINUITY_KINDS = new Set([
  "change_date_range",
  "compare_buy_and_hold",
]);

export type NextExperimentReason = {
  code: string;
  params: Record<string, unknown>;
};

export type NextExperimentRow = {
  kind: string;
  label: string;
  labelKey: string;
  /** Backend-composed short form for narrow screens; the client never clips. */
  labelShort: string | null;
  labelShortKey: string | null;
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
  const labelShort =
    typeof raw.label_short === "string" ? raw.label_short.trim() : "";
  const labelShortKey =
    typeof raw.label_short_key === "string" ? raw.label_short_key.trim() : "";
  return {
    kind,
    label,
    labelKey,
    labelShort: labelShort || null,
    labelShortKey: labelShortKey || null,
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

const RESEARCH_ADD_PEER_KIND_PREFIX = "research_add_peer";

export function nextExperimentAction(
  row: NextExperimentRow,
  localizedLabel?: string,
  sourceRunId?: string,
): ChatActionOption {
  if (row.kind.startsWith(RESEARCH_ADD_PEER_KIND_PREFIX)) {
    // No turn is spent: the typed endpoint patches the pending card with the
    // resolver-verified symbols the row's why payload carries.
    const symbols = Array.isArray(row.why?.params?.symbols)
      ? (row.why?.params?.symbols as unknown[]).map((symbol) => String(symbol))
      : [];
    return {
      label: localizedLabel || row.label,
      type: "add_confirmation_peer",
      payload: { symbols },
    };
  }
  // A prebaked row sends its fully specified ask; nothing is missing, so
  // the normal lifecycle answers with the next confirmation card.
  const send = row.sendText || localizedLabel || row.label;
  const runId = sourceRunId?.trim();
  if (runId && CONTINUITY_KINDS.has(row.kind)) {
    return {
      label: send,
      labelKey: row.sendText ? undefined : row.labelKey,
      value: send,
      type: "refine_strategy",
      presentation: "result",
      payload: {
        run_id: runId,
        next_experiment_kind: row.kind,
      },
    };
  }
  return {
    label: send,
    labelKey: row.sendText ? undefined : row.labelKey,
    value: send,
  };
}
