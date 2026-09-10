import { describe, expect, test } from "bun:test";
import { renderToStaticMarkup } from "react-dom/server";
import ReceiptBody from "../components/receipt/ReceiptBody";
import { receiptCopy, receiptTranslator } from "../lib/receipt-copy";
import { receiptDocumentKind, receiptDocumentLanguage, receiptDocumentSupported } from "../lib/public-receipt-turns";
import { receiptPresentations } from "../lib/receipt-presentation";
import { receiptPreviewFacts } from "../lib/receipt-preview-facts";
import { backtestTurn, legacyReceipt, legacyToolDocument, researchTurn, toolTurnFixture, turnDocument } from "./fixtures/receipt-turns";

test("a selected tool message retains ordered sibling cards as one turn", () => {
  const tool = toolTurnFixture();
  const document = turnDocument(researchTurn, backtestTurn, tool);
  expect(receiptDocumentSupported(document)).toBe(true);
  expect(receiptDocumentKind(document)).toBe("mixed");
  const entries = receiptPresentations(document, null, "en");
  expect(entries).toHaveLength(3);
  expect(entries[2].toolCards?.map((card) => card.presentation.answer?.value)).toEqual([0, 40]);
});

test("frozen bare v2 reads through the common receipt contract", () => {
  const document = legacyToolDocument();
  expect(receiptDocumentSupported(document)).toBe(true);
  expect(receiptDocumentKind(document)).toBe("tool_result");
  expect(receiptPresentations(document, null, "en")[0].toolCards).toHaveLength(1);
});

test.each([
  { card_version: 2 }, { call_id: "private-call" }, { framing: "historical_simulation_not_advice" },
  { presentation: { ...legacyToolDocument().presentation, answer: null } },
])("the legacy tool decoder rejects unsupported or private document fields: %j", (change) => {
  expect(receiptDocumentSupported({ ...legacyToolDocument(), ...change })).toBe(false);
});

describe.each(["en", "es-419"] as const)("generic receipt presentation in %s", (language) => {
  test("the image language comes from the frozen document for every read format", () => {
    expect(receiptDocumentLanguage({ ...legacyReceipt, content_language: language })).toBe(language);
    expect(receiptDocumentLanguage({ ...legacyToolDocument(), content_language: language })).toBe(language);
    expect(receiptDocumentLanguage(turnDocument({ ...toolTurnFixture(), content_language: language }, researchTurn))).toBe(language);
  });

  test.each([false, true])("one receipt body renders each answer once, preview=%s", (preview) => {
    const tool = toolTurnFixture();
    const markup = renderToStaticMarkup(<ReceiptBody payload={turnDocument(tool)} createdAt={null}
      copy={receiptCopy(language)} language={language} preview={preview} />);
    expect(markup.match(/data-tool-answer/g)).toHaveLength(2);
    expect(markup.match(/<main/g)).toHaveLength(1);
    expect(markup.match(/Read these values\./g)).toHaveLength(1);
    expect(markup).toContain(receiptTranslator(language)("tools.receipt.provenance"));
    expect(markup).toContain(receiptTranslator(language)("tools.receipt.framing"));
    expect(markup).not.toContain("artifact-1");
    expect(markup).not.toContain("call-1");
    expect(markup.match(/href="\/"/g) ?? []).toHaveLength(preview ? 0 : 1);
  });

  test("metadata preserves a zero answer and computed framing", () => {
    const facts = receiptPreviewFacts(turnDocument(toolTurnFixture()), language);
    expect(facts.title).toBe(toolTurnFixture().question);
    expect(facts.metricValue).toBe("0");
    expect(facts.framing).toBe(receiptTranslator(language)("tools.receipt.framing"));
    expect(facts.description).not.toContain("undefined");
    expect(facts.provenance).toBe(receiptTranslator(language)("tools.receipt.provenance"));
  });

  test("the frozen bare document retains its own title and answer", () => {
    const markup = renderToStaticMarkup(<ReceiptBody payload={legacyToolDocument()} createdAt={null}
      copy={receiptCopy(language)} language={language} />);
    expect(markup.match(/data-tool-answer/g)).toHaveLength(1);
    expect(markup).toContain(receiptTranslator(language)("tools.card.title"));
  });
});
