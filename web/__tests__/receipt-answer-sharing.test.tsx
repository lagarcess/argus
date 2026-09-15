import { test } from "bun:test";
import assert from "node:assert/strict";
import { renderToStaticMarkup } from "react-dom/server";
import ReceiptBody from "../components/receipt/ReceiptBody";
import { receiptCopy } from "../lib/receipt-copy";
import { receiptDocumentSupported, type PublicReceiptDocument } from "../lib/public-receipt-turns";
import { backtestTurn, researchTurn } from "./fixtures/receipt-turns";

for (const language of ["en", "es-419"] as const) {
  test(`plain answers and complete backtest prose survive the exact preview in ${language}`, () => {
    const answer = "The result includes modeled costs. ".repeat(150);
    const payload = { schema_version: 2, kind: "turns", turns: [
      { kind: "answer", question: "What do those costs mean?", answer, content_language: language, framing: "answer_not_advice", provenance_mark: "tested_with_argus" },
      { ...backtestTurn, question: "Test monthly contributions", answer: "**Quick take:** the contributions grew." },
    ] } as PublicReceiptDocument;
    assert.equal(receiptDocumentSupported(payload), true);
    const markup = renderToStaticMarkup(<ReceiptBody payload={payload} createdAt={null} copy={receiptCopy(language)} language={language} preview />);
    assert.ok(markup.includes(answer.trim()));
    assert.ok(markup.includes("Test monthly contributions"));
    assert.ok(markup.includes("Quick take:"));
  });
}

for (const language of ["en", "es-419"] as const) {
  for (const mixed of [false, true]) {
    test(`public ${mixed ? "mixed" : "plain"} answer footer does not invent dated research in ${language}`, () => {
      const answer = { kind: "answer", question: "What does diversification mean?", answer: "Spreading money across investments.", content_language: language, framing: "answer_not_advice", provenance_mark: "tested_with_argus" } as const;
      const payload: PublicReceiptDocument = { schema_version: 2, kind: "turns", turns: mixed ? [answer, backtestTurn] : [answer] };
      const copy = receiptCopy(language);
      const markup = renderToStaticMarkup(<ReceiptBody payload={payload} createdAt={null} copy={copy} language={language} />);
      assert.ok(!markup.includes(copy.research.headline));
    });
  }
}

for (const language of ["en", "es-419"] as const) {
  test(`public research receipts retain dated research framing in ${language}`, () => {
    const payload: PublicReceiptDocument = { schema_version: 2, kind: "turns", turns: [{ ...researchTurn, content_language: language }] };
    const copy = receiptCopy(language);
    const markup = renderToStaticMarkup(<ReceiptBody payload={payload} createdAt={null} copy={copy} language={language} />);
    assert.ok(markup.includes(copy.research.framing));
    assert.ok(!markup.includes(copy.answer.headline));
  });
}
