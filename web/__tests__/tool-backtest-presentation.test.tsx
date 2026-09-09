import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import path from "node:path";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ReceiptBody from "../components/receipt/ReceiptBody";
import { parseToolResultCard, type ToolResultCard } from "../lib/tool-result-card";
import type { PublicToolReceiptPayload } from "../lib/public-receipt-contract";
import { receiptCopy } from "../lib/receipt-copy";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";

const fixtures = JSON.parse(readFileSync(path.resolve(import.meta.dir,
  "../../docs/reports/evidence/registry/backtest-cards.json"), "utf8")) as Record<string, {
  card: ToolResultCard; receipt: PublicToolReceiptPayload;
}>;

describe("canonical backtest presentation in a v2 receipt", () => {
  for (const language of ["en", "es-419"] as const) {
    test(`preserves the DCA result, zero, costs and plot in ${language}`, () => {
      const { card, receipt } = fixtures[language];
      expect(parseToolResultCard(card)).not.toBeNull();
      expect(receipt.presentation.visual).toEqual(card.presentation.visual);
      const html = renderToStaticMarkup(<ReceiptBody payload={receipt} createdAt={null}
        copy={receiptCopy(language)} language={language} />);
      const copy = (language === "en" ? en : es).receipt;
      expect(html).toContain("data-tool-visual");
      expect(html).toContain(copy.metric_labels.contribution_return_pct);
      expect(html).toContain(copy.assumptions.starting_principal.replace("{{amount}}", "0"));
      expect(html).toContain(copy.assumptions.recurring_contribution.replace("{{amount}}", "200"));
      expect(html).toContain(copy.assumptions.modeled_fee_bps.replace("{{bps}}", "10"));
      expect(html).toContain(copy.assumptions.modeled_slippage_bps.replace("{{bps}}", "5"));
      expect(html).toContain(copy.cadence_values.monthly);
      expect(html).not.toContain("receipt.");
      expect(html).not.toContain(card.artifact_id);
    });
  }
});
