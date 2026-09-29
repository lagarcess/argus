import type { FinancialAccount } from "../lib/financial-accounts-api";
import {
  accountPath, captureEvidence, createAccount, expect, financialResponse,
  labels, nickname, reopen, requestBody, submitEdit, test,
} from "./financial-accounts.helpers";

test("@smoke registered person creates and reopens a durable account", async ({ page, local }, info) => {
  await local.login();
  const name = nickname("Everyday account");
  const account = await createAccount(local, { nickname: name, amount: "12750.25" });
  expect(account.balance.state).toBe("known");
  expect(account.balance.amount).toBe("12750.25");
  await page.reload();
  await expect(page.getByTestId("account-detail")).toContainText(name);
  await expect(page.getByTestId("account-detail")).toContainText("12,750.25");
  expect((await local.get(account.id)).balance.amount).toBe(account.balance.amount);
  await captureEvidence(page, info, local.config, [
    "Existing AuthForm signed in registered user A against local Supabase.",
    "UI create returned HTTP 201 and a decimal-string balance.",
    "Page reload and authenticated GET reopened the same durable record and cents.",
  ]);
});

test("@journey metadata edits explicitly clear nickname and archive restores the same balance", async ({ page, local }, info) => {
  await local.login();
  const account = await createAccount(local, { nickname: nickname("Salary"), amount: "9876.54" });
  await page.getByRole("button", { name: labels.edit }).click();
  const dialog = page.getByRole("dialog");
  await dialog.getByLabel(/^(Nickname \(optional\)|Nickname|Nombre \(opcional\)|Apodo \(opcional\))$/).fill("");
  await dialog.getByLabel(/^(Type|Tipo)$/).selectOption("savings");
  await dialog.getByLabel(/^(Ownership share \(%\)|Participación \(%\))$/).fill("50");
  const editedRequest = page.waitForRequest((request) => request.method() === "PATCH" && request.url().endsWith(`/financial-accounts/${account.id}`));
  const edited = await submitEdit(local, dialog, account);
  const payload = requestBody(await editedRequest);
  expect(payload.expected_version).toBe(account.version);
  expect(Object.hasOwn(payload, "nickname")).toBe(true);
  expect(["", null]).toContain(payload.nickname);
  expect(edited.nickname).toBeNull();
  expect(edited.type).toBe("savings");
  expect(edited.ownership_share_bps).toBe(5000);
  expect(edited.balance.amount).toBe(account.balance.amount);

  for (const [action, archived] of [["Archive", true], ["Restore", false]] as const) {
    await page.getByRole("button", { name: action, exact: true }).click();
    const confirmation = page.getByRole("dialog").or(page.getByRole("alertdialog"));
    const result = financialResponse(page, local.config, "PATCH", `/financial-accounts/${account.id}`);
    await confirmation.getByRole("button", { name: action, exact: true }).click();
    const response = await result;
    expect(response.status()).toBe(200);
    const saved = await response.json() as FinancialAccount;
    expect(saved.archived).toBe(archived);
    expect(saved.balance).toEqual(edited.balance);
    expect((await local.list()).find((item) => item.id === account.id)?.archived).toBe(archived);
    await expect(confirmation).toHaveCount(0);
  }
  await reopen(local, edited);
  await expect(page.getByTestId("account-detail")).toContainText("Savings");
  await captureEvidence(page, info, local.config, [
    "Metadata PATCH sent the version the form opened with and explicit nickname clearing.",
    "Type and ownership share persisted without changing the opening balance.",
    "Archive and restore preserved record identity, list membership, and financial facts.",
  ]);
});

test("@journey unknown differs from zero and first opening preserves its chosen instant and zone", async ({ page, local }, info) => {
  await local.login();
  const zero = await createAccount(local, { nickname: nickname("Zero cash"), type: "cash", amount: "0" });
  expect(zero.balance.state).toBe("known");
  expect(zero.balance.amount).toBe("0.00");
  await expect(page.getByTestId("account-detail")).toContainText("0.00");
  await page.goto(accountPath);
  const unknown = await createAccount(local, { nickname: nickname("Pending estimate"), type: "property" });
  expect(unknown.balance.state).toBe("unknown");
  expect(unknown.balance.amount).toBeNull();
  expect(unknown.opening).toBeNull();
  await expect(page.getByTestId("account-detail")).toContainText("Balance unknown");
  await page.getByRole("button", { name: labels.addOpening }).click();
  const dialog = page.getByRole("dialog");
  const asOf = "2026-01-15T07:45:00+05:45";
  const timeZone = "Asia/Kathmandu";
  const amount = "90071992547409.93";
  await dialog.getByLabel("Amount", { exact: true }).fill(amount);
  await dialog.getByLabel("Date and time (with UTC offset)").fill(asOf);
  await dialog.getByLabel("Time zone", { exact: true }).fill(timeZone);
  const pending = financialResponse(page, local.config, "PUT", `/financial-accounts/${unknown.id}/opening`);
  await dialog.getByRole("button", { name: labels.saveOpening }).click();
  const response = await pending;
  expect(response.status()).toBe(200);
  const payload = requestBody(response.request());
  expect(payload.expected_version).toBe(unknown.version);
  expect(payload.expected_revision).toBeNull();
  const saved = await response.json() as FinancialAccount;
  expect(saved.balance.amount).toBe(amount);
  expect(saved.opening?.as_of).toBe(asOf);
  expect(saved.opening?.time_zone).toBe(timeZone);
  await page.reload();
  await expect(page.getByTestId("account-detail")).toContainText("90,071,992,547,409.93");
  expect((await local.get(saved.id)).opening).toEqual(saved.opening);
  await captureEvidence(page, info, local.config, [
    "A known zero and an unknown account produced different API and UI states.",
    "First opening sent null expected_revision and the original account version.",
    "Amount beyond JavaScript safe integer minor units reopened without lost cents.",
    "The chosen offset-aware instant and IANA zone survived the durable reread.",
  ]);
});

test("@journey debt corrections use positive owed input and date-only changes omit amount", async ({ page, local }, info) => {
  await local.login();
  const debt = await createAccount(local, { nickname: nickname("Card balance"), type: "credit_card", amount: "15000.75" });
  expect(debt.nature).toBe("liability");
  expect(debt.balance.amount).toBe("-15000.75");
  await page.getByRole("button", { name: labels.correctOpening }).click();
  let dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Amount owed", { exact: true })).toHaveValue("15000.75");
  await dialog.getByLabel("Amount owed", { exact: true }).fill("14000.25");
  const amountReason = "Corrected the statement amount";
  await dialog.getByLabel("Reason for correction").fill(amountReason);
  let pending = financialResponse(page, local.config, "PUT", `/financial-accounts/${debt.id}/opening`);
  await dialog.getByRole("button", { name: labels.saveCorrection }).click();
  let response = await pending;
  expect(response.status()).toBe(200);
  const amountPayload = requestBody(response.request());
  expect(amountPayload.amount).toBe("14000.25");
  expect(amountPayload).not.toHaveProperty("as_of");
  expect(amountPayload).not.toHaveProperty("time_zone");
  const corrected = await response.json() as FinancialAccount;
  expect(corrected.balance.amount).toBe("-14000.25");
  expect(corrected.opening?.as_of).toBe(debt.opening?.as_of);
  expect(corrected.opening?.time_zone).toBe(debt.opening?.time_zone);
  await expect(dialog).toHaveCount(0);

  await page.getByRole("button", { name: labels.correctOpening }).click();
  dialog = page.getByRole("dialog");
  await expect(dialog.getByLabel("Amount owed", { exact: true })).toHaveValue("14000.25");
  const correctedDate = "2026-01-16T09:30:00-04:00";
  const dateReason = "Corrected the statement date";
  await dialog.getByLabel("Date and time (with UTC offset)").fill(correctedDate);
  await dialog.getByLabel("Reason for correction").fill(dateReason);
  pending = financialResponse(page, local.config, "PUT", `/financial-accounts/${debt.id}/opening`);
  await dialog.getByRole("button", { name: labels.saveCorrection }).click();
  response = await pending;
  expect(response.status()).toBe(200);
  const datePayload = requestBody(response.request());
  expect(datePayload.expected_version).toBe(corrected.version);
  expect(datePayload.expected_revision).toBe(corrected.opening?.revision);
  expect(datePayload).not.toHaveProperty("amount");
  expect(datePayload).not.toHaveProperty("time_zone");
  const dated = await response.json() as FinancialAccount;
  expect(dated.balance.amount).toBe(corrected.balance.amount);
  expect(dated.opening?.as_of).toBe(correctedDate);
  expect(dated.opening?.time_zone).toBe(debt.opening?.time_zone);
  expect(dated.opening?.revisions).toHaveLength(3);
  expect(dated.opening?.revisions[0]).toEqual(debt.opening?.revisions[0]);
  await expect(dialog).toHaveCount(0);
  await expect(page.getByTestId("account-detail")).toContainText(amountReason);
  await expect(page.getByTestId("account-detail")).toContainText(dateReason);
  await captureEvidence(page, info, local.config, [
    "Negative liability read became positive owed input exactly once.",
    "Amount correction preserved the untouched stored instant and IANA zone.",
    "Date-only correction omitted amount and preserved the signed balance.",
    "Three real revisions remain visible with both correction reasons.",
  ]);
});

for (const scenario of [
  { label: "A", width: 1440, height: 1000, theme: "light", language: "en" },
  { label: "B", width: 834, height: 1112, theme: "dark", language: "es-419" },
  { label: "B", width: 390, height: 844, theme: "system", language: "es-419" },
] as const) {
  test(`@responsive ${scenario.language} ${scenario.width}px ${scenario.theme} persists with keyboard and history`, async ({ page, local }, info) => {
    await page.setViewportSize({ width: scenario.width, height: scenario.height });
    await page.emulateMedia({ colorScheme: "dark" });
    await local.login(scenario.label);
    await page.getByLabel(/^(Appearance|Apariencia)$/).selectOption(scenario.theme);
    await page.reload();
    await expect(page.getByLabel(/^(Appearance|Apariencia)$/)).toHaveValue(scenario.theme);
    await expect(page.locator("html")).toHaveClass(scenario.theme === "light" ? /(?:^|\s)light(?:\s|$)/ : /(?:^|\s)dark(?:\s|$)/);
    await expect(page.locator("h1")).toHaveText(scenario.language === "en" ? "Accounts" : "Cuentas");
    const name = nickname(scenario.language === "en" ? "Household reserve for upcoming commitments" : "Reserva familiar para los próximos compromisos");
    const account = await createAccount(local, { nickname: name, amount: "12345.67" });
    const addOrEdit = page.getByRole("button", { name: labels.edit });
    await addOrEdit.focus();
    await page.keyboard.press("Enter");
    const dialog = page.getByRole("dialog");
    await expect(dialog).toBeVisible();
    await expect.poll(() => dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true);
    for (let index = 0; index < 12; index += 1) {
      await page.keyboard.press("Tab");
      await expect.poll(() => dialog.evaluate((element) => element.contains(document.activeElement))).toBe(true);
    }
    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);
    await expect(addOrEdit).toBeFocused();
    await page.goto(accountPath);
    await page.getByTestId("accounts-list").getByRole("button", { name: new RegExp(name) }).click();
    await expect(page).toHaveURL(new RegExp(`account=${account.id}`));
    await page.goBack();
    await expect(page).not.toHaveURL(/account=/);
    await page.goForward();
    await expect(page.getByTestId("account-detail")).toContainText(name);
    if (scenario.width === 390) {
      await page.evaluate(() => { document.documentElement.style.fontSize = "200%"; });
      await page.getByRole("button", { name: labels.edit }).scrollIntoViewIfNeeded();
      await page.getByRole("button", { name: labels.edit }).click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await page.getByRole("dialog").getByRole("button", { name: labels.saveEdit }).scrollIntoViewIfNeeded();
    }
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    expect(overflow, "Long labels and larger text do not create horizontal page overflow").toBe(false);
    await captureEvidence(page, info, local.config, [
      "Profile-owned locale loaded after real sign-in.",
      "Appearance selection and rendered theme survived reload.",
      "Keyboard opened the dialog, focus stayed inside, and Escape returned focus.",
      "Browser back and forward preserved account navigation.",
      "Long account labels remained reachable without horizontal page overflow.",
    ], { language: scenario.language, theme: scenario.theme, textScalePercent: scenario.width === 390 ? 200 : 100 });
  });
}
