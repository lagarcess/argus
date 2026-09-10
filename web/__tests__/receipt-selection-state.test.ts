import { describe, expect, test } from "bun:test";
import { initialReceiptSelection, receiptSelectionReducer, selectAllEligibleAvailable, receiptRefusalText } from "../lib/receipt-selection";
import { receiptCopy } from "../lib/receipt-copy";
import type { ReceiptCandidates, ReceiptPreview } from "../lib/evidence-receipts";
import { researchTurn, turnDocument } from "./fixtures/receipt-turns";

function candidates(count: number, max = 4): ReceiptCandidates {
  return { max_turns: max, items: Array.from({ length: count }, (_, i) => ({ message_id: `message-${i}`, question: `Question ${i}`, eligible: i !== 0, reason: i === 0 ? "memory_used" : null, kind: "research_answer" })) };
}
const preview: ReceiptPreview = { payload: turnDocument(researchTurn), payload_digest: "a".repeat(64), kind: "research_answer" };

test("select all never silently truncates eligible answers to the cap", () => {
  const page = candidates(6);
  const state = receiptSelectionReducer(initialReceiptSelection, { type: "loaded", page });
  expect(selectAllEligibleAvailable(page)).toBe(false);
  expect(receiptSelectionReducer(state, { type: "select_all" }).selected).toEqual([]);
});

test("server cap and eligibility govern every selection operation", () => {
  const page = candidates(4, 2);
  let state = receiptSelectionReducer(initialReceiptSelection, { type: "loaded", page, messageId: "message-1" });
  state = receiptSelectionReducer(state, { type: "toggle", messageId: "message-0" });
  expect(state.selected).toEqual(["message-1"]);
  state = receiptSelectionReducer(state, { type: "toggle", messageId: "message-2" });
  state = receiptSelectionReducer(state, { type: "toggle", messageId: "message-3" });
  expect(state.selected).toEqual(["message-1", "message-2"]);
});

test("select all includes all eligible turns and excludes unsupported ones", () => {
  const state = receiptSelectionReducer(initialReceiptSelection, { type: "loaded", page: candidates(4) });
  expect(selectAllEligibleAvailable(state.page)).toBe(true);
  expect(receiptSelectionReducer(state, { type: "select_all" }).selected).toEqual(["message-1", "message-2", "message-3"]);
});

test.each(["note", "toggle", "clear", "select_all"] as const)("%s invalidates preview and discards a late response", (type) => {
  let state = receiptSelectionReducer(initialReceiptSelection, { type: "loaded", page: candidates(3), messageId: "message-1" });
  const revision = state.revision;
  state = receiptSelectionReducer(state, { type: "previewed", preview, revision });
  expect(state.preview).toBe(preview);
  state = receiptSelectionReducer(state, type === "note" ? { type, note: "Updated note" } : type === "toggle" ? { type, messageId: "message-2" } : { type });
  expect(state.preview).toBeNull();
  expect(receiptSelectionReducer(state, { type: "previewed", preview, revision }).preview).toBeNull();
});

describe.each(["en", "es-419"] as const)("localized refusals in %s", (language) => {
  test("every backend reason and field has readable copy", () => {
    const copy = receiptCopy(language);
    for (const [reason, text] of Object.entries(copy.selection.reasons)) {
      for (const [field, label] of Object.entries(copy.selection.fields)) {
        const message = receiptRefusalText({ reason, field }, copy);
        expect(message).toContain(text);
        expect(message).toContain(label);
        expect(message).not.toContain("{{");
      }
    }
  });
});
