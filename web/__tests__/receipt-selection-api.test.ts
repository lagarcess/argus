import { afterEach, expect, test } from "bun:test";
import * as receipts from "../lib/evidence-receipts";
import { fetchPublicReceipt } from "../lib/public-receipt-contract";
import { pendingGuestActionSummary, SingleUseGuestAction, verifiedClaimAction } from "../lib/guest-conversion";
import { researchTurn, turnDocument } from "./fixtures/receipt-turns";

const originalFetch = globalThis.fetch;
const originalMock = process.env.NEXT_PUBLIC_MOCK_AUTH;
afterEach(() => { globalThis.fetch = originalFetch; process.env.NEXT_PUBLIC_MOCK_AUTH = originalMock; });

test("preserves named source refusal context through the authenticated transport", async () => {
  process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
  const context = { reason: "unlisted_url", field: "answer" };
  globalThis.fetch = (async () => Response.json({ code: "receipt_source_unsupported", context, detail: "Cannot share" }, { status: 422 })) as typeof fetch;
  let failure;
  try { await receipts.createEvidenceReceipt("unused", null); } catch (error) { failure = error; }
  expect(failure).toMatchObject({ code: "receipt_source_unsupported", status: 422, context });
});

test("reports conversion and stale preview honestly", () => {
  expect(receipts.receiptFailureReason({ code: "account_conversion_required", status: 403 })).toBe("account_conversion_required");
  expect(receipts.receiptFailureReason({ code: "receipt_preview_changed", status: 409 })).toBe("preview_changed");
});

test("guest sharing carries the canonical message identity", () => {
  expect(pendingGuestActionSummary({ reason: "share_result", conversationId: "conversation", messageId: "message", actionId: "action" })).toEqual({ reason: "share_result", conversation_id: "conversation", message_id: "message", action_id: "action" });
});

test("guest sharing resumes the verified message once and rejects a changed message", () => {
  const action = { reason: "share_result" as const, conversationId: "conversation", messageId: "message", actionId: "action" };
  const claim = { conversation_id: action.conversationId, pending_action: pendingGuestActionSummary(action) };
  const latch = new SingleUseGuestAction(action);
  expect(verifiedClaimAction(claim, action.conversationId, latch)).toEqual(action);
  expect(verifiedClaimAction(claim, action.conversationId, latch)).toBeNull();
  expect(() => verifiedClaimAction({ ...claim, pending_action: { ...claim.pending_action, message_id: "different" } }, action.conversationId, new SingleUseGuestAction(action))).toThrow("pending action could not be verified");
});

test("unknown public document versions fail closed", async () => {
  globalThis.fetch = (async () => Response.json({ status: "available", payload: { schema_version: 99 } })) as typeof fetch;
  expect(await fetchPublicReceipt("abcdefghijklmnopqrstuvwx")).toEqual({ kind: "unavailable" });
});

test("header selection and answer shortcut use the same message preview and creation contract", async () => {
  process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
  const seen: { url: string; method: string; body: unknown }[] = [];
  const receipt: receipts.EvidenceReceipt = { id: "receipt", public_id: "abcdefghijklmnopqrstuvwx", path: "/r/abcdefghijklmnopqrstuvwx", title: researchTurn.question, symbols: researchTurn.anchor_symbols, kind: "research_answer", created_at: researchTurn.retrieved_at };
  const preview: receipts.ReceiptPreview = { payload: turnDocument(researchTurn), payload_digest: "b".repeat(64), kind: "research_answer" };
  globalThis.fetch = (async (url, init) => {
    seen.push({ url: String(url), method: init?.method ?? "GET", body: init?.body ? JSON.parse(String(init.body)) : null });
    return Response.json(String(url).endsWith("-candidates") ? { items: [], max_turns: 4 } : String(url).endsWith("-preview") ? preview : { receipt });
  }) as typeof fetch;
  await receipts.listReceiptCandidates("conversation");
  const selection = { message_ids: ["message"], owner_note: "A note" };
  expect(await receipts.previewEvidenceReceipt("conversation", selection)).toEqual(preview);
  expect(await receipts.createSelectedEvidenceReceipt("conversation", selection, preview.payload_digest)).toEqual(receipt);
  expect(seen.map((request) => ({ ...request, url: new URL(request.url).pathname }))).toEqual([
    { url: "/api/v1/conversations/conversation/public-excerpt-candidates", method: "GET", body: null },
    { url: "/api/v1/conversations/conversation/public-excerpt-preview", method: "POST", body: selection },
    { url: "/api/v1/conversations/conversation/public-excerpt", method: "POST", body: { ...selection, payload_digest: preview.payload_digest } },
  ]);
});
