import { type Page } from "@playwright/test";
import { join } from "node:path";
import { test, expect, login, navigate, evidenceDirectory } from "./fixtures";

async function publish(page: Page, scenario: string): Promise<void> {
  await page.getByTestId("demo-scenario").selectOption(scenario);
  const responsePromise = page.waitForResponse((response) =>
    response.url().endsWith("/api/demo/events") && response.request().method() === "POST");
  await page.getByTestId("publish-demo-event").click();
  const response = await responsePromise;
  expect(response.status()).toBe(202);
  const { load_id } = await response.json();
  await expect.poll(async () => {
    const home = await (await page.request.get("/api/home")).json();
    return home.source_status.load_id === load_id ? home.source_status.state : "waiting";
  }).toBe(scenario === "failure" ? "stale" : "ready");
}

for (const example of [
  { language: "es", width: 1440, height: 1050 },
  { language: "en", width: 1440, height: 1050 },
  { language: "es", width: 390, height: 844 },
] as const) {
  test(`${example.language} ${example.width}: confirm, save, unchanged check, changed notice and receipts`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.setViewportSize({ width: example.width, height: example.height });
    await login(page, example.language);
    await navigate(page, "deposits");
    await expect(page.getByTestId("comparison").filter({ visible: true })).toHaveCount(0);
    await page.getByRole("button", { name: /^(Review amount and horizon|Revisar monto y plazo)$/ }).click();
    await expect(page.getByTestId("confirmation").filter({ visible: true })).toBeVisible();
    await expect(page.getByTestId("comparison").filter({ visible: true })).toHaveCount(0);
    await page.getByTestId("confirm-comparison").filter({ visible: true }).first().click();
    await expect(page.getByTestId("comparison").filter({ visible: true }).first()).toBeVisible();
    await page.screenshot({ path: join(evidenceDirectory, `${example.language}-${example.width}-comparison.png`), fullPage: true, animations: "disabled" });
    await page.getByTestId("source-link").first().click();
    await expect(page.getByTestId("receipt-dialog")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByTestId("receipt-dialog")).toHaveCount(0);
    await page.getByRole("button", { name: /^(Save comparison|Guardar comparación)$/ }).first().click();
    await expect.poll(async () => (await (await page.request.get("/api/home")).json()).saved.length).toBe(1);
    await publish(page, "same_winner");
    await expect(page.getByTestId("notice")).toHaveCount(0);
    await publish(page, "leader_changed");
    await expect(page.getByTestId("notice").first()).toBeVisible();
    await page.getByRole("button", { name: /^(Notices|Avisos)/ }).click();
    await page.getByRole("dialog").getByRole("button", { name: /A deposit comparison has a new leader|Una comparación de depósitos tiene un nuevo líder/ }).click();
    await expect(page.getByTestId("saved-detail")).toBeVisible();
    await page.screenshot({ path: join(evidenceDirectory, `${example.language}-${example.width}-before-after.png`), fullPage: true, animations: "disabled" });
    await page.reload();
    await expect.poll(async () => (await (await page.request.get("/api/home")).json()).saved.length).toBe(1);
    await publish(page, "failure");
    const home = await (await page.request.get("/api/home")).json();
    expect(home.source_status.dataset_id).toBeTruthy();
    expect(home.source_status.error_code).toBeTruthy();
    const hasOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1);
    expect(hasOverflow).toBe(false);
    const visibleCopy = await page.locator("body").innerText();
    expect(visibleCopy).not.toMatch(/asesor de inversión|investment adviser|investment advisor|—/i);
    expect(visibleCopy).toContain(example.language === "es" ? "sucursal" : "branch");
    expect(errors).toEqual([]);
  });
}

test("edited replay stays honest and the second country uses the same flow", async ({ page }) => {
  const externalRequests: string[] = [];
  page.on("request", request => {
    const host = new URL(request.url()).hostname;
    if (host !== "127.0.0.1" && host !== "localhost") externalRequests.push(request.url());
  });
  await login(page);
  await navigate(page, "deposits");
  await page.getByText("You can also describe it in words", { exact: true }).click();
  await page.getByTestId("demo-example").first().click();
  await page.getByTestId("chat-input").fill("Compare my edited amount for a different term.");
  await page.getByTestId("send-message").click();
  await expect(page.getByRole("alert").first()).toContainText("This text needs a connected model.");
  await expect(page.getByTestId("confirmation").filter({ visible: true })).toHaveCount(0);
  await expect(page.getByTestId("comparison").filter({ visible: true })).toHaveCount(0);

  await page.getByRole("button", { name: "I want to compare NZD 12,000 for 365 days. Use example" }).click();
  await page.getByTestId("send-message").click();
  const confirmation = page.getByTestId("confirmation").filter({ visible: true }).first();
  await expect(confirmation.locator("select[name=country]")).toHaveValue("NZ");
  await expect(confirmation.locator("select[name=country] option:checked")).toHaveText("New Zealand (synthetic demo)");
  await expect(confirmation).toContainText("NZD");
  await confirmation.locator("input[name=amount]").fill("13500");
  await expect(confirmation.locator("input[name=amount]")).toHaveValue("13500");
  await page.screenshot({ path: join(evidenceDirectory, "en-nz-confirmation.png"), fullPage: true, animations: "disabled" });
  await page.getByTestId("confirm-comparison").filter({ visible: true }).first().click();
  await expect(page.getByTestId("comparison").filter({ visible: true }).first()).toContainText("NZD");
  await expect(page.getByTestId("comparison").filter({ visible: true }).first()).not.toContainText("DOP");
  await page.getByRole("button", { name: /^(Save comparison|Guardar comparación)$/ }).first().click();
  await expect.poll(async () => {
    const home = await (await page.request.get("/api/home")).json();
    return home.saved[0]?.baseline.inputs;
  }).toMatchObject({ country: "NZ", currency: "NZD", amount: "13500.00" });
  await page.reload();
  await expect(page.locator("html")).toHaveAttribute("lang", "en");
  expect(externalRequests).toEqual([]);
});

test("mobile money view fits the maximum supported amount", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await login(page, "es");
  await navigate(page, "deposits");
  await page.getByRole("button", { name: "Revisar monto y plazo" }).click();
  await page.getByTestId("confirmation").filter({ visible: true }).locator("input[name=amount]").fill("1000000000000");
  await expect(page.getByTestId("confirmation").filter({ visible: true }).locator("input[name=amount]")).toHaveValue("1000000000000");
  await page.getByTestId("confirm-comparison").filter({ visible: true }).first().click();
  await expect(page.getByTestId("comparison").filter({ visible: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1)).toBe(false);
  await page.screenshot({ path: join(evidenceDirectory, "es-390-maximum-amount.png"), fullPage: true, animations: "disabled" });
});
