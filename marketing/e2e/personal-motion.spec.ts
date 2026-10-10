import { expect, test, type Page } from "@playwright/test";
import { uniqueAddress } from "./support";

async function desktop(page: Page) {
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/personal");
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator("#personal-email")).toBeEnabled();
}

const hero = (page: Page) => page.locator("[data-signup-state]");

test("waits for confirmed registration, then delivers once while confirmation receives focus", async ({ page }, info) => {
  await desktop(page);
  const titleTop = (await page.locator("#personal-title").boundingBox())!.y;
  let accept: (() => void) | undefined;
  const gate = new Promise<void>((resolve) => { accept = resolve; });
  await page.route("**/api/signups", async (route) => {
    await gate;
    await route.fulfill({ json: { status: "registered" } });
  });
  await page.locator("#personal-email").fill(uniqueAddress(info));
  await page.locator("#personal-email").press("Enter");
  await expect(hero(page)).toHaveAttribute("data-signup-state", "submitting");
  await expect(page.locator("[data-signup-pet]")).toHaveAttribute("data-pose", "excited");
  await expect(page.locator("[data-signup-flight]")).toHaveCount(0);
  accept?.();
  await expect(page.getByRole("heading", { name: "Ya estás en la lista." })).toBeFocused();
  await expect(hero(page)).toHaveAttribute("data-flight-state", "flying");
  expect((await page.locator("#personal-title").boundingBox())!.y).toBeCloseTo(titleTop, 0);
  await expect(hero(page)).toHaveAttribute("data-flight-state", "settled");
  await expect(page.locator("[data-signup-flight]")).toHaveCount(0);
  await expect(page.locator("[data-phone-logo] [data-signup-pet]")).toHaveAttribute("data-pose", "delivered");
});

test("failed and unexpected responses preserve the email without a flight, then allow retry", async ({ page }, info) => {
  await desktop(page);
  const address = uniqueAddress(info);
  let attempt = 0;
  await page.route("**/api/signups", (route) => {
    attempt += 1;
    return route.fulfill(attempt === 1 ? { status: 503, json: { status: "unavailable" } } : attempt === 2 ? { json: { status: "pending" } } : { json: { status: "registered" } });
  });
  await page.locator("#personal-email").fill(address);
  for (let retry = 0; retry < 2; retry += 1) {
    await page.locator('button[type="submit"]').click();
    await expect(page.locator("#signup-error")).toBeVisible();
    await expect(page.locator("#personal-email")).toHaveValue(address);
    await expect(hero(page)).toHaveAttribute("data-flight-state", "rest");
    await expect(page.locator("[data-signup-flight]")).toHaveCount(0);
  }
  await page.locator('button[type="submit"]').click();
  await expect(hero(page)).toHaveAttribute("data-signup-state", "success");
});

test("fine-pointer eyes follow and reset without changing form focus", async ({ page }, info) => {
  test.skip(info.project.name === "mobile", "Touch does not track a pointer.");
  await desktop(page);
  await page.locator("#personal-email").focus();
  const bounds = await hero(page).boundingBox();
  if (!bounds) throw new Error("Personal hero is missing");
  await page.mouse.move(bounds.x + bounds.width - 20, bounds.y + 50);
  await expect.poll(() => hero(page).evaluate((element) => parseFloat((element as HTMLElement).style.getPropertyValue("--eye-x")))).toBeGreaterThan(0);
  await expect(page.locator("#personal-email")).toBeFocused();
  await page.mouse.move(0, 0);
  await expect.poll(() => hero(page).evaluate((element) => (element as HTMLElement).style.getPropertyValue("--eye-x"))).toBe("0px");
});

test("reduced motion confirms directly with a still pet", async ({ page }, info) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await desktop(page);
  await page.route("**/api/signups", (route) => route.fulfill({ json: { status: "registered" } }));
  await page.locator("#personal-email").fill(uniqueAddress(info));
  await page.locator("#personal-email").press("Enter");
  await expect(page.getByRole("heading", { name: "Ya estás en la lista." })).toBeFocused();
  await expect(hero(page)).toHaveAttribute("data-flight-state", "settled");
  await expect(page.locator("[data-signup-flight]")).toHaveCount(0);
  expect(await page.locator("[data-signup-pet]").evaluate((element) => getComputedStyle(element).animationName)).toBe("none");
});

for (const width of [320, 390]) {
  test(`narrow ${width}px form confirms without scrolling toward the offscreen phone`, async ({ page }, info) => {
    await page.setViewportSize({ width, height: 844 });
    await page.goto("/en/personal");
    await page.route("**/api/signups", (route) => route.fulfill({ json: { status: "registered" } }));
    await page.locator("#personal-email").fill(uniqueAddress(info));
    await page.locator('button[type="submit"]').scrollIntoViewIfNeeded();
    const before = await page.evaluate(() => window.scrollY);
    await page.locator("#personal-email").press("Enter");
    await expect(page.getByRole("heading", { name: "You're on the list." })).toBeFocused();
    await expect(page.locator("[data-signup-flight]")).toHaveCount(0);
    expect(await page.evaluate(() => window.scrollY)).toBe(before);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
    await expect(page.getByAltText(/welcome screen with its logo/)).toBeVisible();
  });
}

test("scrolling during delivery removes the flight and keeps the true confirmation", async ({ page }, info) => {
  await desktop(page);
  await page.route("**/api/signups", (route) => route.fulfill({ json: { status: "registered" } }));
  await page.locator("#personal-email").fill(uniqueAddress(info));
  await page.locator("#personal-email").press("Enter");
  await expect(hero(page)).toHaveAttribute("data-flight-state", "flying");
  await page.mouse.wheel(0, 120);
  await expect(hero(page)).toHaveAttribute("data-flight-state", "settled");
  await expect(page.getByRole("heading", { name: "Ya estás en la lista." })).toBeVisible();
  await expect(page.locator("[data-signup-flight]")).toHaveCount(0);
});

test("phone welcome labels follow the page language in both directions", async ({ page }) => {
  await desktop(page);
  const actions = page.locator("[data-phone-actions]");
  await expect(actions).toHaveText("Crear cuentaIniciar sesión");
  await page.getByRole("group", { name: "Idioma" }).getByRole("link", { name: "EN", exact: true }).click();
  await expect(page).toHaveURL(/\/en\/personal$/);
  await expect(actions).toHaveText("Create accountSign in");
  await expect(page.getByAltText("Cuadrao Personal welcome screen with its logo and create-account button.")).toBeVisible();
  await page.getByRole("group", { name: "Language" }).getByRole("link", { name: "ES", exact: true }).click();
  await expect(page).toHaveURL(new URL("/personal", page.url()).href);
  await expect(actions).toHaveText("Crear cuentaIniciar sesión");
  await expect(actions).toHaveAttribute("aria-hidden", "true");
  await expect(actions.locator("button, a, input")).toHaveCount(0);
});
