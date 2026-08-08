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

  test("a revoked receipt is a tombstone, and so is a 404", async () => {
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

    stubFetch(() => new Response("{}", { status: 404 }));
    expect(await fetchPublicReceipt(VALID_ID)).toEqual({ kind: "revoked" });
  });

  test("a backend outage is unavailable, never a false tombstone", async () => {
    stubFetch(() => new Response("{}", { status: 503 }));
    expect(await fetchPublicReceipt(VALID_ID)).toEqual({ kind: "unavailable" });

    stubFetch(() => {
      throw new Error("network down");
    });
    expect(await fetchPublicReceipt(VALID_ID)).toEqual({ kind: "unavailable" });
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
    expect(body).toContain("Tested with Argus");
    expect(body).toContain("Not a tip");
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
