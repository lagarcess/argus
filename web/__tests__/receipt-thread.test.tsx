import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import ReceiptBody from "../components/receipt/ReceiptBody";
import ReceiptTurnContent from "../components/receipt/ReceiptTurnContent";
import { receiptPresentations } from "../lib/receipt-presentation";
import { formatReceiptDate, receiptCopy } from "../lib/receipt-copy";
import type { CalculationReceiptTurn, PublicReceiptDocument } from "../lib/public-receipt-turns";
import { backtestTurn, researchTurn } from "./fixtures/receipt-turns";

const calculation = JSON.parse(readFileSync(new URL("./fixtures/calculation-cards.json", import.meta.url), "utf8")).receipt_turn as CalculationReceiptTurn;
const createdAt = "2026-09-14T12:00:00Z";
const plain = { kind: "answer", question: "What does diversification mean?", answer: "Spreading money across investments.", content_language: "en", framing: "answer_not_advice", provenance_mark: "tested_with_argus" } as const;
const payload: PublicReceiptDocument = { schema_version: 2, kind: "turns", turns: [
  { ...backtestTurn, question: "Test monthly contributions", answer: "Contributions grew after modeled costs." },
  { ...researchTurn, owner_note: backtestTurn.owner_note }, calculation, plain,
] };

describe.each(["en", "es-419"] as const)("shared conversation in %s", (language) => {
  const props = { payload, createdAt, language, copy: receiptCopy(language) };
  test("renders every selected question and answer as a dated read-only chat turn", () => {
    const markup = renderToStaticMarkup(<ReceiptBody {...props} />);
    expect(markup.match(/data-receipt-question=""/g)).toHaveLength(payload.turns.length);
    expect(markup.match(/data-receipt-answer=""/g)).toHaveLength(payload.turns.length);
    expect(markup).toContain(formatReceiptDate(createdAt, language)!);
    for (const turn of payload.turns) expect(markup).toContain(turn.question!);
    expect(markup).toContain("Contributions grew after modeled costs.");
    expect(markup).toContain("<strong>Revenue increased.</strong>");
    expect(markup).toContain("Spreading money across investments.");
    expect(markup).toContain('href="https://www.apple.com/newsroom/"');
    expect(markup).toContain("250");
    expect(markup).not.toContain("—");
    expect(markup).not.toContain('href="/"');
  });
  test("puts the owner's note once above the first question", () => {
    const markup = renderToStaticMarkup(<ReceiptBody {...props} />);
    expect(markup.split(backtestTurn.owner_note!).length - 1).toBe(1);
    expect(markup.indexOf(backtestTurn.owner_note!)).toBeLessThan(markup.indexOf("data-receipt-question"));
  });
  test("preview and public reading use identical thread and follow-up layout", () => {
    const publicMarkup = renderToStaticMarkup(<ReceiptBody {...props} />);
    const previewMarkup = renderToStaticMarkup(<ReceiptBody {...props} preview />);
    expect(publicMarkup).toEqual(previewMarkup);
    expect(previewMarkup.match(/<textarea/g)).toHaveLength(1);
    expect(previewMarkup).toContain('disabled=""');
    expect(previewMarkup).not.toContain('<input');
  });
  test("carried cards render facts without duplicating the question, prose or owner note", () => {
    const [entry] = receiptPresentations(payload, createdAt, language);
    const markup = renderToStaticMarkup(<ReceiptTurnContent entry={entry} copy={props.copy} language={language} includeAnswer={false} />);
    expect(markup).toContain("250");
    expect(markup).toContain(props.copy.thread.read_only);
    expect(markup).not.toContain(entry.title);
    expect(markup).not.toContain(entry.answer!);
    expect(markup).not.toContain(entry.ownerNote!);
    expect(markup).not.toContain("<button");
    expect(markup).not.toContain("<input");
  });
  test("renders the receiver composer in the shared footer slot", () => {
    const markup = renderToStaticMarkup(<ReceiptBody {...props} footer={<form aria-label="Receiver follow-up"><textarea /></form>} />);
    expect(markup).toContain('aria-label="Receiver follow-up"');
    expect(markup.match(/<textarea/g)).toHaveLength(1);
  });
});
