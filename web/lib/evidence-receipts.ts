import { apiFetch } from "./argus-api-transport";
import {
  publicReceiptPath,
  type PublicReceiptDateRange,
} from "./public-receipt-contract";
import type { PublicReceiptDocument, ReceiptKind, ReceiptRefusalField, ReceiptRefusalReason } from "./public-receipt-turns";

/** Mirrors PublicExcerptListItem. Carries no source id, by design. */
export type EvidenceReceipt = {
  id: string;
  public_id: string;
  path: string;
  title: string;
  symbols: string[];
  // Two dates, not a rendered string: the owner reads this row in whatever
  // language the app is in, which need not be the one the run was made in.
  date_range?: PublicReceiptDateRange | null;
  kind: ReceiptKind;
  created_at: string;
  revoked_at?: string | null;
  revocation_reason?: "owner_revoked" | "source_deleted" | "removed_by_argus" | null;
};

export const RECEIPT_OWNER_NOTE_MAX_LENGTH = 280;

export type ReceiptFailureReason =
  | "note_rejected"
  | "rate_limited"
  | "account_conversion_required"
  | "preview_changed"
  | "source_unsupported"
  | "unavailable";

export function receiptFailureReason(error: unknown): ReceiptFailureReason {
  const code = (error as { code?: string } | null)?.code;
  const status = (error as { status?: number } | null)?.status;
  if (code === "receipt_note_rejected") return "note_rejected";
  if (code === "account_conversion_required") return "account_conversion_required";
  if (code === "receipt_preview_changed") return "preview_changed";
  if (code === "receipt_source_unsupported") return "source_unsupported";
  if (status === 429) return "rate_limited";
  return "unavailable";
}

export type ReceiptCandidate = {
  message_id: string; question?: string | null; kind?: Exclude<ReceiptKind, "mixed"> | null;
  eligible: boolean; reason?: ReceiptRefusalReason | null; field?: ReceiptRefusalField | null;
};
export type ReceiptCandidates = { items: ReceiptCandidate[] };
export type ReceiptSelection = { message_ids: string[]; owner_note?: string | null };
export type ReceiptPreview = {
  payload: PublicReceiptDocument; payload_digest: string; kind: ReceiptKind; existing_receipt?: EvidenceReceipt | null;
};
const conversationReceiptPath = (conversationId: string) => `/conversations/${encodeURIComponent(conversationId)}/public-excerpt`;
export function listReceiptCandidates(conversationId: string): Promise<ReceiptCandidates> {
  return apiFetch(`${conversationReceiptPath(conversationId)}-candidates`);
}
export function previewEvidenceReceipt(conversationId: string, selection: ReceiptSelection): Promise<ReceiptPreview> {
  return apiFetch(`${conversationReceiptPath(conversationId)}-preview`, { method: "POST", body: JSON.stringify(selection) });
}
export async function createSelectedEvidenceReceipt(conversationId: string, selection: ReceiptSelection, payloadDigest: string): Promise<EvidenceReceipt> {
  const response = await apiFetch<{ receipt: EvidenceReceipt }>(conversationReceiptPath(conversationId), {
    method: "POST", body: JSON.stringify({ ...selection, payload_digest: payloadDigest }),
  });
  return response.receipt;
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
