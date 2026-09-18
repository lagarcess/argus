import { expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { renderToStaticMarkup } from "react-dom/server";
import ReceiptBody from "../components/receipt/ReceiptBody";
import { receiptCopy } from "../lib/receipt-copy";
import { legacyReceipt } from "./fixtures/receipt-turns";

for (const preview of [false, true]) {
  test(`chart attribution is visible in ${preview ? "preview" : "public thread"}`, () => {
    const payload = { ...legacyReceipt, visual: { kind: "portfolio_equity" as const, base_value: 100, series: [
      { time: legacyReceipt.date_range.start, value: 100 },
      { time: legacyReceipt.date_range.end, value: 118.4 },
    ] } };
    const markup = renderToStaticMarkup(<ReceiptBody payload={payload} copy={receiptCopy("en")} language="en" createdAt={null} preview={preview} />);
    expect(markup).toContain('href="https://www.tradingview.com/"');
    expect(markup).toContain("TradingView Lightweight Charts");
    expect(markup).toContain("TradingView, Inc.");
    expect(markup).toContain('data-testid="receipt-chart-attribution"');
  });
}

test("receipt charts retain the library attribution logo", () => {
  const source = readFileSync(new URL("../components/receipt/ReceiptChart.tsx", import.meta.url), "utf8");
  expect(source).toContain("attributionLogo: true");
  expect(source).not.toContain("attributionLogo: false");
});
