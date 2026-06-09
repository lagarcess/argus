import { afterEach, describe, expect, test } from "bun:test";

import { searchDiscovery, type DiscoveryItem } from "../lib/argus-api";

const discoveryItem: DiscoveryItem = {
  id: "asset:equity:AAPL",
  type: "asset",
  label: "AAPL · Apple Inc.",
  symbol: "AAPL",
  asset_class: "equity",
  description: "Stock",
  insert_text: "AAPL",
  provider: "alpaca",
  support_status: "supported",
};

describe("argus discovery API cache", () => {
  const originalFetch = globalThis.fetch;
  const originalMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    if (originalMockAuth === undefined) {
      delete process.env.NEXT_PUBLIC_MOCK_AUTH;
    } else {
      process.env.NEXT_PUBLIC_MOCK_AUTH = originalMockAuth;
    }
  });

  test("deduplicates repeated provider-backed discovery queries in one browser session", async () => {
    let fetchCount = 0;
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    globalThis.fetch = (() => {
      fetchCount += 1;
      return Promise.resolve(
        new Response(JSON.stringify({ items: [discoveryItem] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }) as typeof fetch;

    const first = await searchDiscovery("assets", " apple-cache-hit ", 20);
    const second = await searchDiscovery("assets", "APPLE-CACHE-HIT", 20);

    expect(fetchCount).toBe(1);
    expect(first.items).toEqual([discoveryItem]);
    expect(second.items).toEqual([discoveryItem]);
  });

  test("does not cache failed discovery responses", async () => {
    let fetchCount = 0;
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    globalThis.fetch = (() => {
      fetchCount += 1;
      if (fetchCount === 1) {
        return Promise.resolve(
          new Response(JSON.stringify({ detail: "temporary failure" }), {
            status: 503,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify({ items: [discoveryItem] }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }) as typeof fetch;

    await expect(searchDiscovery("assets", "apple-cache-error", 20)).rejects.toThrow(
      "temporary failure",
    );
    const recovered = await searchDiscovery("assets", "apple-cache-error", 20);

    expect(fetchCount).toBe(2);
    expect(recovered.items).toEqual([discoveryItem]);
  });
});
