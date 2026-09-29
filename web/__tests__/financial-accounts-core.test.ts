import { describe, test } from "bun:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { spawnSync } from "node:child_process";

import { FINANCIAL_ACCOUNT_TYPES } from "../lib/financial-accounts-api";
import {
  AccountAmountInputError,
  formatAccountAmount,
  formatAccountDate,
  liabilityAmountInput,
  parseAccountAmountInput,
} from "../lib/financial-accounts-format";
import {
  createFinancialAccountAttempt,
  createFinancialAccountRequestOwner,
} from "../lib/financial-accounts-requests";

function deferred<T>(): {
  promise: Promise<T>;
  resolve: (value: T) => void;
  reject: (error: Error) => void;
} {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("financial account wire contract", () => {
  test("offers the account types in the landed OpenAPI schema", () => {
    const contract = readFileSync(`${import.meta.dir}/../../docs/api/openapi.yaml`, "utf8");
    const schema = contract.split("    FinancialAccountResponse:\n")[1]?.split("        nature:\n")[0];
    assert.ok(schema);
    const types = [...(schema ?? "").matchAll(/^          - ([a-z_]+)$/gm)].map((match) => match[1]);
    assert.deepEqual(FINANCIAL_ACCOUNT_TYPES, types);
  });

  test("uses the existing authenticated transport without changing its errors", () => {
    const result = spawnSync(process.execPath, [`${import.meta.dir}/fixtures/financial-accounts-transport.ts`], {
      cwd: `${import.meta.dir}/..`,
      encoding: "utf8",
      timeout: 15_000,
    });
    assert.deepEqual({ status: result.status, error: result.error, stderr: result.stderr }, {
      status: 0, error: undefined, stderr: "",
    });
  });
});

describe("lossless financial amount presentation", () => {
  for (const [amount, currency, locale, number] of [
    ["92233720368547758.07", "DOP", "en-US", "92,233,720,368,547,758.07"],
    ["-92233720368547758.07", "DOP", "es-419", "-92,233,720,368,547,758.07"],
    ["1500", "JPY", "en-US", "1,500"],
    ["1.234", "KWD", "es-419", "1.234"],
    ["10.50", "DOP", "en-US", "10.50"],
    ["0.00", "DOP", "es-419", "0.00"],
    ["-0.01", "DOP", "en-US", "-0.01"],
    ["1234.50", "DOP", "es-ES", "1.234,50"],
  ]) {
    test(`retains every digit of ${amount} ${currency} in ${locale}`, () => {
      const display = formatAccountAmount(amount, currency, locale);
      assert.ok(display.includes(currency));
      const displayedNumber = display.replace(currency, "").replace(/\s/g, "");
      assert.equal(displayedNumber, number);
    });
  }

  test("keeps all supplied fraction digits even if they exceed a currency's precision", () => {
    assert.ok(formatAccountAmount("1.005", "DOP", "en-US").includes("1.005"));
    assert.equal(parseAccountAmountInput("1.005", "en-US"), "1.005");
  });

  for (const [input, locale, result] of [
    ["92,233,720,368,547,758.07", "en-US", "92233720368547758.07"],
    ["-1,234.50", "es-419", "-1234.50"],
    ["1.234,50", "es-ES", "1234.50"],
    [" 0.00 ", "en-US", "0.00"],
    ["1500", "en-US", "1500"],
    ["1.234", "es-419", "1.234"],
  ]) {
    test(`normalizes complete ${input} input under ${locale}`, () => {
      assert.equal(parseAccountAmountInput(input, locale), result);
    });
  }

  for (const input of ["", " ", "1,23.45", "12,34,567.89", "1,,000", "1,000,", ".5", "1.", "-", "+1", "1e3", "1.2.3", "USD 1.00", "$1.00", "1 000", "1,000.0x", "1.000,50", "NaN"]) {
    test(`rejects the entire malformed input ${JSON.stringify(input)}`, () => {
      assert.throws(() => parseAccountAmountInput(input, "es-419"), (error: unknown) => {
        assert.ok(error instanceof AccountAmountInputError);
        assert.equal(error.code, "amount_invalid");
        return true;
      });
    });
  }

  for (const [amount, nature, input] of [
    ["-15000.00", "liability", "15000.00"],
    ["200.00", "liability", "-200.00"],
    ["0.00", "liability", "0.00"],
    ["-100.25", "asset", "-100.25"],
  ] as const) {
    test(`adapts ${amount} only from the returned ${nature} nature`, () => {
      assert.equal(liabilityAmountInput(amount, nature), input);
    });
  }

  test("displays the date in the stored zone even across midnight", () => {
    assert.equal(formatAccountDate("2026-09-01T00:30:00Z", "America/Santo_Domingo", "en-US"), "Aug 31, 2026");
    assert.equal(formatAccountDate("2026-09-01T00:30:00Z", "Asia/Tokyo", "en-US"), "Sep 1, 2026");
  });
});

describe("financial account identity lifetime", () => {
  test("retains in-flight work when the same identity refreshes", async () => {
    const owner = createFinancialAccountRequestOwner("account-a");
    const request = deferred<string>();
    let signal: AbortSignal | undefined;
    const pending = owner.execute((nextSignal) => {
      signal = nextSignal;
      return request.promise;
    });
    await Promise.resolve();
    owner.setIdentity("account-a");
    request.resolve("current");
    assert.equal(await pending, "current");
    assert.equal(signal?.aborted, false);
    owner.dispose();
  });

  for (const outcome of ["resolve", "reject"] as const) {
    test(`retires an A -> B -> A operation that ignores abort and later ${outcome}s`, async () => {
      const owner = createFinancialAccountRequestOwner("account-a");
      const request = deferred<string>();
      let signal: AbortSignal | undefined;
      const pending = owner.execute((nextSignal) => {
        signal = nextSignal;
        return request.promise;
      });
      const result = pending.catch((error: unknown) => error);
      await Promise.resolve();
      owner.setIdentity("account-b");
      owner.setIdentity("account-a");
      assert.equal(signal?.aborted, true);
      const error = await result;
      assert.ok(error instanceof DOMException);
      assert.equal(error.name, "AbortError");
      if (outcome === "resolve") request.resolve("old private result");
      else request.reject(new Error("old private failure"));
      await Promise.resolve();
      assert.equal(await owner.execute(async () => "new lifetime"), "new lifetime");
      owner.dispose();
    });
  }

  test("blocks work while signed out and after disposal", async () => {
    const owner = createFinancialAccountRequestOwner();
    let calls = 0;
    const operation = async (): Promise<void> => { calls += 1; };
    await assert.rejects(owner.execute(operation), { name: "AbortError" });
    owner.setIdentity("account-a");
    await owner.execute(operation);
    owner.dispose();
    owner.setIdentity("account-a");
    await assert.rejects(owner.execute(operation), { name: "AbortError" });
    assert.equal(calls, 1);
  });

  test("preserves a current request's original error", async () => {
    const owner = createFinancialAccountRequestOwner("account-a");
    const error = Object.assign(new Error("stale"), { status: 409, code: "stale_version" });
    await assert.rejects(owner.execute(async () => { throw error; }), (received: unknown) => received === error);
    owner.dispose();
  });
});

describe("financial account create attempts", () => {
  test("detaches and freezes the exact payload and key for an uncertain retry", () => {
    const payload = { type: "cash" as const, currency: "DOP", amount: "0.00", nickname: "Cash" };
    const attempt = createFinancialAccountAttempt(payload);
    const serialized = JSON.stringify(attempt.payload);
    payload.amount = "900.01";
    payload.nickname = "New draft";
    assert.equal(JSON.stringify(attempt.payload), serialized);
    assert.equal(Object.isFrozen(attempt), true);
    assert.equal(Object.isFrozen(attempt.payload), true);
    assert.notEqual(createFinancialAccountAttempt(payload).idempotencyKey, attempt.idempotencyKey);
    assert.equal(createFinancialAccountAttempt(payload, "same-attempt").idempotencyKey, "same-attempt");
  });
});
