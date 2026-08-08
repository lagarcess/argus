import { apiFetch } from "./argus-api-transport";
import { publicReceiptPath } from "./public-receipt-contract";

/** Mirrors PublicExcerptListItem. Carries no source id, by design. */
export type EvidenceReceipt = {
  id: string;
  public_id: string;
  path: string;
  title: string;
  symbols: string[];
  date_range_display: string;
  created_at: string;
  revoked_at?: string | null;
  revocation_reason?: "owner_revoked" | "source_deleted" | null;
};

export const RECEIPT_OWNER_NOTE_MAX_LENGTH = 280;

export type ReceiptFailureReason =
  | "note_rejected"
  | "rate_limited"
  | "unavailable";

export function receiptFailureReason(error: unknown): ReceiptFailureReason {
  const code = (error as { code?: string } | null)?.code;
  const status = (error as { status?: number } | null)?.status;
  if (code === "receipt_note_rejected") return "note_rejected";
  if (status === 429) return "rate_limited";
  return "unavailable";
}

export function receiptUrl(receipt: EvidenceReceipt): string {
  const path = receipt.path || publicReceiptPath(receipt.public_id);
  if (typeof window === "undefined") return path;
  return `${window.location.origin}${path}`;
}

export async function createEvidenceReceipt(
  artifactId: string,
  ownerNote: string | null,
): Promise<EvidenceReceipt> {
  const response = await apiFetch<{ receipt: EvidenceReceipt }>(
    `/evidence-artifacts/${encodeURIComponent(artifactId)}/public-excerpt`,
    {
      method: "POST",
      body: JSON.stringify({ owner_note: ownerNote || null }),
    },
  );
  return response.receipt;
}

export type EvidenceReceiptPage = {
  items: EvidenceReceipt[];
  next_cursor: string | null;
};

/**
 * Paginated, not capped. This list is the only place an owner can find a receipt
 * to revoke, so every one of them has to stay reachable.
 */
export async function listEvidenceReceipts(
  cursor?: string | null,
): Promise<EvidenceReceiptPage> {
  const query = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  const response = await apiFetch<{
    items: EvidenceReceipt[];
    next_cursor?: string | null;
  }>(`/public-excerpts${query}`);
  return { items: response.items, next_cursor: response.next_cursor ?? null };
}

export async function revokeEvidenceReceipt(
  receiptId: string,
): Promise<EvidenceReceipt> {
  const response = await apiFetch<{ receipt: EvidenceReceipt }>(
    `/public-excerpts/${encodeURIComponent(receiptId)}`,
    { method: "DELETE" },
  );
  return response.receipt;
}

/**
 * Copy link is the primary action. A native share sheet behaves inconsistently
 * across platforms and buries the url, which is the one thing the owner needs.
 */
export async function copyReceiptLink(url: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(url);
    return true;
  } catch {
    return false;
  }
}
