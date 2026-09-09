import { describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";
import ReceiptBody from "../components/receipt/ReceiptBody";
import { receiptCopy } from "../lib/receipt-copy";
import { receiptPresentations } from "../lib/receipt-presentation";
import { receiptTranslator } from "../lib/receipt-copy";
import { formatCurrency } from "../lib/result-card-display";
import type { ResearchReceiptTurn } from "../lib/public-receipt-turns";
import { legacyReceipt, researchTurn, backtestTurn, turnDocument } from "./fixtures/receipt-turns";

describe.each(["en", "es-419"] as const)("receipt body in %s", (language) => {
  test("preserves the complete v1 main markup", () => {
    const markup = renderToStaticMarkup(<ReceiptBody payload={legacyReceipt} createdAt="2026-09-09T14:32:00Z" language={language} copy={receiptCopy(language)} />);
    expect(markup.match(/<main[\s\S]*<\/main>/)?.[0]).toMatchSnapshot();
  });

  test("renders the exact selected research and backtest content with one public action", () => {
    const markup = renderToStaticMarkup(<ReceiptBody payload={turnDocument(researchTurn, backtestTurn)} createdAt="2026-09-09T14:32:00Z" language={language} copy={receiptCopy(language)} />);
    expect(markup).toContain(researchTurn.question);
    expect(markup).toContain("<strong>Revenue increased.</strong>");
    expect(markup).toContain('lang="en"');
    expect(markup).toContain('href="https://www.apple.com/newsroom/"');
    expect(markup).toContain(backtestTurn.idea_title);
    expect(markup).toContain("250");
    expect(markup).toContain("10");
    expect(markup.match(/href="\/"/g)).toHaveLength(1);
    expect(markup.match(/<main/g)).toHaveLength(1);
  });

  test("owner preview suppresses public actions", () => {
    const markup = renderToStaticMarkup(<ReceiptBody payload={turnDocument(researchTurn)} createdAt={null} language={language} copy={receiptCopy(language)} preview />);
    expect(markup).toContain(researchTurn.question);
    expect(markup).not.toContain('href="/"');
  });

  test("the typed starting principal survives without a private chart or card prose", () => {
    const capital = 1300;
    const turn = { ...backtestTurn, fact_bank: { ...backtestTurn.fact_bank, config_snapshot: { template: "buy_and_hold", starting_capital: capital } } };
    const presentation = receiptPresentations({ schema_version: 2, kind: "turns", turns: [turn] }, null, language)[0];
    const expected = receiptTranslator(language)("chat.result_readout.starting_capital", { value: formatCurrency(capital, language) });
    expect(presentation.plan?.rows.map((row) => row.text)).toContain(expected);
  });

  test("an unknown optional next-step kind does not prevent reading the research", () => {
    const turn = { ...researchTurn, offered_next_step: { kind: "future_kind", symbols: ["AAPL"] } } as unknown as ResearchReceiptTurn;
    const presentation = receiptPresentations({ schema_version: 2, kind: "turns", turns: [turn] }, null, language)[0];
    expect(presentation.research?.answer).toBe(researchTurn.answer);
    expect(presentation.research?.nextStep).toBeNull();
  });
});
