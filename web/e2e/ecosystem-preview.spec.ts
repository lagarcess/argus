import type { Locator, Page } from "@playwright/test";
import { LANGUAGE_STORAGE_KEY, THEME_STORAGE_KEY } from "../lib/browser-storage";
import { DESKTOP_MIN_WIDTH_PX, TABLET_MIN_WIDTH_PX } from "../lib/responsive-layout";
import { DCA_CONFIRMATION, PREVIEW_VIEWS, RECENTS, SAMPLE, previewCopy, type SampleAccount } from "../app/dev/ecosystem/preview-content";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";
import {
  CELLS,
  assertDialogFocus,
  assertFocusInsideDialog,
  assertLastControlReachable,
  assertNoHorizontalOverflow,
  capture,
  chooseView,
  controls,
  enlargeText,
  expect,
  openPreview,
  test,
  type View,
} from "./ecosystem-preview.support";

const copy = previewCopy("en");

for (const [language, catalog] of [["en", en], ["es-419", es]] as const) {
  test(`the reused DCA confirmation stays localized and inert in ${language}`, async ({ page, networkAudit }, testInfo) => {
    const localized = previewCopy(language);
    await openPreview(page, { language, audience: "sample", view: "argus", width: 834, height: 1112 });
    await page.getByRole("button", { name: localized.recents, exact: true }).click();
    await page.getByRole("dialog").getByRole("button", { name: localized.recentInvest }).click();
    const card = page.locator("section").filter({ has: page.locator('[data-confirmation-status="editing"]') }).last();
    await expect(card).toContainText(catalog.chat.confirmation.status.editing);
    await expect(card).toContainText(String(DCA_CONFIRMATION.display_facts?.recurring_contribution));
    await expect(card).toContainText(catalog.chat.confirmation.contribution_periods.monthly);
    await expect(card.getByRole("button", { name: catalog.chat.confirmation.actions.run_backtest, exact: true })).toHaveCount(0);
    await expect(page.getByText(localized.artifactNote)).toBeVisible();
    await assertNoHorizontalOverflow(page);
    await capture(page, testInfo, networkAudit, `tablet-${language}-dca-confirmation`);
  });
}

function destination(page: Page, view: View) {
  return page.getByTestId("ecosystem-preview").locator(`a[href*="view=${view}"]`).first();
}

async function closeControls(page: Page) {
  const details = page.getByTestId("preview-controls");
  if (await details.evaluate((element) => (element as HTMLDetailsElement).open)) {
    await details.locator("summary").click();
  }
}

async function openPreferences(page: Page, labels = copy) {
  if (await page.getByRole("dialog", { name: labels.preferences, exact: true }).count() === 0) {
    await page.getByRole("button", { name: new RegExp(`^${labels.preferences}`) }).click();
  }
}

async function closeInspector(page: Page, labels = copy) {
  await page.getByTestId("account-inspector").getByRole("button", { name: labels.closeAccountDetails, exact: true }).click();
  await expect(page.getByTestId("account-inspector")).toHaveCount(0);
}

async function rectangle(locator: Locator) {
  await expect(locator).toBeVisible();
  const box = await locator.boundingBox();
  expect(box).not.toBeNull();
  return box!;
}

async function assertUnobscured(locator: Locator) {
  await expect(locator).toBeVisible();
  expect(await locator.evaluate((element) => {
    const box = element.getBoundingClientRect();
    const hit = document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2);
    return hit !== null && element.contains(hit);
  }), "The control must be reachable in the visible viewport").toBe(true);
}

for (const cell of CELLS) {
  test(`responsive destinations: ${cell.name}`, async ({ page, networkAudit }, testInfo) => {
    await openPreview(page, { ...cell, audience: "sample" });
    for (const view of PREVIEW_VIEWS) {
      await chooseView(page, view);
      await closeControls(page);
      await expect(page.getByTestId("preview-main")).toBeVisible();
      await expect(page.getByRole("navigation").getByRole("link")).toHaveCount(5);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await expect(page.locator("html")).toHaveAttribute("lang", cell.language);
      await expect(page.getByText(previewCopy(cell.language).previewNote, { exact: true })).toBeVisible();
      await assertNoHorizontalOverflow(page);
      await assertLastControlReachable(page);
      if (cell.captures.includes(view)) await capture(page, testInfo, networkAudit, `${cell.name}-${view}`);
    }
  });
}

test("cold guest chat keeps its unsent draft across destination changes", async ({ page, networkAudit }, testInfo) => {
  await openPreview(page);
  await page.goto("/dev/ecosystem", { waitUntil: "networkidle" });
  const composer = page.getByTestId("preview-composer-input");
  await expect(composer).toBeVisible();
  const draft = "@NVDA help me understand this example";
  await composer.pressSequentially(draft);
  await composer.press("Enter");
  await expect(page.getByTestId("preview-notice")).toContainText(copy.sendNotice);
  await expect(composer).toHaveValue(draft);
  await destination(page, "accounts").click();
  await destination(page, "argus").click();
  await expect(composer).toHaveValue(draft);
  await page.getByTestId("preview-send").click();
  await expect(page.getByTestId("preview-notice")).toContainText(copy.sendNotice);
  await expect(composer).toHaveValue(draft);
  await capture(page, testInfo, networkAudit, "guest-unsent-chat-draft");
});

test("destinations participate in browser Back and Forward", async ({ page }) => {
  await openPreview(page, { view: "home" });
  await destination(page, "accounts").click();
  await expect(page).toHaveURL(/view=accounts(?:&|$)/);
  await destination(page, "plan").click();
  await expect(page).toHaveURL(/view=plan(?:&|$)/);
  await page.goBack();
  await expect(page).toHaveURL(/view=accounts(?:&|$)/);
  await page.goBack();
  await expect(page).toHaveURL(/view=home(?:&|$)/);
  await page.goForward();
  await expect(page).toHaveURL(/view=accounts(?:&|$)/);
});

for (const width of [1440, 390]) {
  test(`account dialog traps focus and restores it on Escape and Back at ${width}px`, async ({ page }) => {
    await openPreview(page, { view: "accounts", audience: "sample", width, height: width === 390 ? 844 : 1000 });
    const trigger = page.getByRole("button", { name: copy.addAccount, exact: true }).first();
    await trigger.focus();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("account-create")).toBeVisible();
    await assertDialogFocus(page);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("account-create")).toBeVisible();
    await page.goBack();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(trigger).toBeFocused();
    await expect(page).toHaveURL(/view=accounts(?:&|$)/);
  });
}

test("appearance and language use existing browser persistence", async ({ page, networkAudit }, testInfo) => {
  await openPreview(page, { view: "settings" });
  const appearance = () => page.getByRole("button", { name: new RegExp(`^${copy.appearance}`) });
  for (const mode of ["dark", "light", "system"] as const) {
    await openPreferences(page);
    await appearance().click();
    await page.getByRole("dialog").getByRole("button", { name: en.settings.app.appearance_options[mode], exact: true }).click();
    await expect(page.getByRole("dialog", { name: en.settings.app.appearance, exact: true })).toHaveCount(0);
    await expect(page.getByRole("dialog", { name: copy.preferences, exact: true })).toBeVisible();
    await expect.poll(() => page.evaluate((key) => localStorage.getItem(key), THEME_STORAGE_KEY)).toBe(mode);
    await expect(page.locator("html")).toHaveClass(new RegExp(`\\b${mode === "system" ? "light" : mode}\\b`));
  }
  await page.emulateMedia({ colorScheme: "dark" });
  await expect(page.locator("html")).toHaveClass(/\bdark\b/);
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.locator("html")).toHaveClass(/\bdark\b/);
  await expect.poll(() => page.evaluate((key) => localStorage.getItem(key), THEME_STORAGE_KEY)).toBe("system");
  await openPreferences(page);
  await page.getByRole("button", { name: new RegExp(`^${copy.language}`) }).click();
  await page.getByRole("dialog").getByRole("button", { name: /^Español/ }).click();
  await expect(page.locator("html")).toHaveAttribute("lang", "es-419");
  await expect.poll(() => page.evaluate((key) => localStorage.getItem(key), LANGUAGE_STORAGE_KEY)).toBe("es-419");
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.locator("html")).toHaveAttribute("lang", "es-419");
  await expect(page.locator("html")).toHaveClass(/\bdark\b/);
  await capture(page, testInfo, networkAudit, "settings-spanish-system-dark-persistence");
  await page.emulateMedia({ colorScheme: "light" });
  await expect(page.locator("html")).toHaveClass(/\blight\b/);
});

test("reviewer controls describe fixtures without claiming authentication", async ({ page }) => {
  await openPreview(page, { view: "home" });
  await controls(page);
  const audience = page.getByTestId("preview-audience");
  await expect(audience).toHaveValue("guest");
  await audience.selectOption("sample");
  await expect(audience).toHaveValue("sample");
  await expect(page.getByTestId("preview-controls")).toContainText(copy.controlsNote);
  await audience.selectOption("guest");
  await expect(audience).toHaveValue("guest");
  await expect(page).toHaveURL(/audience=guest(?:&|$)/);
});

for (const cell of [CELLS[0], CELLS[5]]) {
  test(`ecosystem actions explain registration before proceeding: ${cell.name}`, async ({ page, networkAudit }, testInfo) => {
    const labels = previewCopy(cell.language);
    await openPreview(page, { ...cell, view: "home", audience: "guest" });
    const actions = [
      { view: "home" as const, action: labels.record },
      { view: "accounts" as const, action: labels.addAccount },
      { view: "plan" as const, action: labels.newPlan },
      { view: "updates" as const, action: labels.review },
    ];
    for (const [index, action] of actions.entries()) {
      await chooseView(page, action.view);
      await closeControls(page);
      await page.getByRole("button", { name: action.action, exact: true }).last().click();
      const dialog = page.getByRole("dialog", { name: labels.registration, exact: true });
      await expect(dialog).toBeVisible();
      await expect(dialog).toContainText(labels.registrationBody);
      await expect(dialog.getByRole("link", { name: labels.createAccount, exact: true })).toHaveAttribute("href", "/?auth=signup");
      await expect(dialog.getByRole("link", { name: labels.signIn, exact: true })).toHaveAttribute("href", "/?auth=login");
      if (index === 0) await capture(page, testInfo, networkAudit, `${cell.name}-guest-registration-handoff`);
      await page.keyboard.press("Escape");
      await expect(dialog).toHaveCount(0);
      await expect(page).toHaveURL(/\/dev\/ecosystem\?/);
    }
  });
}

for (const handoff of [
  { destination: "signup", label: copy.createAccount },
  { destination: "login", label: copy.signIn },
]) {
  test(`registration handoff keeps the ${handoff.destination} destination and one-step Back`, async ({ page }) => {
    await openPreview(page, { view: "home", audience: "guest" });
    const previewURL = page.url();
    const origin = new URL(previewURL).origin;
    const originalHistoryLength = await page.evaluate(() => history.length);
    // A local inert page proves navigation only. It cannot bootstrap a real
    // auth session or present account creation as a tested capability.
    await page.route((url) => url.origin === origin && url.pathname === "/" && url.searchParams.get("auth") === handoff.destination, (route) => route.fulfill({
      status: 200,
      contentType: "text/html",
      body: "<!doctype html><html lang=\"en\"><head><title>Local navigation fixture</title></head><body><h1>Inert registration destination</h1><p>No authentication is implemented or exercised here.</p></body></html>",
    }));
    await page.getByRole("button", { name: copy.record, exact: true }).first().click();
    await page.getByRole("dialog", { name: copy.registration, exact: true }).getByRole("link", { name: handoff.label, exact: true }).click();
    await page.waitForLoadState("load");
    await expect(page.getByRole("heading", { name: "Inert registration destination", exact: true })).toBeVisible();
    await expect(page).toHaveURL(`${origin}/?auth=${handoff.destination}`);
    expect(await page.evaluate(() => history.length)).toBe(originalHistoryLength + 1);
    await page.goBack({ waitUntil: "networkidle" });
    await expect(page).toHaveURL(previewURL);
    await expect(page.getByTestId("ecosystem-preview")).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });
}

for (const scenario of [
  { state: "empty" as const, query: "", message: "recentsEmpty" as const, name: "empty" },
  { state: "sample" as const, query: "A new money question with no matching sample", message: "recentsNoResults" as const, name: "unmatched" },
]) {
  test(`Recents ${scenario.name} state starts an unsent chat with composer focus`, async ({ page, networkAudit }, testInfo) => {
    await openPreview(page, { view: "argus", state: scenario.state });
    const composer = page.getByTestId("preview-composer-input");
    const originalDraft = "Unsent draft before opening recents";
    await composer.fill(originalDraft);
    await page.getByRole("button", { name: copy.recents, exact: true }).click();
    const dialog = page.getByRole("dialog", { name: copy.recents, exact: true });
    if (scenario.query) await dialog.getByRole("searchbox", { name: copy.searchRecents, exact: true }).fill(scenario.query);
    await expect(dialog).toContainText(copy[scenario.message]);
    await expect(dialog).not.toContainText(copy[scenario.message === "recentsEmpty" ? "recentsNoResults" : "recentsEmpty"]);
    await capture(page, testInfo, networkAudit, `recents-${scenario.name}-state`);
    await dialog.getByRole("button", { name: copy.newChat, exact: true }).click();
    await expect(dialog).toHaveCount(0);
    await expect(composer).toHaveValue(scenario.query || originalDraft);
    await expect(composer).toBeFocused();
    await expect(page.getByText(copy.sendNotice, { exact: true })).toHaveCount(0);
    await expect(page.getByText(copy.sampleConversationBody, { exact: true })).toHaveCount(0);
  });
}

test("sample account creation remains an unsaved draft and leaves sample balances unchanged", async ({ page, networkAudit }, testInfo) => {
  await openPreview(page, { view: "accounts", audience: "sample" });
  const before = await page.getByTestId("preview-main").innerText();
  const storageBefore = await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage } }));
  await page.getByRole("button", { name: copy.addAccount, exact: true }).first().click();
  const create = page.getByTestId("account-create");
  await create.getByRole("button", { name: copy.cash, exact: true }).click();
  await assertFocusInsideDialog(page);
  await expect(create.getByRole("button", { name: copy.cash, exact: true })).toHaveCount(0);
  await expect(create.getByRole("button", { name: copy.change, exact: true })).toBeVisible();
  await create.getByLabel(copy.nickname, { exact: true }).fill("Weekend cash example");
  await create.getByLabel(copy.startingBalance).fill("");
  await expect(create).not.toContainText(copy.institution);
  await create.getByRole("button", { name: copy.reviewDraft, exact: true }).click();
  await assertFocusInsideDialog(page);
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText(copy.draftNotice);
  await expect(dialog).toContainText(copy.unknownBalance);
  await expect(dialog).toContainText("Weekend cash example");
  await capture(page, testInfo, networkAudit, "account-create-unsaved-review");
  // Closing the shared overlay spends its temporary history entry. Reload
  // only after that real traversal, otherwise it can abort the test's reload.
  const closedOverlayHistory = page.evaluate(() => new Promise<void>((resolve) => {
    window.addEventListener("popstate", () => resolve(), { once: true });
  }));
  await page.keyboard.press("Escape");
  await closedOverlayHistory;
  await expect(page.getByTestId("preview-main")).toHaveText(before, { useInnerText: true });
  await page.reload({ waitUntil: "networkidle" });
  await expect(page.getByTestId("preview-main")).toHaveText(before, { useInnerText: true });
  await expect(page.getByText("Weekend cash example", { exact: true })).toHaveCount(0);
  expect(await page.evaluate(() => ({ local: { ...localStorage }, session: { ...sessionStorage } }))).toEqual(storageBefore);
});

for (const language of ["en", "es-419"] as const) {
  for (const mode of ["create", "edit"] as const) {
    test(`account balance syntax blocks invalid text and recovers in ${mode}: ${language}`, async ({ page, networkAudit }, testInfo) => {
      const labels = previewCopy(language);
      await openPreview(page, { view: "accounts", audience: "sample", language });
      const main = page.getByTestId("preview-main");
      const originalAccounts = await main.innerText();
      if (mode === "create") {
        await page.getByRole("button", { name: labels.addAccount, exact: true }).first().click();
        await page.getByTestId("account-create").getByRole("button", { name: labels.cash, exact: true }).click();
      } else {
        await main.getByRole("button", { name: new RegExp(`^${labels.everyday}`) }).click();
        await page.getByRole("button", { name: labels.editDetails, exact: true }).click();
      }
      const form = page.getByTestId(`account-${mode}`);
      const balance = form.getByLabel(labels.startingBalance);
      const nickname = labels.pocket;
      await form.getByLabel(labels.nickname, { exact: true }).fill(nickname);
      for (const invalid of ["abc", "12,34"]) {
        await balance.fill(invalid);
        await form.getByRole("button", { name: labels.reviewDraft, exact: true }).click();
        await expect(form).toBeVisible();
        await expect(page.getByTestId("account-draft")).toHaveCount(0);
        await expect(balance).toHaveValue(invalid);
        await expect(balance).toHaveAttribute("aria-invalid", "true");
        await expect(balance).toBeFocused();
        await expect(form.getByRole("alert")).toHaveText(labels.invalidBalance);
        await expect(balance).toHaveAccessibleDescription(`${labels.leaveBlank} ${labels.invalidBalance}`);
        if (mode === "create" && invalid === "abc") {
          await capture(page, testInfo, networkAudit, `account-balance-invalid-${language}`);
        }
      }
      for (const valid of [SAMPLE.accounts[0].balance, `  ${SAMPLE.accounts[0].balance}  `, "-1250.50", "0", "", "   "]) {
        await balance.fill(valid);
        await expect(form.getByRole("alert")).toHaveCount(0);
        await balance.press("Enter");
        const review = page.getByTestId("account-draft");
        await expect(review).toBeVisible();
        await expect(review).toContainText(labels.draftNotice);
        await expect(review.getByText(nickname, { exact: true })).toBeVisible();
        await expect(review.getByText(valid.trim() || labels.unknownBalance, { exact: true })).toBeVisible();
        await review.getByRole("button", { name: labels.returnDraft, exact: true }).click();
        await expect(balance).toHaveValue(valid.trim());
        await expect(form.getByLabel(labels.nickname, { exact: true })).toHaveValue(nickname);
      }
      await page.keyboard.press("Escape");
      if (mode === "edit") {
        await expect(page.getByTestId("account-inspector")).toContainText(SAMPLE.accounts[0].balance);
        await closeInspector(page, labels);
      }
      await expect(main).toHaveText(originalAccounts, { useInnerText: true });
    });
  }
}

test("reopening an account exposes edit details and a transparent correction review", async ({ page, networkAudit }, testInfo) => {
  await openPreview(page, { view: "accounts", audience: "sample" });
  const main = page.getByTestId("preview-main");
  const original = await main.innerText();
  await main.getByRole("button", { name: new RegExp(`^${copy.everyday}`) }).click();
  await expect(page.getByTestId("account-detail")).toBeVisible();
  await page.getByRole("button", { name: copy.editDetails, exact: true }).click();
  await assertFocusInsideDialog(page);
  const edit = page.getByTestId("account-edit");
  await expect(edit).toBeVisible();
  await expect(edit.getByLabel(copy.institution, { exact: true })).toBeVisible();
  await expect(edit.getByLabel(copy.reference, { exact: true })).toBeVisible();
  await capture(page, testInfo, networkAudit, "account-reopen-edit-details");
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("account-inspector")).toBeVisible();
  await page.getByRole("button", { name: copy.checkBalance, exact: true }).click();
  await assertFocusInsideDialog(page);
  const review = page.getByTestId("correction-review");
  await expect(review).toBeVisible();
  await expect(review).toContainText(copy.previousBalance);
  await expect(review).toContainText(SAMPLE.accounts[0].balance);
  await expect(review).toContainText(SAMPLE.correction.observed);
  await expect(review).toContainText(SAMPLE.correction.difference);
  await expect(review).toContainText(copy.checkedOn);
  await expect(review).toContainText(copy.correctionBasis);
  await expect(review).toContainText(copy.discrepancy);
  const notes = review.getByLabel(copy.notes);
  await expect(notes).toHaveAttribute("maxlength", "200");
  await notes.fill("Sample note. ".repeat(20));
  expect((await notes.inputValue()).length).toBeLessThanOrEqual(200);
  await capture(page, testInfo, networkAudit, "account-correction-review");
  await review.getByRole("button", { name: copy.previewAdjustment, exact: true }).click();
  await assertFocusInsideDialog(page);
  await expect(page.getByRole("dialog")).toContainText(copy.adjustmentNotice);
  await page.keyboard.press("Escape");
  await expect(page.getByTestId("account-inspector")).toContainText(SAMPLE.accounts[0].balance);
  await closeInspector(page);
  await expect(main).toHaveText(original, { useInnerText: true });
});

test("recents and search preserve context without running a conversation", async ({ page, networkAudit }, testInfo) => {
  await openPreview(page, { view: "argus", audience: "sample" });
  await page.getByRole("button", { name: copy.recents, exact: true }).click();
  const recent = copy[RECENTS[2]];
  await page.getByRole("dialog").getByRole("button", { name: new RegExp(recent) }).click();
  await expect(page.getByRole("heading", { name: recent, level: 1, exact: true })).toBeVisible();
  await expect(page.getByText(copy.artifactNote, { exact: true })).toBeVisible();
  await capture(page, testInfo, networkAudit, "argus-dca-confirmation-read-only");
  await destination(page, "accounts").click();
  await destination(page, "argus").click();
  await expect(page.getByRole("heading", { name: recent, level: 1, exact: true })).toBeVisible();
  await destination(page, "search").click();
  const search = page.getByRole("searchbox", { name: copy.searchLabel, exact: true });
  await search.fill("no matching sample record 4926");
  await expect(page.getByTestId("preview-main")).toContainText(copy.noResults);
  await search.fill(copy.everyday);
  await expect(page.getByTestId("preview-main").getByRole("button", { name: new RegExp(`^${copy.everyday}`) })).toBeVisible();
  await capture(page, testInfo, networkAudit, "search-local-account-results");
  await destination(page, "home").click();
  await destination(page, "search").click();
  await expect(search).toHaveValue(copy.everyday);
  await page.getByTestId("preview-main").getByRole("button", { name: new RegExp(`^${copy.everyday}`) }).click();
  await expect(page.getByTestId("account-detail")).toBeVisible();
  await expect(page.getByTestId("account-inspector")).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("account activity uses its canonical entries and replaces stale search filters", async ({ page, networkAudit }, testInfo) => {
  await openPreview(page, { view: "search", audience: "sample" });
  const search = page.getByRole("searchbox", { name: copy.searchLabel, exact: true });
  await search.fill(copy.goalTitle);
  await page.getByRole("group", { name: copy.searchCategories }).getByRole("button", { name: copy.plans, exact: true }).click();
  await expect(page.getByTestId("preview-main")).toContainText(copy.goalTitle);

  await destination(page, "accounts").click();
  await page.getByTestId("preview-main").getByRole("button", { name: new RegExp(`^${copy.pocket}`) }).click();
  const detail = page.getByTestId("account-detail");
  await expect(detail).toContainText(copy.cashTransfer);
  await expect(detail).not.toContainText(copy.noActivity);
  await detail.getByRole("button", { name: copy.viewAll, exact: true }).click();

  await expect(page).toHaveURL(/view=search(?:&|$)/);
  await expect(search).toHaveValue("");
  await expect(page.getByRole("group", { name: copy.searchCategories }).getByRole("button", { name: copy.activity, exact: true })).toHaveAttribute("aria-pressed", "true");
  await expect(page.getByTestId("preview-main")).toContainText(copy.cashTransfer);
  await expect(page.getByTestId("preview-main")).not.toContainText(copy.goalTitle);
  await capture(page, testInfo, networkAudit, "account-activity-filter-recovery");
});

test("empty, loading and error layouts recover only to local sample content", async ({ page, networkAudit }, testInfo) => {
  await openPreview(page, { view: "home", audience: "sample", state: "empty" });
  await expect(page.getByTestId("preview-main")).toContainText(copy.homeEmpty);
  await capture(page, testInfo, networkAudit, "home-empty-state");
  await controls(page);
  await page.getByTestId("preview-state").selectOption("loading");
  await closeControls(page);
  await expect(page.getByTestId("preview-main")).toContainText(copy.loadingBody);
  await capture(page, testInfo, networkAudit, "home-loading-state");
  await controls(page);
  await page.getByTestId("preview-state").selectOption("error");
  await closeControls(page);
  await expect(page.getByTestId("preview-main")).toContainText(copy.errorBody);
  await capture(page, testInfo, networkAudit, "home-error-state");
  await page.getByRole("button", { name: copy.retry, exact: true }).click();
  await expect(page.getByTestId("preview-state")).toHaveValue("sample");
  await expect(page.getByTestId("preview-main")).toContainText(copy.recordedPosition);
});

test("unknown query values cannot claim a signed-in or saved preview", async ({ page }) => {
  await openPreview(page);
  await page.goto("/dev/ecosystem?view=unknown&state=saved&audience=registered&authenticated=true&account=private-account");
  await controls(page);
  await expect(page.getByTestId("preview-view")).toHaveValue("argus");
  await expect(page.getByTestId("preview-state")).toHaveValue("sample");
  await expect(page.getByTestId("preview-audience")).toHaveValue("guest");
  await expect(page.getByTestId("account-inspector")).toHaveCount(0);
  await expect(page.getByTestId("account-detail")).toHaveCount(0);
  await expect(page.getByText(copy.previewNote, { exact: true })).toBeVisible();
});

for (const scenario of [
  { audience: "guest", state: "sample" },
  { audience: "sample", state: "empty" },
  { audience: "sample", state: "error" },
] as const) {
  test(`an account deep link respects the ${scenario.audience}/${scenario.state} presentation`, async ({ page }) => {
    await openPreview(page, { view: "accounts", ...scenario });
    const query = new URLSearchParams({ view: "accounts", ...scenario, account: SAMPLE.accounts[0].id });
    await page.goto(`/dev/ecosystem?${query}`, { waitUntil: "networkidle" });
    await expect(page.getByTestId("account-inspector")).toHaveCount(0);
    await expect(page.getByTestId("account-detail")).toHaveCount(0);
    await expect(page.getByRole("dialog")).toHaveCount(0);
    if (scenario.audience === "guest") {
      await page.getByRole("button", { name: copy.addAccount, exact: true }).first().click();
      await expect(page.getByRole("dialog", { name: copy.registration, exact: true })).toContainText(copy.registrationBody);
    } else {
      await expect(page.getByTestId("preview-main")).toContainText(scenario.state === "empty" ? copy.accountsEmpty : copy.errorBody);
    }
  });
}

for (const cell of [CELLS[0], CELLS[6]]) {
  test(`200% text and a long account label remain usable: ${cell.name}`, async ({ page, networkAudit }, testInfo) => {
    const labels = previewCopy(cell.language);
    await openPreview(page, { ...cell, view: "home", audience: "sample" });
    for (const view of ["home", "accounts", "argus", "settings"] as const) {
      await chooseView(page, view);
      await closeControls(page);
      await enlargeText(page);
      await assertNoHorizontalOverflow(page);
      await assertLastControlReachable(page);
      for (const link of await page.getByRole("navigation").getByRole("link").all()) {
        const bounds = await rectangle(link);
        expect(bounds.width).toBeGreaterThanOrEqual(44);
        expect(bounds.height).toBeGreaterThanOrEqual(44);
      }
    }
    await chooseView(page, "accounts");
    await closeControls(page);
    await page.getByRole("button", { name: labels.addAccount, exact: true }).first().click();
    const create = page.getByTestId("account-create");
    await create.getByRole("button", { name: labels.checking, exact: true }).click();
    await assertFocusInsideDialog(page);
    const longLabel = `${labels.everyday} · ${labels.unknownAccount} · ${labels.safety}`;
    await create.getByLabel(labels.nickname, { exact: true }).fill(longLabel);
    await enlargeText(page);
    await create.getByRole("button", { name: labels.reviewDraft, exact: true }).click();
    await assertFocusInsideDialog(page);
    await enlargeText(page);
    const dialog = page.getByRole("dialog");
    const visibleName = dialog.getByRole("heading", { name: longLabel, exact: true });
    await expect(visibleName).toBeVisible();
    expect(await visibleName.evaluate((element) => element.scrollHeight <= element.clientHeight + 1 && element.scrollWidth <= element.clientWidth + 1), "The long draft name must wrap without clipping").toBe(true);
    await expect(dialog).toContainText(labels.draftNotice);
    const dimensions = await dialog.evaluate((element) => ({ scroll: element.scrollWidth, client: element.clientWidth }));
    expect(dimensions.scroll).toBeLessThanOrEqual(dimensions.client + 1);
    await capture(page, testInfo, networkAudit, `${cell.name}-enlarged-text-long-label`);
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
  });
}

for (const cell of [CELLS[0], CELLS[3]]) {
  test(`web rail keeps local geometry through preferences and history: ${cell.name}`, async ({ page, networkAudit }, testInfo) => {
    const labels = previewCopy(cell.language);
    await openPreview(page, { ...cell, view: "home" });
    const rail = page.getByTestId("preview-rail");
    const initiallyExpanded = cell.width >= DESKTOP_MIN_WIDTH_PX;
    const storageBefore = await page.evaluate(() => ({ ...localStorage }));
    await expect(rail).toHaveAttribute("data-expanded", String(initiallyExpanded));
    expect((await rectangle(rail)).width).toBeCloseTo(initiallyExpanded ? 288 : 56, 0);
    const toggle = rail.getByRole("button", { name: initiallyExpanded ? labels.collapseNavigation : labels.expandNavigation, exact: true });
    await toggle.focus();
    await page.keyboard.press("Enter");
    await expect(rail).toHaveAttribute("data-expanded", String(!initiallyExpanded));
    expect((await rectangle(rail)).width).toBeCloseTo(initiallyExpanded ? 56 : 288, 0);
    for (const view of PREVIEW_VIEWS.slice(0, 5)) {
      const link = rail.getByRole("link", { name: labels[view], exact: true });
      const bounds = await rectangle(link);
      expect(bounds.width).toBeGreaterThanOrEqual(44);
      expect(bounds.height).toBeGreaterThanOrEqual(44);
      await assertUnobscured(link);
    }
    await destination(page, "accounts").click();
    await page.goBack();
    await expect(destination(page, "home")).toHaveAttribute("aria-current", "page");
    await expect(rail).toHaveAttribute("data-expanded", String(!initiallyExpanded));
    expect(await page.evaluate(() => ({ ...localStorage }))).toEqual(storageBefore);

    await destination(page, "settings").click();
    await openPreferences(page, labels);
    await page.getByRole("button", { name: new RegExp(`^${labels.language}`) }).click();
    const nextLanguage = cell.language === "en" ? "es-419" : "en";
    await page.getByRole("dialog").getByRole("button", { name: nextLanguage === "en" ? /^English/ : /^Español/ }).click();
    await expect(page.locator("html")).toHaveAttribute("lang", nextLanguage);
    const nextCopy = previewCopy(nextLanguage);
    const nextCatalog = nextLanguage === "en" ? en : es;
    await page.getByRole("button", { name: new RegExp(`^${nextCopy.appearance}`) }).click();
    await page.getByRole("dialog").getByRole("button", { name: nextCatalog.settings.app.appearance_options.dark, exact: true }).click();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(page.locator("html")).toHaveClass(/\bdark\b/);
    await expect(rail).toHaveAttribute("data-expanded", String(!initiallyExpanded));
    await expect(rail.getByRole("link", { name: nextCopy.accounts, exact: true })).toBeVisible();
    expect(await page.evaluate(() => localStorage.getItem("argus:sidebar_mode"))).toBeNull();
    await assertNoHorizontalOverflow(page);
    await capture(page, testInfo, networkAudit, `${cell.name}-rail-preferences-local-state`);
  });
}

for (const cell of [CELLS[0], CELLS[2], CELLS[4]]) {
  test(`cold chat groups its composer and active chat scrolls independently: ${cell.name}`, async ({ page, networkAudit }, testInfo) => {
    await openPreview(page, { ...cell, view: "argus", audience: "sample" });
    const composer = page.getByTestId("preview-composer");
    const input = page.getByTestId("preview-composer-input");
    const recents = page.getByRole("button", { name: copy.recents, exact: true });
    const main = page.getByTestId("preview-main");
    const cold = await rectangle(composer);
    const reading = await rectangle(main);
    const chips = await rectangle(page.getByRole("group", { name: copy.suggestions, exact: true }));
    expect(Math.abs(cold.x + cold.width / 2 - reading.x - reading.width / 2)).toBeLessThanOrEqual(2);
    expect(cold.width).toBeLessThanOrEqual(672);
    expect(cold.y - chips.y - chips.height, "The cold composer stays with the suggestions").toBeGreaterThanOrEqual(0);
    expect(cold.y - chips.y - chips.height).toBeLessThanOrEqual(40);
    await assertUnobscured(input);
    const headerBefore = await rectangle(recents);
    const draft = "@NVDA this stays an unsent preview draft";
    await input.fill(draft);
    await recents.click();
    await page.getByRole("dialog").getByRole("button", { name: copy.recentInvest, exact: true }).click();
    const transcript = page.getByTestId("preview-transcript");
    await expect(transcript).toBeVisible();
    await expect(input).toHaveValue(draft);
    const active = await rectangle(composer);
    const transcriptBounds = await rectangle(transcript);
    expect(active.width).toBeLessThanOrEqual(768);
    expect(transcriptBounds.y + transcriptBounds.height).toBeLessThanOrEqual(active.y + 1);
    if (cell.width >= TABLET_MIN_WIDTH_PX) expect(active.y - cold.y, "Active chat docks its composer below the central cold layout").toBeGreaterThan(60);
    expect((await rectangle(recents)).x).toBeCloseTo(headerBefore.x, 0);
    expect((await rectangle(recents)).y).toBeCloseTo(headerBefore.y, 0);
    await capture(page, testInfo, networkAudit, `${cell.name}-active-chat-docked`);

    // The real fixed DCA sample at 200% text supplies overflow without adding
    // invented messages or changing the product's fixture data.
    await enlargeText(page);
    await expect.poll(() => transcript.evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(true);
    const dockBefore = await rectangle(composer);
    const headerAtLargeText = await rectangle(recents);
    const documentScrollBefore = await page.evaluate(() => window.scrollY);
    await transcript.hover();
    await page.mouse.wheel(0, 1800);
    await expect.poll(() => transcript.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
    const dockAfter = await rectangle(composer);
    expect(dockAfter.y).toBeCloseTo(dockBefore.y, 0);
    expect(dockAfter.height).toBeCloseTo(dockBefore.height, 0);
    expect((await rectangle(recents)).y).toBeCloseTo(headerAtLargeText.y, 0);
    expect(await page.evaluate(() => window.scrollY)).toBe(documentScrollBefore);
    await assertUnobscured(input);
    await assertNoHorizontalOverflow(page);
    await expect(input).toHaveValue(draft);
    await capture(page, testInfo, networkAudit, `${cell.name}-active-chat-text-200-scroll`);
  });
}

test("desktop account inspection retains the list, keyboard access and route history", async ({ page, networkAudit }, testInfo) => {
  for (const view of ["accounts", "search"] as const) {
    await openPreview(page, { view, audience: "sample", width: 1440, height: 1000 });
    const main = page.getByTestId("preview-main");
    const inspector = page.getByTestId("account-inspector");
    const [first, second] = SAMPLE.accounts;
    const row = (account: SampleAccount) => main.getByRole("button", { name: new RegExp(`^${copy[account.name]}`) });
    const selected = () => new URL(page.url()).searchParams.get("account");
    await row(first).focus();
    await page.keyboard.press("Enter");
    await expect(inspector).toBeVisible();
    await expect(page.getByRole("dialog")).toHaveCount(0);
    expect(selected()).toBe(first.id);
    await expect(inspector).toContainText(first.balance!);
    await expect.poll(() => inspector.evaluate((element) => element.contains(document.activeElement))).toBe(true);
    const listRow = await rectangle(row(first));
    const detail = await rectangle(inspector);
    expect(listRow.x + listRow.width, "The list remains beside the detail pane").toBeLessThanOrEqual(detail.x + 1);
    await assertUnobscured(row(second));
    await inspector.getByRole("button", { name: copy.closeAccountDetails, exact: true }).focus();
    await page.keyboard.press("Shift+Tab");
    expect(await inspector.evaluate((element) => element.contains(document.activeElement)), "The ordinary inspector does not trap keyboard focus").toBe(false);

    await row(second).click();
    await expect(inspector).toContainText(second.balance!);
    expect(selected()).toBe(second.id);
    await page.goBack();
    await expect(inspector).toContainText(first.balance!);
    expect(selected()).toBe(first.id);
    await page.goBack();
    await expect(inspector).toHaveCount(0);
    await expect(row(first)).toBeFocused();
    expect(selected()).toBeNull();
    await page.goForward();
    await expect(inspector).toBeVisible();
    expect(selected()).toBe(first.id);
    await capture(page, testInfo, networkAudit, `${view}-desktop-account-inspector`);
    await closeInspector(page);
    await expect(row(first)).toBeFocused();
    expect(selected()).toBeNull();
    await page.goBack();
    await expect(inspector).toBeVisible();
    expect(selected()).toBe(first.id);
    await page.goForward();
    await expect(inspector).toHaveCount(0);
    expect(selected()).toBeNull();

    await page.setViewportSize({ width: DESKTOP_MIN_WIDTH_PX, height: 580 });
    const lowerAccount = SAMPLE.accounts.at(-1)!;
    await row(lowerAccount).scrollIntoViewIfNeeded();
    await expect.poll(() => main.evaluate((element) => element.scrollTop)).toBeGreaterThan(0);
    await row(lowerAccount).click();
    const heading = inspector.getByRole("heading", { name: copy[lowerAccount.name], level: 2, exact: true });
    await expect(heading).toBeFocused();
    const mainViewport = await rectangle(main);
    const headingBounds = await rectangle(heading);
    expect(headingBounds.y, "Opening a lower account reveals its focused detail heading").toBeGreaterThanOrEqual(mainViewport.y);
    expect(headingBounds.y + headingBounds.height).toBeLessThanOrEqual(mainViewport.y + mainViewport.height);
    await assertUnobscured(heading);
    await closeInspector(page);
    await expect(row(lowerAccount)).toBeFocused();
    const restoredRow = await rectangle(row(lowerAccount));
    expect(restoredRow.y, "Closing account detail reveals the row receiving focus").toBeGreaterThanOrEqual(mainViewport.y);
    expect(restoredRow.y + restoredRow.height).toBeLessThanOrEqual(mainViewport.y + mainViewport.height);
    await assertUnobscured(row(lowerAccount));
  }
});

for (const entry of [
  { view: "accounts", kind: "navigation" },
  { view: "search", kind: "navigation" },
  { view: "accounts", kind: "direct-link" },
] as const) test(`account inspection stays in its URL across the desktop boundary without duplicate history: ${entry.view}/${entry.kind}`, async ({ page, networkAudit }, testInfo) => {
  await openPreview(page, { view: "home", audience: "sample", width: DESKTOP_MIN_WIDTH_PX, height: 1000 });
  const homeURL = page.url();
  const account = SAMPLE.accounts[0];
  const inspector = page.getByTestId("account-inspector");
  const trigger = page.getByTestId("preview-main").getByRole("button", { name: new RegExp(`^${copy[account.name]}`) });
  let listURL: string | undefined;
  if (entry.kind === "navigation") {
    await destination(page, entry.view).click();
    await expect(page).toHaveURL(new RegExp(`view=${entry.view}(?:&|$)`));
    listURL = page.url();
    await trigger.click();
  } else {
    const query = new URLSearchParams({ view: entry.view, audience: "sample", state: "sample", account: account.id });
    await page.goto(`/dev/ecosystem?${query}`, { waitUntil: "networkidle" });
  }
  await expect(inspector).toBeVisible();
  const selectedURL = page.url();
  const selectedHistoryLength = await page.evaluate(() => history.length);
  expect(new URL(selectedURL).searchParams.get("account")).toBe(account.id);
  await expect.poll(() => inspector.evaluate((element) => element.contains(document.activeElement))).toBe(true);
  await page.setViewportSize({ width: DESKTOP_MIN_WIDTH_PX - 1, height: 1000 });
  await expect(page).toHaveURL(selectedURL);
  expect(await page.evaluate(() => history.length)).toBe(selectedHistoryLength);
  await expect(inspector).toContainText(account.balance!);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect.poll(() => inspector.evaluate((element) => element.contains(document.activeElement))).toBe(true);
  const stackedDetail = await rectangle(inspector);
  expect(stackedDetail.y + stackedDetail.height, "Selected detail stacks above the account list below desktop").toBeLessThanOrEqual((await rectangle(trigger)).y);
  await page.setViewportSize({ width: 834, height: 1112 });
  await assertNoHorizontalOverflow(page);
  if (entry.view === "accounts" && entry.kind === "navigation") {
    await capture(page, testInfo, networkAudit, "tablet-account-inspector-stacked-after-resize");
  }

  // A resize adds no history step: selection returns to its original list,
  // while a direct selected URL returns straight to the preceding Home page.
  if (listURL) {
    await page.goBack();
    await expect(page).toHaveURL(listURL);
    await expect(inspector).toHaveCount(0);
    await expect(page.getByRole("dialog")).toHaveCount(0);
    await expect(trigger).toBeFocused();
  }
  await page.goBack();
  await expect(page).toHaveURL(homeURL);
  await expect(page.getByTestId("ecosystem-preview")).toHaveAttribute("data-preview-view", "home");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await page.goForward();
  if (listURL) {
    await expect(page).toHaveURL(listURL);
    await expect(inspector).toHaveCount(0);
    await page.goForward();
  }
  await expect(page).toHaveURL(selectedURL);
  await expect(inspector).toContainText(account.balance!);
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect.poll(() => inspector.evaluate((element) => element.contains(document.activeElement))).toBe(true);
  await closeInspector(page);
  await expect(trigger).toBeFocused();
  expect(new URL(page.url()).searchParams.has("account")).toBe(false);
  const closedURL = page.url();
  await trigger.click();
  await assertDialogFocus(page);
  await expect(page.getByRole("dialog")).toContainText(account.balance!);
  await expect(inspector).toHaveCount(0);
  await expect(page).toHaveURL(closedURL);
  if (entry.view === "accounts" && entry.kind === "navigation") {
    await capture(page, testInfo, networkAudit, "tablet-account-detail-after-resize");
  }
  await page.goBack();
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(trigger).toBeFocused();
  await expect(page).toHaveURL(closedURL);
  await page.setViewportSize({ width: DESKTOP_MIN_WIDTH_PX, height: 1000 });
  await expect(inspector).toHaveCount(0);
  await trigger.press("Enter");
  await expect(inspector).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("Home keeps two upcoming commitments ahead of account browsing on narrow screens", async ({ page, networkAudit }, testInfo) => {
  await openPreview(page, { view: "home", audience: "sample", width: 1440, height: 1000 });
  const comingUp = page.getByTestId("home-coming-up");
  await expect(comingUp).toContainText(copy.comingUpNote);
  for (const commitment of SAMPLE.commitments.slice(0, 2)) await expect(comingUp).toContainText(copy[commitment.title]);
  for (const commitment of SAMPLE.commitments.slice(2)) await expect(comingUp.getByRole("button", { name: new RegExp(copy[commitment.title]) })).toHaveCount(0);
  await page.setViewportSize({ width: 390, height: 844 });
  const upcomingBounds = await rectangle(comingUp);
  const firstAccount = await rectangle(page.getByTestId("preview-main").getByRole("button", { name: new RegExp(`^${copy.everyday}`) }));
  expect(upcomingBounds.y + upcomingBounds.height).toBeLessThanOrEqual(firstAccount.y);
  await comingUp.getByRole("button", { name: copy.plan, exact: true }).click();
  await expect(page).toHaveURL(/view=plan(?:&|$)/);
  await page.goBack();
  await expect(comingUp).toBeVisible();
  await capture(page, testInfo, networkAudit, "narrow-home-upcoming-priority");
});
