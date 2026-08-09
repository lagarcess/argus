import { afterEach, describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  fetchPublicReceipt,
  headlineReceiptMetric,
  isPublicReceiptId,
  publicReceiptPath,
  type PublicReceiptPayload,
  type PublicReceiptView,
} from "../lib/public-receipt-contract";
import {
  formatReceiptDate,
  interpolate,
  receiptCopy,
  receiptLanguageFromAcceptLanguage,
} from "../lib/receipt-copy";
import { benchmarkVerdict, receiptPlan } from "../lib/receipt-plan";
import enCommon from "../public/locales/en/common.json";
import esCommon from "../public/locales/es-419/common.json";

const WEB_ROOT = join(import.meta.dir, "..");
const RECEIPT_ROUTE = join(WEB_ROOT, "app/r/[receiptId]/page.tsx");
const RECEIPT_LAYOUT = join(WEB_ROOT, "app/r/layout.tsx");
const OG_IMAGE_ROUTE = join(WEB_ROOT, "app/r/[receiptId]/opengraph-image.tsx");
const RECEIPT_BODY = join(WEB_ROOT, "components/receipt/ReceiptBody.tsx");
const CTA = join(WEB_ROOT, "components/receipt/TryArgusCallToAction.tsx");

function source(path: string): string {
  return readFileSync(path, "utf8");
}

/** The closed key set, read from the contract so no list is kept here by hand. */
function strategyFactKeys(): string[] {
  const contract = source(join(WEB_ROOT, "lib/public-receipt-contract.ts"));
  const start = contract.indexOf("PublicReceiptStrategyFactKey =");
  const union = contract.slice(start, contract.indexOf(";", start));
  const keys = [...union.matchAll(/"(\w+)"/g)].map((match) => match[1]);
  if (keys.length < 12) throw new Error("strategy fact key union not parsed");
  return keys;
}

/**
 * Structural assertions below are about code, not prose. Comments on these files
 * legitimately name the things the code must not touch (that is what the comments
 * are for), so they are stripped before scanning.
 */
function code(path: string): string {
  return source(path)
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/^\s*\/\/.*$/gm, "")
    .replace(/([^:])\/\/.*$/gm, "$1");
}

const VALID_ID = "abcdefghijklmnopqrstuvwx";

const PAYLOAD: PublicReceiptPayload = {
  schema_version: 1,
  idea_title: "AAPL buy and hold",
  asset_class: "equity",
  symbols: ["AAPL"],
  strategy_label: "Buy and hold",
  assumptions: ["Long only, no leverage."],
  date_range: {
    start: "2024-01-02",
    end: "2024-03-01",
    display: "Jan 2, 2024 to Mar 1, 2024",
  },
  metrics: [
    { key: "max_drawdown_pct", label: "Max drawdown", value: "-6.2%" },
    { key: "total_return_pct", label: "Total return", value: "+18.4%" },
  ],
  benchmark_symbol: "SPY",
  benchmark_note: "Compared against SPY.",
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

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

function stubFetch(
  responder: () => Response | Promise<Response> | never,
): void {
  globalThis.fetch = (async () => responder()) as typeof fetch;
}

describe("public receipt id", () => {
  test("accepts an unguessable token and refuses anything short or odd", () => {
    expect(isPublicReceiptId(VALID_ID)).toBe(true);
    expect(isPublicReceiptId("short")).toBe(false);
    expect(isPublicReceiptId("has spaces in it aaaaaaaaaa")).toBe(false);
    expect(isPublicReceiptId("../../etc/passwd")).toBe(false);
    expect(isPublicReceiptId("a".repeat(65))).toBe(false);
  });

  test("path prefix matches the backend contract", () => {
    expect(publicReceiptPath(VALID_ID)).toBe(`/r/${VALID_ID}`);
  });
});

describe("fetching a receipt", () => {
  test("a malformed id never reaches the network", async () => {
    let called = false;
    globalThis.fetch = (async () => {
      called = true;
      return new Response("{}", { status: 200 });
    }) as typeof fetch;
    expect(await fetchPublicReceipt("nope")).toEqual({ kind: "revoked" });
    expect(called).toBe(false);
  });

  test("an available receipt returns its frozen payload", async () => {
    const view: PublicReceiptView = {
      public_id: VALID_ID,
      status: "available",
      indexing: "noindex, nofollow",
      created_at: "2026-08-07T12:00:00Z",
      payload: PAYLOAD,
    };
    stubFetch(() => new Response(JSON.stringify(view), { status: 200 }));
    const result = await fetchPublicReceipt(VALID_ID);
    expect(result).toEqual({
      kind: "available",
      payload: PAYLOAD,
      createdAt: "2026-08-07T12:00:00Z",
    });
  });

  test("only the backend saying revoked makes a receipt revoked", async () => {
    stubFetch(
      () =>
        new Response(
          JSON.stringify({
            public_id: VALID_ID,
            status: "revoked",
            indexing: "noindex, nofollow",
          }),
          { status: 200 },
        ),
    );
    expect(await fetchPublicReceipt(VALID_ID)).toEqual({ kind: "revoked" });
  });

  test("a transient failure is never presented as a revocation", async () => {
    // Permanent and temporary are different facts. An unknown id already answers
    // 200 with status revoked, so a 404 means the endpoint is absent, which happens
    // when sharing is on here and off on the API. That is a deployment state.
    for (const status of [404, 500, 502, 503, 504]) {
      stubFetch(() => new Response("{}", { status }));
      expect(await fetchPublicReceipt(VALID_ID)).toEqual(
        { kind: "unavailable" },
      );
    }

    stubFetch(() => {
      throw new Error("network down");
    });
    expect(await fetchPublicReceipt(VALID_ID)).toEqual({ kind: "unavailable" });

    // An unrecognised shape is not evidence that anything was revoked either.
    stubFetch(() => new Response(JSON.stringify({ nonsense: true }), { status: 200 }));
    expect(await fetchPublicReceipt(VALID_ID)).toEqual({ kind: "unavailable" });
  });

  test("410 is the one status that does mean gone", async () => {
    stubFetch(() => new Response("{}", { status: 410 }));
    expect(await fetchPublicReceipt(VALID_ID)).toEqual({ kind: "revoked" });
  });

  test("the request carries no credentials and no auth header", () => {
    const contract = code(join(WEB_ROOT, "lib/public-receipt-contract.ts"));
    expect(contract).not.toContain("credentials");
    expect(contract).not.toContain("Authorization");
    expect(contract).not.toContain("getSupabaseClient");
    expect(contract).toContain('cache: "no-store"');
  });
});

describe("never indexable", () => {
  test("both the layout and the page declare noindex and nofollow", () => {
    for (const path of [RECEIPT_LAYOUT, RECEIPT_ROUTE]) {
      const body = source(path);
      expect(body).toContain("index: false");
      expect(body).toContain("follow: false");
      expect(body).toContain("googleBot");
    }
  });

  test("the preview image is marked noindex at the header level too", () => {
    const body = source(OG_IMAGE_ROUTE);
    expect(body).toContain("X-Robots-Tag");
    expect(body).toContain("noimageindex");
    expect(body).toContain("no-store");
  });

  test("no user-facing control can turn indexing on", () => {
    // A discoverability toggle is the specific failure this design exists to
    // avoid, so no such control may exist anywhere on the surface.
    for (const path of [RECEIPT_ROUTE, RECEIPT_LAYOUT, RECEIPT_BODY]) {
      const body = code(path).toLowerCase();
      expect(body).not.toContain("discoverab");
      expect(body).not.toMatch(/(?:^|[^a-z])index:\s*true/);
      expect(body).not.toContain('"index, follow"');
      expect(body).not.toContain("setrobots");
    }
  });

  test("a view is reported by the rendered page, not by reading the receipt", () => {
    // The read endpoint answers the metadata pass and the preview image too, so
    // counting there would log views for a pasted link nobody opened.
    const contract = code(join(WEB_ROOT, "lib/public-receipt-contract.ts"));
    expect(contract).not.toContain("receipt-funnel");
    expect(source(join(WEB_ROOT, "components/receipt/ReceiptViewBeacon.tsx"))).toContain(
      'reportReceiptFunnelStage("viewed")',
    );
    for (const path of [RECEIPT_BODY, join(WEB_ROOT, "components/receipt/ReceiptNotice.tsx")]) {
      expect(source(path)).toContain("<ReceiptViewBeacon />");
    }
    // The image never reports anything.
    expect(code(OG_IMAGE_ROUTE)).not.toContain("receipt-funnel");
  });

  test("the metadata pass and the page render share one backend read", () => {
    const contract = source(join(WEB_ROOT, "lib/public-receipt-contract.ts"));
    expect(contract).toContain("cache(fetchPublicReceipt)");
    expect(source(RECEIPT_ROUTE)).toContain("readPublicReceipt");
    expect(source(RECEIPT_ROUTE)).not.toContain("await fetchPublicReceipt");
  });

  test("an outage renders distinctly from a revocation, page and card alike", () => {
    // Platforms cache preview images and metadata, so a temporary failure dressed
    // as a permanent one would pin a revoked-looking card to a live receipt, and
    // Argus cannot clear a cache it does not own.
    const image = code(OG_IMAGE_ROUTE);
    expect(image).toContain('result.kind === "unavailable"');
    expect(image).toContain("status: 503");
    expect(image).toContain("Retry-After");
    expect(image).toContain('result.kind === "revoked"');
    // The gone card is reachable only from the revoked branch.
    expect(image.indexOf('result.kind === "unavailable"')).toBeLessThan(
      image.indexOf("copy.gone"),
    );

    const page = code(RECEIPT_ROUTE);
    expect(page).toContain('result.kind === "unavailable"');
    expect(page.indexOf('result.kind === "unavailable"')).toBeLessThan(
      page.indexOf("copy.tombstone.title"),
    );

    // The page keeps its own distinct copy for the temporary case.
    const notice = source(join(WEB_ROOT, "components/receipt/ReceiptNotice.tsx"));
    expect(notice).toContain('kind === "revoked" ? copy.tombstone : copy.unavailable');
    for (const bundle of [enCommon.receipt, esCommon.receipt]) {
      expect(bundle.unavailable.title).not.toBe(bundle.tombstone.title);
      expect(bundle.unavailable.detail).not.toBe(bundle.tombstone.detail);
    }
  });

  test("the route is never cached, so revocation lands on the next request", () => {
    const body = source(RECEIPT_ROUTE);
    expect(body).toContain('dynamic = "force-dynamic"');
    expect(body).toContain("revalidate = 0");
  });
});

describe("the preview image inherits the never-expose list", () => {
  test("it renders a named subset of the frozen payload and nothing else", () => {
    const body = source(OG_IMAGE_ROUTE);
    expect(body).toContain("PREVIEW_FIELDS");
    for (const field of [
      "idea_title",
      "symbols",
      "date_range.display",
      "headline_metric.label",
      "headline_metric.value",
    ]) {
      expect(body).toContain(field);
    }
  });

  test("it never reads a private record and never calls a provider", () => {
    const body = code(OG_IMAGE_ROUTE).toLowerCase();
    for (const forbidden of [
      "conversation",
      "artifact",
      "memory",
      "transcript",
      "openrouter",
      "alpaca",
      "supabase",
      "owner_id",
      "owner_note",
    ]) {
      expect(body).not.toContain(forbidden);
    }
  });

  test("it carries the provenance mark and the not-advice framing", () => {
    const body = source(OG_IMAGE_ROUTE);
    expect(body).toContain("copy.provenance");
    expect(body).toContain("copy.framing");
    for (const bundle of [enCommon.receipt, esCommon.receipt]) {
      expect(bundle.provenance.length).toBeGreaterThan(0);
      expect(bundle.framing.short.length).toBeGreaterThan(0);
    }
    expect(enCommon.receipt.framing.short).toContain("Not a tip");
  });

  test("it follows the receipt's own language, not a viewer's", () => {
    // A crawler fetching the card has no language of its own, and the frozen facts
    // on the card are already in the receipt's language.
    const body = code(OG_IMAGE_ROUTE);
    expect(body).toContain("cardCopy(result.payload.content_language)");
    expect(body).not.toContain("accept-language");
    expect(body).not.toContain("const FRAMING");
    expect(body).not.toContain("const PROVENANCE");
  });
});

describe("the rendered page", () => {
  test("carries the provenance mark and prominent not-advice framing", () => {
    const body = source(RECEIPT_BODY);
    expect(body).toContain("ProvenanceMark");
    expect(body).toContain("copy.framing.headline");
    expect(body).toContain("copy.framing.detail");
  });

  test("renders no field outside the closed payload", () => {
    const body = source(RECEIPT_BODY);
    const referenced = [...body.matchAll(/payload\.(\w+)/g)].map(
      (match) => match[1],
    );
    const closed = new Set(Object.keys(PAYLOAD));
    expect([...new Set(referenced)].filter((key) => !closed.has(key))).toEqual([]);
  });

  test("shows no attribution: the owner is never named", () => {
    const body = source(RECEIPT_BODY).toLowerCase();
    for (const forbidden of ["display_name", "username", "avatar", "shared by"]) {
      expect(body).not.toContain(forbidden);
    }
  });
});

describe("try argus", () => {
  test("lands on bare guest entry with no carried state and no new parameter", () => {
    const body = source(CTA);
    expect(body).toContain('href="/"');
    expect(body).not.toContain("?");
    expect(body).not.toContain("searchParams");
    expect(body).not.toContain("prefill");
  });
});

describe("headline metric", () => {
  test("prefers total return over whatever happens to be first", () => {
    expect(headlineReceiptMetric(PAYLOAD)?.key).toBe("total_return_pct");
  });

  test("falls back to the first metric, and to nothing when there are none", () => {
    const onlyDrawdown = { ...PAYLOAD, metrics: [PAYLOAD.metrics[0]] };
    expect(headlineReceiptMetric(onlyDrawdown)?.key).toBe("max_drawdown_pct");
    expect(headlineReceiptMetric({ ...PAYLOAD, metrics: [] })).toBeNull();
  });
});

describe("viewer language", () => {
  test("reads the request rather than a stored preference", () => {
    expect(receiptLanguageFromAcceptLanguage(null)).toBe("en");
    expect(receiptLanguageFromAcceptLanguage("en-GB,en;q=0.9")).toBe("en");
    expect(receiptLanguageFromAcceptLanguage("de-DE,de;q=0.9")).toBe("en");
  });

  test("both languages have the whole receipt namespace", () => {
    const flatten = (node: unknown, prefix = ""): string[] => {
      if (typeof node !== "object" || node === null) return [prefix];
      return Object.entries(node as Record<string, unknown>).flatMap(
        ([key, value]) => flatten(value, prefix ? `${prefix}.${key}` : key),
      );
    };
    expect(flatten(esCommon.receipt).sort()).toEqual(
      flatten(enCommon.receipt).sort(),
    );
  });

  test("no em dash in receipt copy, in either language", () => {
    for (const bundle of [enCommon.receipt, esCommon.receipt]) {
      expect(JSON.stringify(bundle)).not.toContain("—");
    }
  });

  test("copy resolves and interpolates", () => {
    expect(receiptCopy("en").provenance).toBe("Tested with Argus");
    expect(
      interpolate(receiptCopy("en").frozen_note, { date: "August 7, 2026" }),
    ).toContain("August 7, 2026");
  });

  test("a missing or unparseable date degrades to the undated note", () => {
    expect(formatReceiptDate(null, "en")).toBeNull();
    expect(formatReceiptDate("not-a-date", "en")).toBeNull();
    expect(formatReceiptDate("2026-08-07T12:00:00Z", "en")).toBe("August 7, 2026");
  });
});

describe("the strategy a receipt shows", () => {
  test("every frozen fact still reaches the page, in the fine print", () => {
    // The facts moved out of the headline and into the fine print; none of them
    // was dropped. The plan is composed from the payload, and the fine print maps
    // over the whole set rather than a chosen subset.
    const plan = source(join(WEB_ROOT, "lib/receipt-plan.ts"));
    expect(plan).toContain("payload.strategy_facts");
    const body = source(RECEIPT_BODY);
    expect(body).toContain("plan.settings.map");
    expect(body).toContain("copy.strategy_facts[fact.key]");
  });

  test("labels are the viewer's language and values stay frozen", () => {
    // Freezing an English label would put untranslatable chrome in the payload.
    // Keys come from the contract rather than a list kept here by hand, because a
    // hand-kept list is what let a crossover ship with no window labels: adding a
    // key to the union now fails until both languages can render it.
    for (const bundle of [enCommon.receipt, esCommon.receipt]) {
      for (const key of strategyFactKeys()) {
        expect(
          (bundle.strategy_facts as Record<string, string>)[key]?.length,
        ).toBeGreaterThan(0);
      }
    }
    expect(enCommon.receipt.strategy_facts.indicator).not.toBe(
      esCommon.receipt.strategy_facts.indicator,
    );
  });

  test("the frozen key set matches the backend enum exactly", () => {
    // Two enums that have to agree. A key the backend can freeze but the page
    // cannot name would render as a raw identifier on a public page.
    const schema = source(
      join(WEB_ROOT, "../src/argus/api/public_excerpt_schemas.py"),
    );
    const start = schema.indexOf("StrategyFactKey = Literal[");
    const literal = schema.slice(start, schema.indexOf("]", start));
    const backend = [...literal.matchAll(/"(\w+)"/g)].map((match) => match[1]);
    expect([...strategyFactKeys()].sort()).toEqual([...backend].sort());
  });
});

describe("a view is only counted when a receipt was shown", () => {
  test("the outage notice does not fire the beacon", () => {
    const notice = source(join(WEB_ROOT, "components/receipt/ReceiptNotice.tsx"));
    expect(notice).toContain('kind === "revoked" ? <ReceiptViewBeacon /> : null');
  });
});

describe("the public route escapes the client i18n gate", () => {
  test("so a shared link is not blank without JavaScript", () => {
    // The gate returns a placeholder instead of children until i18n initialises,
    // which left the initial HTML empty and the page permanently blank with JS off.
    const provider = source(join(WEB_ROOT, "components/I18nProvider.tsx"));
    expect(provider).toContain("PUBLIC_RECEIPT_PATH_PREFIX");
    expect(provider).toContain("!isInitialized && !rendersWithoutI18n");
    // The receipt surface consumes no i18next resources, which is what makes this safe.
    for (const file of [
      "components/receipt/ReceiptBody.tsx",
      "components/receipt/ReceiptNotice.tsx",
      "components/receipt/TryArgusCallToAction.tsx",
      "components/receipt/ProvenanceMark.tsx",
    ]) {
      expect(source(join(WEB_ROOT, file))).not.toContain("useTranslation");
    }
  });
});

describe("when the label and the frozen strategy name disagree", () => {
  test("the description is composed from the executed facts, not the label", () => {
    // The two are frozen from different records: the label from the result card,
    // the name from the run's own config. The page no longer renders the label as
    // the description of what ran at all, so a stale label cannot speak for a run
    // it does not describe. It survives only as the fallback for a shape with no
    // sentence of its own.
    const plan = source(join(WEB_ROOT, "lib/receipt-plan.ts"));
    const labelUses = plan.match(/payload\.strategy_label/g) ?? [];
    expect(labelUses).toHaveLength(1);
    expect(plan).toContain("plan.unnamed");
  });
});

describe("the plan sentence", () => {
  const copy = receiptCopy("en");
  const spanish = receiptCopy("es-419");

  function withFacts(
    facts: PublicReceiptPayload["strategy_facts"],
  ): PublicReceiptPayload {
    return { ...PAYLOAD, strategy_facts: facts };
  }

  test("states a crossover's entry and its mirrored exit in words", () => {
    const { sentences, settings } = receiptPlan(
      withFacts([
        { key: "strategy_type", value: "moving average crossover" },
        { key: "fast_indicator", value: "sma" },
        { key: "fast_period", value: "20" },
        { key: "slow_indicator", value: "sma" },
        { key: "slow_period", value: "50" },
      ]),
      copy,
    );
    expect(sentences[0]).toBe(
      "Bought when the 20 day SMA crossed above the 50 day SMA.",
    );
    expect(sentences[1]).toBe("Sold when it crossed back below.");
    // Acronyms read as acronyms, and nothing frozen was lost on the way.
    expect(settings).toHaveLength(4);
  });

  test("states a differing exit as its own sentence", () => {
    const { sentences } = receiptPlan(
      withFacts([
        { key: "strategy_type", value: "moving average crossover" },
        { key: "fast_indicator", value: "sma" },
        { key: "fast_period", value: "20" },
        { key: "slow_indicator", value: "sma" },
        { key: "slow_period", value: "50" },
        { key: "exit_fast_indicator", value: "ema" },
        { key: "exit_fast_period", value: "9" },
        { key: "exit_slow_indicator", value: "ema" },
        { key: "exit_slow_period", value: "21" },
      ]),
      copy,
    );
    expect(sentences[1]).toBe(
      "Sold when the 9 day EMA crossed below the 21 day EMA.",
    );
  });

  test("states an indicator threshold and a cadence in words", () => {
    expect(
      receiptPlan(
        withFacts([
          { key: "strategy_type", value: "rsi threshold" },
          { key: "indicator", value: "RSI" },
          { key: "indicator_period", value: "14" },
          { key: "entry_threshold", value: "30" },
          { key: "exit_threshold", value: "70" },
        ]),
        copy,
      ).sentences[0],
    ).toBe("Bought when RSI fell to 30, sold when it climbed back to 70.");

    expect(
      receiptPlan(
        withFacts([
          { key: "strategy_type", value: "dca accumulation" },
          { key: "cadence", value: "monthly" },
        ]),
        copy,
      ).sentences[0],
    ).toBe("Bought every month, whatever the price was that day.");
  });

  test("reads in the viewer's language while the values stay frozen", () => {
    const { sentences } = receiptPlan(
      withFacts([
        { key: "strategy_type", value: "dca accumulation" },
        { key: "cadence", value: "monthly" },
      ]),
      spanish,
    );
    expect(sentences[0]).toBe("Compró cada mes, sin importar el precio de ese día.");
  });

  test("the comparison is stated as a verdict, not left as two numbers", () => {
    const ahead = {
      ...PAYLOAD,
      metrics: [
        { key: "total_return_pct", label: "Total return", value: "+18.4%" },
        { key: "benchmark_return_pct", label: "SPY", value: "+9.1%" },
      ],
    };
    expect(benchmarkVerdict(ahead, copy)).toBe("9.3 pts ahead of SPY");
    const behind = {
      ...PAYLOAD,
      metrics: [
        { key: "total_return_pct", label: "Total return", value: "+2.0%" },
        { key: "benchmark_return_pct", label: "SPY", value: "+9.1%" },
      ],
    };
    expect(benchmarkVerdict(behind, copy)).toBe("7.1 pts behind SPY");
  });

  test("says nothing when the payload carries no benchmark to compare against", () => {
    // PAYLOAD has a return and no benchmark row, which is a real shape.
    expect(benchmarkVerdict(PAYLOAD, copy)).toBeNull();
  });

  test("says nothing rather than guessing when a figure will not parse", () => {
    const unparseable = {
      ...PAYLOAD,
      benchmark_symbol: null,
      metrics: [{ key: "total_return_pct", label: "Total return", value: "n/a" }],
    };
    expect(benchmarkVerdict(unparseable, copy)).toBeNull();
  });
});
