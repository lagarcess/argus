// This isolated process keeps its Supabase mock out of other frontend suites.
// @ts-expect-error The repository's minimal Bun ambient declaration omits mock.
import { mock } from "bun:test";
import assert from "node:assert/strict";

let session: { user: { id: string }; access_token: string } | null = null;
mock.module("../../lib/supabase-client", () => ({
  getSupabaseClient: () => ({
    auth: { getSession: async () => ({ data: { session }, error: null }) },
  }),
}));
const api = await import("../../lib/financial-accounts-api");
process.env.NEXT_PUBLIC_MOCK_AUTH = "false";

const userId = crypto.randomUUID();
const accountId = crypto.randomUUID();
const requests: Array<{ url: string; init: RequestInit }> = [];
const unknownBalance = { state: "unknown", amount_minor: null, amount: null, as_of: null, basis: null, activity_since_tracking_minor: 0 };
const zeroBalance = { state: "known", amount_minor: 0, amount: "0.00", as_of: "2026-09-01T09:00:00-04:00", basis: "opening", activity_since_tracking_minor: 0 };
let responseBody: unknown = {};
let rawResponse: string | undefined;
let status = 200;
globalThis.fetch = (async (url: string | URL | Request, init: RequestInit = {}) => {
  requests.push({ url: String(url), init });
  return new Response(rawResponse ?? JSON.stringify(responseBody), { status, headers: { "Content-Type": "application/json" } });
}) as typeof fetch;

const abort = new AbortController();
const create = { type: "cash" as const, currency: "DOP", amount: "92233720368547758.07" };
const edit = { expected_version: 3, nickname: null };
const opening = { expected_version: 3, expected_revision: 2, as_of: "2026-09-01T08:00:00-04:00", reason: "Correct the date" };
const operations = [
  () => api.listFinancialAccounts(userId, abort.signal),
  () => api.getFinancialAccount(userId, accountId, abort.signal),
  () => api.createFinancialAccount(userId, create, "create-attempt", abort.signal),
  () => api.editFinancialAccount(userId, accountId, edit, abort.signal),
  () => api.writeFinancialOpening(userId, accountId, opening, abort.signal),
];

for (const operation of operations) {
  for (const identity of [null, { user: { id: crypto.randomUUID() }, access_token: "other-token" }]) {
    session = identity;
    await assert.rejects(operation(), { name: "ChatAccountChangedError" });
    assert.equal(requests.length, 0);
  }
}
session = { user: { id: userId }, access_token: "refreshed-token" };
responseBody = { accounts: [{ id: accountId, balance: unknownBalance }, { id: crypto.randomUUID(), balance: zeroBalance }] };
const accounts = await operations[0]();
assert.ok(Array.isArray(accounts));
assert.equal(accounts[0].balance.state, "unknown");
assert.equal(accounts[0].balance.amount, null);
assert.equal(accounts[1].balance.state, "known");
assert.equal(accounts[1].balance.amount, "0.00");

rawResponse = `{"id":"${accountId}","balance":{"state":"known","amount":"${create.amount}","amount_minor":9223372036854775807}}`;
for (const operation of operations.slice(1)) {
  const account = await operation();
  assert.ok(!Array.isArray(account));
  assert.equal(account.balance.amount, create.amount);
}
rawResponse = undefined;
assert.deepEqual(requests.map(({ url }) => new URL(url).pathname), [
  "/api/v1/financial-accounts",
  `/api/v1/financial-accounts/${accountId}`,
  "/api/v1/financial-accounts",
  `/api/v1/financial-accounts/${accountId}`,
  `/api/v1/financial-accounts/${accountId}/opening`,
]);
for (const { init } of requests) {
  assert.equal(new Headers(init.headers).get("Authorization"), "Bearer refreshed-token");
  assert.equal(init.credentials, "omit");
  assert.equal(init.signal, abort.signal);
}
assert.equal(requests[2].init.method, "POST");
assert.equal(requests[2].init.body, JSON.stringify(create));
assert.equal(new Headers(requests[2].init.headers).get("Idempotency-Key"), "create-attempt");
assert.equal(requests[3].init.method, "PATCH");
assert.equal(requests[3].init.body, JSON.stringify(edit));
assert.equal(requests[4].init.method, "PUT");
assert.equal(requests[4].init.body, JSON.stringify(opening));
assert.equal(Object.hasOwn(JSON.parse(String(requests[4].init.body)), "amount"), false);

for (const [failureStatus, code] of [
  [404, "financial_accounts_unavailable"], [401, "unauthorized"],
  [403, "account_conversion_required"], [404, "financial_account_not_found"],
  [409, "stale_version"], [409, "idempotency_conflict"],
  [422, "amount_precision"], [422, "date_invalid"],
] as const) {
  status = failureStatus;
  responseBody = { code, status, detail: "Preserve the server failure", context: { field: "amount" } };
  await assert.rejects(operations[1](), { code, status, context: { field: "amount" } });
}

const count = requests.length;
abort.abort();
await assert.rejects(operations[1](), { name: "AbortError" });
assert.equal(requests.length, count);
