import { afterEach, describe, expect, test } from "bun:test";

import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  deletionEndsSession,
  endSessionKeepingSurface,
  requestAccountDeletion,
} from "@/lib/account-deletion-api";

type Call = { url: string; body: unknown };

function respond(
  answers: Array<{ status: number; body: unknown } | Error>,
): Call[] {
  const calls: Call[] = [];
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({
      url: String(input),
      body: init?.body ? JSON.parse(String(init.body)) : null,
    });
    const answer = answers.shift();
    if (!answer) throw new Error("unexpected request");
    if (answer instanceof Error) throw answer;
    return new Response(JSON.stringify(answer.body), {
      status: answer.status,
      headers: { "Content-Type": "application/json" },
    });
  }) as typeof fetch;
  return calls;
}

describe("account deletion outcomes (Lane 6)", () => {
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

  test("done and 202 in_progress map to their own states", async () => {
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    respond([
      { status: 200, body: { status: "done", pending: [] } },
      { status: 202, body: { status: "in_progress", pending: ["apple"] } },
    ]);
    expect(await requestAccountDeletion("en")).toBe("success");
    expect(await requestAccountDeletion("en")).toBe("in_progress");
  });

  test("a 503 after the lock is in progress, not a failure", async () => {
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    respond([{ status: 503, body: { code: "account_deletion_incomplete" } }]);
    expect(await requestAccountDeletion("en")).toBe("in_progress");
  });

  test("nothing happened: unavailable and network failures throw for a retry", async () => {
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    respond([{ status: 503, body: { code: "account_deletion_unavailable" } }]);
    await expect(requestAccountDeletion("en")).rejects.toMatchObject({
      status: 503,
      code: "account_deletion_unavailable",
    });
    respond([new TypeError("network down")]);
    await expect(requestAccountDeletion("en")).rejects.toThrow("network down");
  });

  test("with the command off (404) support gets a ticket", async () => {
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    const calls = respond([
      { status: 404, body: { code: "not_found" } },
      { status: 200, body: { success: true } },
    ]);
    expect(await requestAccountDeletion("es-419")).toBe("requested");
    expect(calls[0].url).toEndWith("/account/delete");
    expect(calls[0].body).toEqual({ confirm: true });
    expect(calls[1].url).toEndWith("/feedback");
    expect(calls[1].body).toMatchObject({
      type: "account_deletion_request",
      context: { source: "profile_modal", profile_language: "es-419" },
    });
  });

  test("with the command off and the ticket failing, only email is left", async () => {
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    respond([
      { status: 404, body: { code: "not_found" } },
      { status: 500, body: { code: "internal_error" } },
    ]);
    expect(await requestAccountDeletion("en")).toBe("unavailable");
  });

  test("deleted or locked ends the session on the result; nothing else does", () => {
    expect(deletionEndsSession("success")).toBe(true);
    expect(deletionEndsSession("in_progress")).toBe(true);
    for (const other of ["requested", "unavailable", "error", "idle", "submitting"]) {
      expect(deletionEndsSession(other)).toBe(false);
    }
  });

  test("the sign-out keeps the surface: the boundary hears first", async () => {
    const order: string[] = [];
    await endSessionKeepingSurface(
      { beginConversion: () => order.push("boundary") },
      async () => {
        order.push("signOut");
        throw new Error("network");
      },
    );
    expect(order).toEqual(["boundary", "signOut"]);
  });

  test("the menu signs out on the result, and Done leaves (Marcus #801 N2)", () => {
    const root = join(import.meta.dir, "..");
    const menu = readFileSync(join(root, "components/sidebar/ProfileMenu.tsx"), "utf-8");
    const chat = readFileSync(join(root, "components/chat/ChatInterface.tsx"), "utf-8");
    expect(menu).toContain(
      "if (deletionEndsSession(outcome)) onLogout({ afterAccountDeletion: true });",
    );
    const close = menu.slice(menu.indexOf("const handleCloseDeleteRequest"));
    expect(close.slice(0, close.indexOf("}, [deleteRequestState, onLogout]);"))).toContain(
      "onLogout();",
    );
    expect(chat).toContain(
      "if (options.afterAccountDeletion) return endSessionKeepingSurface(accountBoundary);",
    );
  });
});
