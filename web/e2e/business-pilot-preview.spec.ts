import { expect, test, type Page } from "@playwright/test";
import { installBreakpointFixture } from "./support/breakpoint-fixture";

const PREVIEW = "/dev/business-preview";

async function openPreview(
  page: Page,
  url = PREVIEW,
  options: { sidebarMode?: "expanded" | "collapsed"; emptyChat?: boolean } = {},
) {
  await page.route("**/*", (route) => {
    const { hostname } = new URL(route.request().url());
    return ["127.0.0.1", "localhost"].includes(hostname)
      ? route.continue()
      : route.abort("blockedbyclient");
  });
  await installBreakpointFixture(page, {
    language: "en",
    theme: "light",
    emptyChat: options.emptyChat ?? true,
  });
  if (options.sidebarMode) {
    await page.addInitScript((mode) => {
      window.localStorage.setItem("argus:sidebar_mode", mode);
    }, options.sidebarMode);
  }
  await page.goto(url);
}

const nav = (page: Page) => page.getByTestId("business-sidebar-nav");
const panelHeading = (page: Page, name: string) =>
  page.getByTestId("workspace-panel-region").getByRole("heading", { name, exact: true });

test.describe("Business preview", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("an Overview draft survives a visit to the Inbox", async ({ page }) => {
    await openPreview(page);
    await expect(panelHeading(page, "Your business")).toBeVisible();

    const composer = page.getByTestId("chat-input");
    await composer.click();
    await page.keyboard.type("How much did I spend on paint?");

    await nav(page).getByRole("button", { name: /^Inbox/ }).click();
    await expect(panelHeading(page, "Inbox")).toBeVisible();
    await expect(page.getByTestId("chat-input")).toHaveCount(0);

    await nav(page).getByRole("button", { name: /^Overview/ }).click();
    await expect(panelHeading(page, "Your business")).toBeVisible();
    await expect(page.getByTestId("chat-input")).toHaveText("How much did I spend on paint?");
  });

  test("the Create menu opens from the collapsed rail inside the viewport", async ({ page }) => {
    await openPreview(page, PREVIEW, { sidebarMode: "collapsed" });
    await expect(panelHeading(page, "Your business")).toBeVisible();

    const trigger = page.getByTestId("business-create");
    await expect(trigger).toHaveAccessibleName("Create");
    await trigger.focus();
    await page.keyboard.press("Enter");

    const menu = page.getByRole("menu", { name: "Create" });
    await expect(menu).toBeVisible();
    const box = await menu.boundingBox();
    const viewport = page.viewportSize();
    expect(box && viewport).toBeTruthy();
    expect(box!.x).toBeGreaterThanOrEqual(0);
    expect(box!.y).toBeGreaterThanOrEqual(0);
    expect(box!.x + box!.width).toBeLessThanOrEqual(viewport!.width);
    expect(box!.y + box!.height).toBeLessThanOrEqual(viewport!.height);

    const items = menu.getByRole("menuitem");
    await expect(items).toHaveText(["Upload receipt", "Record expense"]);
    await expect(items.nth(0)).toBeFocused();
    await page.keyboard.press("ArrowDown");
    await expect(items.nth(1)).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(menu).toHaveCount(0);
    await expect(trigger).toBeFocused();

    await page.keyboard.press("Enter");
    await expect(items.nth(0)).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(menu).toHaveCount(0);
    await expect(trigger).toBeFocused();
  });

  test("New chat has one entry point and Create sits on the nav row grid", async ({ page }) => {
    await openPreview(page, PREVIEW);
    await expect(page.getByRole("button", { name: /^New chat/ })).toHaveCount(1);

    const create = page.getByTestId("business-create");
    const overview = page.getByRole("button", { name: /^Overview/ }).first();
    const [createBox, overviewBox] = await Promise.all([create.boundingBox(), overview.boundingBox()]);
    expect(createBox!.height).toBe(overviewBox!.height);
    const [createIcon, overviewIcon] = await Promise.all([
      create.locator("svg").boundingBox(),
      overview.locator("svg").first().boundingBox(),
    ]);
    expect(createIcon!.width).toBe(overviewIcon!.width);
  });

  test("New chat from the Inbox shows the chat surface", async ({ page }) => {
    await openPreview(page, `${PREVIEW}?view=inbox`);
    await expect(panelHeading(page, "Inbox")).toBeVisible();

    await page.getByRole("button", { name: /^New chat/ }).first().click();

    await expect(page.locator('[data-business-home="new_chat"]')).toBeVisible();
    await expect(page.getByTestId("workspace-panel-region")).toHaveCount(0);
    await expect(page).toHaveURL(/view=chat/);
  });

  test("leaving a conversation for a panel keeps the panel in the address bar", async ({ page }) => {
    await openPreview(page, `${PREVIEW}?conversation=conversation-alpha`, { emptyChat: false });
    await expect(page.getByTestId("workspace-panel-region")).toHaveCount(0);
    await expect(page.getByTestId("chat-input")).toBeVisible();

    await nav(page).getByRole("button", { name: /^Inbox/ }).click();
    await expect(panelHeading(page, "Inbox")).toBeVisible();
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveURL(/\/dev\/business-preview\?view=inbox$/);

    await page.reload();
    await expect(panelHeading(page, "Inbox")).toBeVisible();
  });

  test("the review screen marks missing_fields Needed and confirms into Expenses", async ({ page }) => {
    await openPreview(page, `${PREVIEW}?receipt=rcpt-ferreteria`);
    await expect(panelHeading(page, "Review receipt")).toBeVisible();

    const needed = page.getByText("Needed", { exact: true });
    await expect(needed).toHaveCount(1);
    const paidFrom = page.locator("label", { hasText: "Paid from" });
    await expect(paidFrom.getByText("Needed", { exact: true })).toBeVisible();
    const confirm = page.getByRole("button", { name: "Confirm expense" });
    await expect(confirm).toBeDisabled();

    await paidFrom.locator("select").selectOption("acct-ops");
    await expect(needed).toHaveCount(0);
    await confirm.click();

    await expect(panelHeading(page, "Saved expense")).toBeVisible();
    await page.getByRole("button", { name: "View expenses" }).click();
    await expect(panelHeading(page, "Expenses")).toBeVisible();
    await expect(page.getByTestId("workspace-panel-region")).toContainText("Ferretería La Esquina");
  });

  test("a reload of view=chat stays on the chat surface", async ({ page }) => {
    await openPreview(page, `${PREVIEW}?view=chat`);
    const home = page.locator('[data-business-home="new_chat"]');
    await expect(home).toBeVisible();

    await page.reload();
    await expect(home).toBeVisible();
    await expect(page.getByTestId("workspace-panel-region")).toHaveCount(0);
    await expect(page).toHaveURL(/view=chat/);
  });
});

test.describe("Business preview on a phone", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("the drawer shows the Business destinations with labels and Create", async ({ page }) => {
    await openPreview(page);
    await expect(panelHeading(page, "Your business")).toBeVisible();

    await page.getByTestId("chat-shell-menu-trigger").click();

    const drawerNav = nav(page);
    for (const label of ["Overview", "Inbox", "Expenses", "Updates"]) {
      await expect(drawerNav.getByText(label, { exact: true })).toBeVisible();
    }
    await expect(drawerNav.getByRole("button", { name: /^Inbox/ })).toContainText("4");
    await expect(page.getByTestId("business-create")).toHaveText("Create");
  });
});

test.describe("Argus chat without a workspace", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("keeps the mention button and the legacy starter pills", async ({ page }) => {
    await page.route("**/*", (route) => {
      const { hostname } = new URL(route.request().url());
      return ["127.0.0.1", "localhost"].includes(hostname)
        ? route.continue()
        : route.abort("blockedbyclient");
    });
    await installBreakpointFixture(page, { language: "en", theme: "light", emptyChat: true });
    await page.goto("/chat");

    await expect(page.getByTestId("chat-input")).toBeVisible();
    await expect(page.getByRole("button", { name: "Mention an asset or indicator" })).toBeVisible();
    for (const pill of ["Test Apple vs SPY", "Test Bitcoin (BTC) hold", "Test weekly Nvidia buys"]) {
      await expect(page.getByRole("button", { name: pill })).toBeVisible();
    }
    await expect(page.getByTestId("business-sidebar-nav")).toHaveCount(0);
  });
});
