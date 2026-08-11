import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import type { PublicReceiptPayload } from "../lib/public-receipt-contract";
import {
  formatReceiptDateRange,
  formatReceiptNumber,
  receiptCopy,
} from "../lib/receipt-copy";
import { receiptAssumptions } from "../lib/receipt-plan";
import enCommon from "../public/locales/en/common.json";
import esCommon from "../public/locales/es-419/common.json";

/**
 * What the page says, and whose language and voice it says it in.
 *
 * The payload freezes keys and bare scalars, so every sentence, label, number
 * format and date on this route is composed here at view time. These cover the
 * two questions that composition raises: does it read correctly for whoever
 * opened the link, and does it still read like Argus.
 */
const WEB_ROOT = join(import.meta.dir, "..");
const RECEIPT_ROUTE = join(WEB_ROOT, "app/r/[receiptId]/page.tsx");
const RECEIPT_BODY = join(WEB_ROOT, "components/receipt/ReceiptBody.tsx");

function source(path: string): string {
  return readFileSync(path, "utf8");
}

/** Comments legitimately name the things the code must not do, so they are stripped. */
function code(path: string): string {
  return source(path)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "")
    .replace(/([^:])\/\/.*$/gm, "$1");
}

const PAYLOAD: PublicReceiptPayload = {
  schema_version: 1,
  idea_title: "AAPL buy and hold",
  asset_class: "equity",
  symbols: ["AAPL"],
  assumptions: [
    { key: "long_only" },
    { key: "equal_weight" },
    { key: "no_costs" },
    { key: "benchmark", value: "SPY" },
  ],
  date_range: { start: "2024-01-02", end: "2024-03-01" },
  metrics: [
    { key: "max_drawdown_pct", value: "-6.2%" },
    { key: "total_return_pct", value: "+18.4%" },
    { key: "benchmark_return_pct", value: "+9.1%" },
    { key: "delta_vs_benchmark_pct", value: "9.3" },
  ],
  benchmark_symbol: "SPY",
  strategy_facts: [
    { key: "indicator", value: "RSI" },
    { key: "indicator_period", value: "14" },
  ],
  visual: null,
  owner_note: null,
  content_language: "en",
  framing: "historical_simulation_not_advice",
  provenance_mark: "tested_with_argus",
};

describe("what the run assumed, spoken to whoever opened the link", () => {
  // One frozen payload, produced by one run, read by two people who share no
  // language. Everything below reads this same object: that is the whole point.
  const FROZEN: PublicReceiptPayload = {
    ...PAYLOAD,
    assumptions: [
      { key: "recurring_contribution", value: "1200" },
      { key: "contribution_cadence", value: "monthly" },
      { key: "starting_principal", value: "0" },
      { key: "long_only" },
      { key: "equal_weight" },
      { key: "modeled_fee_bps", value: "10" },
      { key: "modeled_slippage_bps", value: "5" },
      { key: "benchmark_same_modeled_costs", value: "SPY" },
    ],
  };

  test("every frozen assumption becomes a sentence, in each language", () => {
    for (const language of ["en", "es-419"] as const) {
      const lines = receiptAssumptions(FROZEN, receiptCopy(language), language);
      // Two pairs each read as one line, the contribution with its cadence and the
      // fee with its slippage, so eight frozen facts read as six.
      expect(lines).toHaveLength(6);
      expect(lines.every((line) => line.trim().length > 0)).toBe(true);
      expect(lines.some((line) => line.includes("{{"))).toBe(false);
    }
  });

  test("the two languages say different words about the same run", () => {
    const english = receiptAssumptions(FROZEN, receiptCopy("en"), "en");
    const spanish = receiptAssumptions(FROZEN, receiptCopy("es-419"), "es-419");
    expect(english).not.toEqual(spanish);
    // The numbers and the symbol are the frozen facts and survive both readings.
    expect(english.join(" ")).toContain("SPY");
    expect(spanish.join(" ")).toContain("SPY");
    for (const lines of [english, spanish]) {
      expect(lines.join(" ")).toContain("10");
      expect(lines.join(" ")).toContain("5");
    }
  });

  test("the contribution and its cadence read as one line", () => {
    const [first] = receiptAssumptions(FROZEN, receiptCopy("en"), "en");
    expect(first).toBe("$1,200 every month");
    const [firstEs] = receiptAssumptions(FROZEN, receiptCopy("es-419"), "es-419");
    expect(firstEs).toBe("$1,200 cada mes");
  });

  test("a contribution with no frozen cadence still reads", () => {
    const withoutCadence = {
      ...FROZEN,
      assumptions: FROZEN.assumptions.filter(
        (assumption) => assumption.key !== "contribution_cadence",
      ),
    };
    const lines = receiptAssumptions(withoutCadence, receiptCopy("en"), "en");
    expect(lines[0]).toBe("$1,200 each time");
  });

  test("the fine print stays fine print, in both languages", () => {
    // These sit under the rules block as muted one-liners, where the result card
    // froze terse fragments before this lane existed. Full past-tense sentences
    // with terminal periods turn that block into a narration and undo the shape
    // the surface was redesigned into.
    // The longest fragment the result card itself froze is "Neto de comisión de 10
    // bps + deslizamiento de 5 bps", at 50 characters. Nothing composed here should
    // run longer than what it replaced.
    for (const language of ["en", "es-419"] as const) {
      for (const line of receiptAssumptions(FROZEN, receiptCopy(language), language)) {
        expect(line.endsWith(".")).toBe(false);
        expect(line.length).toBeLessThanOrEqual(50);
      }
    }
  });

  test("a key whose sentence needs a value it does not have is dropped", () => {
    const broken: PublicReceiptPayload = {
      ...PAYLOAD,
      assumptions: [
        { key: "benchmark", value: null },
        { key: "modeled_fee_bps" },
        { key: "long_only" },
      ],
    };
    expect(receiptAssumptions(broken, receiptCopy("en"), "en")).toEqual([
      receiptCopy("en").assumptions.long_only,
    ]);
  });

  test("both locales carry a sentence for every key in the closed set", () => {
    const contract = code(join(WEB_ROOT, "lib/public-receipt-contract.ts"));
    const start = contract.indexOf("PublicReceiptAssumptionKey =");
    const union = contract.slice(start, contract.indexOf(";", start));
    const keys = [...union.matchAll(/"(\w+)"/g)].map((match) => match[1]);
    expect(keys).toHaveLength(10);
    for (const common of [enCommon, esCommon]) {
      const said = common.receipt.assumptions as Record<string, string>;
      for (const key of keys) {
        // The cadence is spoken through the contribution line, not on its own.
        if (key === "contribution_cadence") continue;
        expect(said[key]).toBeTruthy();
      }
      // The two composed lines, each covering a pair of frozen facts.
      expect(said.recurring_contribution_cadence).toBeTruthy();
      expect(said.modeled_costs).toBeTruthy();
    }
  });
});

describe("the tested window", () => {
  test("is rendered from two dates, in the language of whoever opened it", () => {
    const range = { start: "2024-01-02", end: "2024-03-01" };
    expect(formatReceiptDateRange(range, receiptCopy("en"), "en")).toBe(
      "Jan 2, 2024 to Mar 1, 2024",
    );
    const spanish = formatReceiptDateRange(range, receiptCopy("es-419"), "es-419");
    expect(spanish).toContain(" al ");
    expect(spanish).not.toBe(formatReceiptDateRange(range, receiptCopy("en"), "en"));
  });

  test("reads the frozen day in UTC, so the window cannot slide", () => {
    // A calendar day parsed in the viewer's zone lands on the day before for
    // anyone west of Greenwich, which would move the tested window.
    const range = { start: "2024-01-01", end: "2024-12-31" };
    expect(formatReceiptDateRange(range, receiptCopy("en"), "en")).toBe(
      "Jan 1, 2024 to Dec 31, 2024",
    );
  });

  test("says nothing when either end will not parse", () => {
    expect(
      formatReceiptDateRange(
        { start: "not a date", end: "2024-03-01" },
        receiptCopy("en"),
        "en",
      ),
    ).toBeNull();
  });

  test("the page and its preview card render it rather than reading a string", () => {
    const route = code(RECEIPT_ROUTE);
    const body = code(RECEIPT_BODY);
    expect(route).not.toContain("date_range.display");
    expect(body).not.toContain("date_range.display");
    expect(route).toContain("formatReceiptDateRange");
    expect(body).toContain("formatReceiptDateRange");
  });
});

describe("metric labels", () => {
  test("are rendered from the key, never read off the payload", () => {
    const body = code(RECEIPT_BODY);
    const route = code(RECEIPT_ROUTE);
    expect(body).not.toContain("entry.label");
    expect(route).not.toContain("headline.label");
    expect(body).toContain("copy.metric_labels");
    expect(route).toContain("metric_labels");
  });

  test("both locales label every key the payload can carry", () => {
    const contract = code(join(WEB_ROOT, "lib/public-receipt-contract.ts"));
    const start = contract.indexOf("PublicReceiptMetricKey =");
    const union = contract.slice(start, contract.indexOf(";", start));
    const keys = [...union.matchAll(/"(\w+)"/g)].map((match) => match[1]);
    expect(keys).toHaveLength(6);
    // The card's own benchmark row is a sentence, so the payload carries the two
    // numbers behind it instead. Both need a label like every other key.
    expect(keys).toContain("benchmark_return_pct");
    expect(keys).toContain("delta_vs_benchmark_pct");
    for (const common of [enCommon, esCommon]) {
      const labels = common.receipt.metric_labels as Record<string, string>;
      expect(Object.keys(labels).sort()).toEqual([...keys].sort());
      for (const key of keys) expect(labels[key]).toBeTruthy();
    }
  });
});

describe("numbers frozen bare", () => {
  test("are grouped by the renderer, not by whoever ran the backtest", () => {
    // The payload freezes "25000" with no separators at all, and each locale adds
    // its own. CLDR gives es-419 the same grouping as en-US today, so the two read
    // alike; the point is that the separator is a rendering decision rather than a
    // frozen one, which is what makes the payload safe to hand any locale later.
    expect(formatReceiptNumber("25000", "en")).toBe("25,000");
    expect(formatReceiptNumber("25000", "es-419")).toBe(
      new Intl.NumberFormat("es-419").format(25000),
    );
    expect(formatReceiptNumber("not a number", "en")).toBeNull();
  });
});

describe("the receipt shell is one fixed look", () => {
  test("is sized against the viewport, not against a parent with no height", () => {
    // A percentage min-height resolves against the containing block's height, and
    // body sets min-height without ever setting height, so its own height stays
    // content-based and the percentage resolves to nothing. Any page shorter than
    // the screen ended the dark surface at its last line and showed white below.
    const layout = code(join(WEB_ROOT, "app/r/layout.tsx"));
    expect(layout).toContain("min-h-dvh");
    expect(layout).not.toContain("min-h-full");
  });

  test("no component on the route is theme-conditional", () => {
    // The shell is one colour on purpose, so the page and the preview card that
    // advertises it cannot disagree. This route runs no theme provider either, so
    // a `dark:` variant never applies and its light-mode value is what ships. The
    // tombstone rendered black text on the dark shell for exactly that reason.
    for (const file of [
      "app/r/layout.tsx",
      "components/receipt/ReceiptBody.tsx",
      "components/receipt/ReceiptNotice.tsx",
      "components/receipt/ReceiptActionBar.tsx",
      "components/receipt/ProvenanceMark.tsx",
      "components/receipt/ReceiptChart.tsx",
    ]) {
      expect(code(join(WEB_ROOT, file))).not.toContain("dark:");
    }
  });
});

describe("no user-facing copy on this surface uses an em dash", () => {
  test("in either language", () => {
    for (const common of [enCommon, esCommon]) {
      expect(JSON.stringify(common.receipt)).not.toContain("—");
    }
  });
});
