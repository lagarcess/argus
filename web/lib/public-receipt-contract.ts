import type { AssetClass } from "./argus-types";
import { ARGUS_API_BASE_URL } from "./argus-api-transport";

/**
 * Mirrors src/argus/api/public_excerpt_schemas.py. The payload is closed: this
 * type is the whole of what a receipt can ever show.
 */
export type PublicReceiptDateRange = {
  start: string;
  end: string;
  display: string;
};

export type PublicReceiptMetric = {
  key: string;
  label: string;
  value: string;
};

export type PublicReceiptVisualPoint = {
  time: string;
  value: number;
};

export type PublicReceiptVisual = {
  kind: "portfolio_equity";
  currency?: string | null;
  base_value?: number | null;
  series: PublicReceiptVisualPoint[];
};

export type PublicReceiptPayload = {
  schema_version: 1;
  idea_title: string;
  asset_class?: AssetClass | null;
  symbols: string[];
  strategy_label?: string | null;
  assumptions: string[];
  date_range: PublicReceiptDateRange;
  metrics: PublicReceiptMetric[];
  benchmark_symbol?: string | null;
  benchmark_note?: string | null;
  visual?: PublicReceiptVisual | null;
  owner_note?: string | null;
  content_language: "en" | "es-419";
  framing: "historical_simulation_not_advice";
  provenance_mark: "tested_with_argus";
};

export type PublicReceiptView = {
  public_id: string;
  status: "available" | "revoked";
  indexing: "noindex, nofollow";
  created_at?: string | null;
  payload?: PublicReceiptPayload | null;
};

export const PUBLIC_RECEIPT_PATH_PREFIX = "/r/";
export const PUBLIC_RECEIPT_MAX_ID_LENGTH = 64;

const PUBLIC_RECEIPT_ID_PATTERN = /^[A-Za-z0-9_-]{22,64}$/;

export function isPublicReceiptId(value: string): boolean {
  return PUBLIC_RECEIPT_ID_PATTERN.test(value);
}

export function publicReceiptPath(publicId: string): string {
  return `${PUBLIC_RECEIPT_PATH_PREFIX}${publicId}`;
}

/**
 * Three page states, not two. A revoked receipt is gone for good and says so; a
 * backend that cannot answer right now is a different, temporary thing, and
 * telling a viewer their link is dead when it is not would be a lie.
 */
export type PublicReceiptResult =
  | { kind: "available"; payload: PublicReceiptPayload; createdAt: string | null }
  | { kind: "revoked" }
  | { kind: "unavailable" };

/**
 * The only network call the public route makes. No credentials and no auth
 * header, so this request cannot carry an Argus session even by accident.
 */
export async function fetchPublicReceipt(
  publicId: string,
): Promise<PublicReceiptResult> {
  if (!isPublicReceiptId(publicId)) {
    return { kind: "revoked" };
  }
  try {
    const response = await fetch(
      `${ARGUS_API_BASE_URL}/public/receipts/${encodeURIComponent(publicId)}`,
      {
        headers: { Accept: "application/json" },
        cache: "no-store",
      },
    );
    if (response.status === 404 || response.status === 410) {
      return { kind: "revoked" };
    }
    if (!response.ok) {
      return { kind: "unavailable" };
    }
    const view = (await response.json()) as PublicReceiptView;
    if (view.status !== "available" || !view.payload) {
      return { kind: "revoked" };
    }
    return {
      kind: "available",
      payload: view.payload,
      createdAt: view.created_at ?? null,
    };
  } catch {
    return { kind: "unavailable" };
  }
}

export function headlineReceiptMetric(
  payload: PublicReceiptPayload,
): PublicReceiptMetric | null {
  const preferred = ["total_return_pct", "delta_vs_benchmark_pct", "total_return"];
  for (const key of preferred) {
    const match = payload.metrics.find((metric) => metric.key === key);
    if (match) return match;
  }
  return payload.metrics[0] ?? null;
}
