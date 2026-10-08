import { afterEach, describe, expect, test } from "bun:test";

import { startBusinessSpace } from "@/lib/business-api";

type Call = { url: string; method: string; body: unknown };

function respond(status: number, body: unknown): Call[] {
  const calls: Call[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({
      url: String(input),
      method: init?.method ?? "GET",
      body: init?.body ? JSON.parse(String(init.body)) : null,
    });
    return new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof fetch;
  return calls;
}

describe("starting the Business space", () => {
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

  test("sends only the language; the server names and owns the space", async () => {
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    const calls = respond(200, { id: "space-1", name: "Mi negocio" });
    expect(await startBusinessSpace("es-419")).toEqual({ id: "space-1", name: "Mi negocio" });
    expect(calls).toHaveLength(1);
    expect(calls[0].url.endsWith("/business/space")).toBe(true);
    expect(calls[0].method).toBe("POST");
    expect(calls[0].body).toEqual({ language: "es-419" });
  });

  test("a refused start surfaces the server's code", async () => {
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    respond(404, { code: "business_unavailable" });
    await expect(startBusinessSpace("en")).rejects.toMatchObject({
      status: 404,
      code: "business_unavailable",
    });
  });
});
