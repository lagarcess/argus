import { afterEach, expect, test } from "bun:test";
import {
  initialReceiptSelection, publishReceiptSelection, receiptSelectionReducer,
  type ReceiptSelectionState,
} from "../lib/receipt-selection";
import type { EvidenceReceipt, ReceiptPreview } from "../lib/evidence-receipts";
import { researchTurn, turnDocument } from "./fixtures/receipt-turns";

const originalFetch = globalThis.fetch;
const originalMock = process.env.NEXT_PUBLIC_MOCK_AUTH;
afterEach(() => { globalThis.fetch = originalFetch; process.env.NEXT_PUBLIC_MOCK_AUTH = originalMock; });

const receipt: EvidenceReceipt = {
  id: "existing", public_id: "abcdefghijklmnopqrstuvwx", path: "/r/abcdefghijklmnopqrstuvwx",
  kind: "research_answer", title: researchTurn.question, symbols: researchTurn.anchor_symbols, created_at: researchTurn.retrieved_at,
};
function previewState(existing: boolean): ReceiptSelectionState {
  const selected = receiptSelectionReducer(initialReceiptSelection, { type: "loaded", page: { max_turns: 4, items: [{ message_id: "answer", eligible: true }] }, messageId: "answer" });
  const preview: ReceiptPreview = { payload: turnDocument({ ...researchTurn, owner_note: "The frozen note" }), payload_digest: "a".repeat(64), kind: "research_answer", ...(existing ? { existing_receipt: receipt } : {}) };
  return receiptSelectionReducer(selected, { type: "previewed", revision: selected.revision, preview });
}

test.each([false, true])("publication revalidates the selected message and digest, existing=%s", async (existing) => {
  process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
  let state = previewState(existing);
  const preview = state.preview;
  const requests: { url: string; method?: string; body: unknown }[] = [];
  globalThis.fetch = (async (url, init) => {
    requests.push({ url: new URL(String(url)).pathname, method: init?.method, body: JSON.parse(String(init?.body)) });
    return Response.json({ receipt });
  }) as typeof fetch;
  const phases: string[] = [];
  await publishReceiptSelection("conversation", state, (action) => { state = receiptSelectionReducer(state, action); phases.push(state.phase); });
  expect(requests).toEqual([{ url: "/api/v1/conversations/conversation/public-excerpt", method: "POST", body: { message_ids: ["answer"], owner_note: null, payload_digest: preview!.payload_digest } }]);
  expect(phases).toEqual(["creating", "created"]);
  expect(state.receipt).toEqual(receipt);
  expect(state.preview).toBe(preview);
  expect(state.preview?.payload).toEqual(preview?.payload);
});

test.each([
  { status: 409, code: "receipt_preview_changed" },
  { status: 422, code: "receipt_source_unsupported", context: { reason: "invalid_source", field: "answer" } },
])("existing preview refuses success after final $code validation", async (failure) => {
  process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
  let state = previewState(true);
  let requests = 0;
  globalThis.fetch = (async () => { requests += 1; return Response.json(failure, { status: failure.status }); }) as typeof fetch;
  await publishReceiptSelection("conversation", state, (action) => { state = receiptSelectionReducer(state, action); });
  expect(requests).toBe(1);
  expect(state.phase).toBe("selecting");
  expect(state.receipt).toBeNull();
  expect(state.preview).toBeNull();
  expect(state.error).toMatchObject(failure);
});
