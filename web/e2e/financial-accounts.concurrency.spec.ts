import type { FinancialAccount } from "../lib/financial-accounts-api";
import {
  accountPath, captureEvidence, createAccount, expect, fillCreate, financialResponse,
  labels, LocalSession, nickname, openCreate, protectLocalNetwork, requestBody, test,
} from "./financial-accounts.helpers";

test("@concurrency a lost create response retries the immutable attempt exactly once", async ({ page, local }, info) => {
  await local.login();
  const name = nickname("Replay-safe account");
  const attempts: { body: unknown; key: string | undefined; status: number; id: string }[] = [];
  await page.route(`${local.config.apiURL}/financial-accounts`, async (route) => {
    if (route.request().method() !== "POST") return route.fallback();
    const response = await route.fetch();
    const saved = await response.json() as FinancialAccount;
    attempts.push({ body: requestBody(route.request()), key: route.request().headers()["idempotency-key"], status: response.status(), id: saved.id });
    if (attempts.length === 1) await route.abort("connectionreset");
    else await route.fulfill({ response });
  });
  const dialog = await openCreate(page);
  await fillCreate(dialog, { nickname: name, amount: "125.50" });
  await dialog.getByRole("button", { name: labels.add }).click();
  await expect(page.getByTestId("create-attempt-uncertain")).toBeVisible();
  expect(attempts).toHaveLength(1);
  await expect(dialog.getByLabel(/Nickname/)).toBeDisabled();
  await expect(dialog.getByLabel(/Starting balance/)).toBeDisabled();
  expect((await local.list()).filter((account) => account.nickname === name)).toHaveLength(1);
  await page.getByRole("button", { name: "Retry same account", exact: true }).click();
  await expect(page.getByTestId("account-detail")).toContainText(name);
  expect(attempts).toHaveLength(2);
  expect(attempts[0].status).toBe(201);
  expect(attempts[1].status).toBe(200);
  expect(attempts[1].body).toEqual(attempts[0].body);
  expect(attempts[0].key).toBeTruthy();
  expect(attempts[1].key).toBe(attempts[0].key);
  expect(attempts[1].id).toBe(attempts[0].id);
  expect((await local.list()).filter((account) => account.nickname === name)).toHaveLength(1);
  await captureEvidence(page, info, local.config, [
    "The first real POST committed, then its browser response was deliberately lost.",
    "Uncertain creation froze inputs and did not automatically resend.",
    "Explicit retry reused the exact payload and Idempotency-Key, returned 200, and left one record.",
  ]);
});

test("@concurrency stale metadata retains the original version and needs explicit adoption", async ({ page, local }, info) => {
  await local.login();
  const account = await createAccount(local, { nickname: nickname("Original details") });
  const draft = nickname("Unsaved local details");
  const concurrentName = nickname("Concurrent saved details");
  await page.getByRole("button", { name: labels.edit }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(/Nickname/).fill(draft);
  const concurrent = await local.request("PATCH", `/financial-accounts/${account.id}`, {
    expected_version: account.version, nickname: concurrentName,
  });
  expect(concurrent.status).toBe(200);
  let pending = financialResponse(page, local.config, "PATCH", `/financial-accounts/${account.id}`);
  await dialog.getByRole("button", { name: labels.saveEdit }).click();
  let response = await pending;
  expect(response.status()).toBe(409);
  expect((await response.json()).code).toBe("stale_version");
  expect(requestBody(response.request()).expected_version).toBe(account.version);
  await expect(dialog.getByLabel(/Nickname/)).toHaveValue(draft);
  await expect(page.getByTestId("accounts-reconciliation")).toContainText("Original snapshot");
  await page.getByRole("button", { name: "Review current account", exact: true }).click();
  await expect(page.getByTestId("accounts-reconciliation")).toContainText(concurrentName);
  expect((await local.get(account.id)).nickname).toBe(concurrentName);
  await page.getByRole("button", { name: "Use current version and keep my draft", exact: true }).click();
  await expect(dialog.getByLabel(/Nickname/)).toHaveValue(draft);
  pending = financialResponse(page, local.config, "PATCH", `/financial-accounts/${account.id}`);
  await dialog.getByRole("button", { name: labels.saveEdit }).click();
  response = await pending;
  expect(response.status()).toBe(200);
  expect(requestBody(response.request()).expected_version).toBe(concurrent.body.version);
  expect((await local.get(account.id)).nickname).toBe(draft);
  await expect(dialog).toHaveCount(0);
  await captureEvidence(page, info, local.config, [
    "A second authenticated API request changed the saved account while the UI draft stayed open.",
    "The UI submitted its original version, received stale_version, and preserved the draft.",
    "Review displayed current facts; only explicit adoption enabled a write using the newer version.",
  ]);
});

test("@concurrency stale unknown opening cannot silently change currency or debt meaning", async ({ page, local }, info) => {
  await local.login();
  const account = await createAccount(local, { nickname: nickname("Opening concurrency") });
  await page.getByRole("button", { name: labels.addOpening }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel("Amount", { exact: true }).fill("125.50");
  const concurrent = await local.request("PATCH", `/financial-accounts/${account.id}`, {
    expected_version: account.version, type: "credit_card", currency: "JPY",
  });
  expect(concurrent.status).toBe(200);
  const attempts: Record<string, unknown>[] = [];
  page.on("request", (request) => {
    if (request.method() === "PUT" && request.url().endsWith(`/financial-accounts/${account.id}/opening`)) attempts.push(requestBody(request));
  });
  let pending = financialResponse(page, local.config, "PUT", `/financial-accounts/${account.id}/opening`);
  await dialog.getByRole("button", { name: labels.saveOpening }).click();
  let response = await pending;
  expect(response.status()).toBe(409);
  expect((await response.json()).code).toBe("stale_version");
  expect(attempts[0]).toMatchObject({ expected_version: account.version, expected_revision: null, amount: "125.50" });
  await expect(dialog.getByLabel("Amount", { exact: true })).toHaveValue("125.50");
  expect((await local.get(account.id)).opening).toBeNull();
  await page.getByRole("button", { name: "Review current account", exact: true }).click();
  await expect(page.getByTestId("accounts-reconciliation")).toContainText("JPY");
  await expect(dialog.getByLabel("Amount", { exact: true })).toHaveValue("125.50");
  await page.getByRole("button", { name: "Use current version and keep my draft", exact: true }).click();
  await expect(dialog.getByLabel("Amount owed", { exact: true })).toHaveValue("");
  await dialog.getByRole("button", { name: labels.saveOpening }).click();
  await expect(dialog.getByRole("alert")).toBeVisible();
  expect(attempts).toHaveLength(1);
  await dialog.getByLabel("Amount owed", { exact: true }).fill("125");
  pending = financialResponse(page, local.config, "PUT", `/financial-accounts/${account.id}/opening`);
  await dialog.getByRole("button", { name: labels.saveOpening }).click();
  response = await pending;
  expect(response.status()).toBe(200);
  expect(requestBody(response.request())).toMatchObject({ expected_version: concurrent.body.version, expected_revision: null, amount: "125" });
  const saved = await response.json() as FinancialAccount;
  expect(saved.currency).toBe("JPY");
  expect(saved.nature).toBe("liability");
  expect(saved.balance.amount).toBe("-125");
  await expect(dialog).toHaveCount(0);
  await captureEvidence(page, info, local.config, [
    "Concurrent currency and nature changes caused the original opening version to fail with 409.",
    "The old amount remained visible during review and no opening was written.",
    "Adopting different currency/nature cleared the amount; an empty save could not write.",
    "Explicitly reentered positive owed amount saved under the reviewed JPY liability facts.",
  ]);
});

for (const method of ["PATCH", "PUT"] as const) {
  test(`@concurrency uncertain ${method} rereads and reconciles before another write`, async ({ page, local }, info) => {
    await local.login();
    const account = await createAccount(local, { nickname: nickname(`Uncertain ${method}`), amount: "100.00" });
    const endpoint = `/financial-accounts/${account.id}${method === "PUT" ? "/opening" : ""}`;
    let writes = 0;
    let canonicalReads = 0;
    page.on("request", (request) => {
      if (request.method() === "GET" && request.url() === `${local.config.apiURL}/financial-accounts/${account.id}`) canonicalReads += 1;
    });
    await page.route(`${local.config.apiURL}${endpoint}`, async (route) => {
      if (route.request().method() !== method) return route.fallback();
      writes += 1;
      if (writes > 1) return route.fallback();
      const response = await route.fetch();
      expect(response.status()).toBe(200);
      await route.abort("connectionreset");
    });
    await page.getByRole("button", { name: method === "PATCH" ? labels.edit : labels.correctOpening }).click();
    const dialog = page.getByRole("dialog");
    const firstName = nickname("First uncertain edit");
    if (method === "PATCH") await dialog.getByLabel(/Nickname/).fill(firstName);
    else {
      await dialog.getByLabel("Amount", { exact: true }).fill("200.00");
      await dialog.getByLabel("Reason for correction").fill("First correction with lost response");
    }
    const save = dialog.getByRole("button", { name: method === "PATCH" ? labels.saveEdit : labels.saveCorrection });
    await save.click();
    await expect(page.getByTestId("accounts-reconciliation")).toBeVisible();
    expect(writes).toBe(1);
    const committed = await local.get(account.id);
    expect(committed.version).toBe(account.version + 1);
    if (method === "PATCH") expect(committed.nickname).toBe(firstName);
    else expect(committed.balance.amount).toBe("200.00");
    await expect(save).toBeDisabled();
    await page.getByRole("button", { name: "Review current account", exact: true }).click();
    await expect(page.getByRole("button", { name: "Use current version and keep my draft", exact: true })).toBeEnabled();
    expect(canonicalReads).toBeGreaterThan(0);
    expect(writes).toBe(1);
    await page.getByRole("button", { name: "Use current version and keep my draft", exact: true }).click();
    if (method === "PATCH") await dialog.getByLabel(/Nickname/).fill(nickname("Reconciled edit"));
    else await dialog.getByLabel("Amount", { exact: true }).fill("250.00");
    const pending = financialResponse(page, local.config, method, endpoint);
    await save.click();
    const response = await pending;
    expect(response.status()).toBe(200);
    expect(requestBody(response.request()).expected_version).toBe(committed.version);
    expect(writes).toBe(2);
    const saved = await local.get(account.id);
    expect(saved.version).toBe(account.version + 2);
    if (method === "PUT") expect(saved.opening?.revisions).toHaveLength(3);
    await expect(dialog).toHaveCount(0);
    await captureEvidence(page, info, local.config, [
      `${method} committed to Postgres before its response was lost.`,
      "The form blocked resubmission and performed no automatic write retry.",
      "A real canonical GET and explicit adoption preceded the next user write.",
    ]);
  });
}

test("@concurrency two real sessions isolate records and a late identity response cannot restore private drafts", async ({ page, context, browser, local }, info) => {
  await local.login();
  const accountA = await createAccount(local, { nickname: nickname("Private account A"), amount: "15.25" });
  const secondContext = await browser.newContext({ baseURL: local.config.appURL, serviceWorkers: "block" });
  const denied = await protectLocalNetwork(secondContext, local.config);
  let accountB: FinancialAccount;
  try {
    const pageB = await secondContext.newPage();
    const sessionB = new LocalSession(pageB, local.config);
    await sessionB.login("B");
    accountB = await createAccount(sessionB, { nickname: nickname("Private account B"), amount: "25.50" });
    expect((await sessionB.list()).some((item) => item.id === accountA.id)).toBe(false);
    expect((await local.list()).some((item) => item.id === accountB.id)).toBe(false);
    const foreign = await sessionB.request<{ code: string }>("GET", `/financial-accounts/${accountA.id}`);
    expect(foreign.status).toBe(404);
    expect(foreign.body.code).toBe("financial_account_not_found");
    expect(denied()).toBe(0);
  } finally {
    await secondContext.close();
  }

  const switcher = await context.newPage();
  const switchingSession = new LocalSession(switcher, local.config);
  await switcher.goto(accountPath);
  await expect(switcher.getByTestId("accounts-list")).toBeVisible();
  await page.getByRole("button", { name: labels.edit }).click();
  const draft = nickname("Never save this private draft");
  await page.getByRole("dialog").getByLabel(/Nickname/).fill(draft);
  let release!: () => void;
  let responseReady!: () => void;
  let responseRetired!: () => void;
  const waitForRelease = new Promise<void>((resolve) => { release = resolve; });
  const ready = new Promise<void>((resolve) => { responseReady = resolve; });
  const retired = new Promise<void>((resolve) => { responseRetired = resolve; });
  await page.route(`${local.config.apiURL}/me`, async (route) => {
    const response = await route.fetch();
    responseReady();
    await waitForRelease;
    try { await route.fulfill({ response }); } catch { /* Session invalidation may already abort this request. */ }
    responseRetired();
  }, { times: 1 });
  await page.evaluate(() => window.dispatchEvent(new Event("focus")));
  await ready;
  await switcher.getByRole("button", { name: labels.signOut }).click();
  await switchingSession.login("B");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByTestId("accounts-list")).not.toContainText(accountA.nickname!);
  await expect(page.getByTestId("accounts-list")).toContainText(accountB!.nickname!);
  await page.evaluate(({ oldName, draftValue }) => {
    const state = { leaked: false };
    Object.assign(window, { accountsIdentityProbe: state });
    const inspect = () => {
      if (document.body.textContent?.includes(oldName) || [...document.querySelectorAll("input")].some((input) => input.value === draftValue)) state.leaked = true;
    };
    new MutationObserver(inspect).observe(document.body, { subtree: true, childList: true, attributes: true });
    inspect();
  }, { oldName: accountA.nickname!, draftValue: draft });
  release();
  await retired;
  await page.evaluate(() => new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
  await expect(page.getByTestId("accounts-list")).toContainText(accountB!.nickname!);
  const leaked = await page.evaluate(() => (window as Window & { accountsIdentityProbe?: { leaked: boolean } }).accountsIdentityProbe?.leaked);
  expect(leaked).toBe(false);
  await expect(page.locator("input")).not.toHaveValue(draft);
  await captureEvidence(page, info, local.config, [
    "Two independent real authenticated browser sessions listed only their own records.",
    "User B received the owner-safe 404 for user A's account.",
    "A second tab signed out and signed in as B through the existing auth UI.",
    "The old draft was cleared and a delayed real response from A never repainted A's data or draft.",
  ]);
});
