import { describe, expect, test } from "bun:test";
import type { FinancialAccount } from "../lib/financial-accounts-api";
import {
  accountDraft, createAccountPayload, editAccountPayload, emptyAccountDraft,
  openingAccountPayload, reconcileAccountDraft, requiresAccountReconciliation,
} from "../app/dev/financial-accounts/account-form-state";

const instant = "2026-09-01T09:00:00-04:00";
const zone = "America/Santo_Domingo";

function record(overrides: Partial<FinancialAccount> = {}): FinancialAccount {
  return {
    id: crypto.randomUUID(), type: "checking", nature: "asset", currency: "DOP",
    currency_fraction_digits: 2, nickname: "Daily account", archived: false,
    ownership_share_bps: 10000, version: 3, created_at: instant, updated_at: instant,
    balance: { state: "unknown", amount_minor: null, amount: null, as_of: null, basis: null, activity_since_tracking_minor: null },
    opening: null, ...overrides,
  };
}

function withOpening(amount: string, overrides: Partial<FinancialAccount> = {}): FinancialAccount {
  const revision = { revision: 2, amount_minor: null, amount, as_of: instant, time_zone: zone, reason: "Corrected source", recorded_at: instant, recorded_by: null };
  return record({
    opening: { ...revision, record_id: crypto.randomUUID(), revisions: [revision] },
    balance: { state: "known", amount_minor: null, amount, as_of: instant, basis: "opening", activity_since_tracking_minor: 0 },
    ...overrides,
  });
}

describe("Accounts form snapshots", () => {
  test("unknown creation omits amount while an explicit zero is preserved", () => {
    const unknown = emptyAccountDraft("DOP");
    expect(createAccountPayload(unknown, "en", instant, zone).amount).toBeUndefined();
    expect(createAccountPayload({ ...unknown, amount: "0" }, "en", instant, zone)).toMatchObject({ amount: "0", as_of: instant, time_zone: zone });
  });

  test("nickname clearing remains an explicit change at the original version", () => {
    const snapshot = record();
    expect(editAccountPayload(snapshot, { ...accountDraft(snapshot), nickname: "" })).toEqual({ expected_version: snapshot.version, nickname: "" });
    expect(snapshot.nickname).not.toBe("");
  });

  test.each(["-420.50", "0.00", "128.00"])("date-only liability correction never resends amount %s", (amount) => {
    const snapshot = withOpening(amount, { type: "credit_card", nature: "liability" });
    const draft = { ...accountDraft(snapshot), asOf: "2026-08-31T09:00:00-04:00", reason: "Correct statement date" };
    expect(openingAccountPayload(snapshot, draft, "en")).toEqual({
      expected_version: snapshot.version, expected_revision: snapshot.opening?.revision,
      as_of: draft.asOf, reason: draft.reason,
    });
  });

  test("liability amount change is positive owed, with untouched date and zone omitted", () => {
    const snapshot = withOpening("-420.50", { type: "other_debt", nature: "liability" });
    expect(accountDraft(snapshot).amount).toBe("420.50");
    expect(openingAccountPayload(snapshot, { ...accountDraft(snapshot), amount: "500.50", reason: "Correct amount" }, "en")).toEqual({
      expected_version: snapshot.version, expected_revision: snapshot.opening?.revision,
      amount: "500.50", reason: "Correct amount",
    });
  });

  test("first opening binds the snapshot version and a null record revision", () => {
    const snapshot = record();
    expect(openingAccountPayload(snapshot, { ...accountDraft(snapshot), amount: "9007199254740993.01" }, "en")).toEqual({
      expected_version: snapshot.version, expected_revision: null, amount: "9007199254740993.01",
    });
  });

  test("explicit adoption retains edits and refreshes only untouched metadata", () => {
    const original = record();
    const draft = { ...accountDraft(original), nickname: "My revised nickname" };
    const current = { ...original, version: original.version + 1, currency: "USD" };
    expect(editAccountPayload(original, draft).expected_version).toBe(original.version);
    const adopted = reconcileAccountDraft(original, current, draft);
    expect(adopted.nickname).toBe(draft.nickname);
    expect(adopted.currency).toBe(current.currency);
    expect(editAccountPayload(current, adopted)).toEqual({ expected_version: current.version, nickname: draft.nickname });
    expect(draft.currency).toBe(original.currency);
  });

  test("adopting a newer amount cannot turn a date-only correction into an amount overwrite", () => {
    const original = withOpening("-100.00", { nature: "liability", type: "credit_card" });
    const current = withOpening("-150.00", { ...original, opening: { ...original.opening!, amount: "-150.00", revision: 3 }, version: 4 });
    const draft = { ...accountDraft(original), asOf: "2026-08-31T22:00:00-04:00", reason: "Correct statement date" };
    const adopted = reconcileAccountDraft(original, current, draft);
    expect(adopted.amount).toBe("150.00");
    expect(openingAccountPayload(current, adopted, "en").amount).toBeUndefined();
    expect(openingAccountPayload(current, adopted, "en").expected_revision).toBe(current.opening?.revision);
  });

  test("a changed amount does not rewrite an unusual original instant or IANA zone", () => {
    const snapshot = withOpening("10.00");
    snapshot.opening = { ...snapshot.opening!, as_of: "2026-08-31T23:40:00.123456+05:45", time_zone: "Asia/Kathmandu" };
    const draft = { ...accountDraft(snapshot), amount: "20.00", reason: "Updated statement" };
    const payload = openingAccountPayload(snapshot, draft, "en");
    expect(payload.as_of).toBeUndefined();
    expect(payload.time_zone).toBeUndefined();
    expect(draft.asOf).toBe(snapshot.opening.as_of);
  });

  test.each([
    { currency: "JPY" },
    { type: "credit_card" as const, nature: "liability" as const },
    { currency: "JPY", type: "credit_card" as const, nature: "liability" as const },
  ])("adopting a changed currency or nature requires deliberate amount re-entry: %p", (changes) => {
    const original = record();
    const draft = { ...accountDraft(original), amount: "125.00" };
    const current = { ...original, ...changes, version: original.version + 1 };
    const adopted = reconcileAccountDraft(original, current, draft);
    expect(draft.amount).toBe("125.00");
    expect(adopted.amount).toBe("");
    expect(() => openingAccountPayload(current, adopted, "en")).toThrow();
    expect(openingAccountPayload(current, { ...adopted, amount: "200" }, "en")).toEqual({
      expected_version: current.version, expected_revision: null, amount: "200",
    });
  });

  test("only stale or uncertain write outcomes require canonical reconciliation", () => {
    expect(requiresAccountReconciliation({ status: 409, code: "stale_version" })).toBe(true);
    expect(requiresAccountReconciliation(new TypeError("Network failed"))).toBe(true);
    expect(requiresAccountReconciliation({ status: 503 })).toBe(true);
    expect(requiresAccountReconciliation({ status: 422, code: "amount_precision" })).toBe(false);
  });
});
