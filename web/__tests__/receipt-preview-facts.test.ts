import { expect, test } from "bun:test";
import { receiptPreviewFacts } from "../lib/receipt-preview-facts";
import { receiptCopy, interpolate, formatReceiptDate } from "../lib/receipt-copy";
import { backtestTurn, legacyReceipt, researchTurn, turnDocument } from "./fixtures/receipt-turns";

test.each(["en", "es-419"] as const)("research metadata uses the frozen first turn in %s", (language) => {
  const facts = receiptPreviewFacts(turnDocument(researchTurn, backtestTurn), language);
  expect(facts.title).toBe(researchTurn.question);
  expect(facts.metricValue).toBe("");
  expect(facts.description).toContain(interpolate(receiptCopy(language).research.preview_stamp, { date: formatReceiptDate(researchTurn.retrieved_at, language)!, count: researchTurn.sources.length }));
  expect(facts.description).toContain(interpolate(receiptCopy(language).selection.turns, { count: 2 }));
  expect(facts.description).not.toContain(researchTurn.answer);
});

test("v1 image keeps the frozen metric value", () => {
  expect(receiptPreviewFacts(legacyReceipt, "en").metricValue).toBe(legacyReceipt.metrics[0].value);
});
