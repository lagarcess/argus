import { expect, test, type Page } from "@playwright/test";

for (const path of ["/", "/en"]) {
  test(`${path} preserves the capture story and accessible progress rail`, async ({
    page,
  }) => {
    await page.goto(path);
    const tabs = page.getByRole("tab");
    await expect(tabs).toHaveCount(3);
    await tabs.first().focus();
    await page.keyboard.press("ArrowRight");
    await expect(tabs.nth(1)).toBeFocused();
    await expect(tabs.nth(1)).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("tabpanel")).toContainText("RD$ 1,250");
    await page.keyboard.press("End");
    await expect(tabs.last()).toHaveAttribute("aria-selected", "true");
    await expect(page.getByRole("tabpanel")).toContainText(
      path === "/" ? "Aprobado" : "Approved",
    );
    await expect(page.locator("iframe")).toHaveCount(0);
  });
}

test("header blends at the top and becomes a pill after scrolling", async ({
  page,
}) => {
  await page.goto("/");
  const header = page.locator("header");
  expect(
    await header.evaluate((node) => getComputedStyle(node).borderRadius),
  ).toBe("0px");
  await page.evaluate(() => window.scrollTo(0, 350));
  await expect
    .poll(() => header.evaluate((node) => getComputedStyle(node).borderRadius))
    .toBe("44px");
  await expect(
    header.getByRole("img", { name: "cuadrao", exact: true }),
  ).toBeVisible();
});

for (const locale of ["es", "en"] as const) {
  test(`${locale} header separates language controls and links to how it works`, async ({ page }) => {
    const home = locale === "es" ? "/" : "/en";
    await page.goto(home);
    const header = page.locator("header");
    const menu = header.getByRole("button", { name: /Abrir menú|Open menu/ });
    const mobile = await menu.isVisible();
    if (mobile) {
      await menu.click();
      await page.keyboard.press("Escape");
      await expect(menu).toBeFocused();
      await menu.click();
    }
    const navigation = header.locator("nav:visible");
    const languages = navigation.getByRole("group", { name: locale === "es" ? "Idioma" : "Language" });
    await expect(languages.getByRole("link", { name: locale.toUpperCase(), exact: true })).toHaveAttribute("aria-current", "true");
    for (const language of ["es", "en"]) {
      const link = languages.getByRole("link", { name: language.toUpperCase(), exact: true });
      await expect(link).toHaveAttribute("href", language === "es" ? "/" : "/en");
      const bounds = await link.boundingBox();
      expect(bounds!.width).toBeGreaterThanOrEqual(44);
      expect(bounds!.height).toBeGreaterThanOrEqual(44);
    }
    await navigation.getByRole("link", { name: locale === "es" ? "Cómo funciona" : "How it works", exact: true }).click();
    await expect(page).toHaveURL(`${home}#el-producto`);
    if (mobile) await menu.click();
    await header.locator("nav:visible").getByRole("group").getByRole("link", { name: locale === "es" ? "EN" : "ES", exact: true }).click();
    await expect(page).toHaveURL(locale === "es" ? "/en" : "/");
  });
}

async function footerEnd(page: Page) {
  await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
  await expect.poll(() => page.evaluate(() =>
    document.documentElement.scrollHeight - window.innerHeight - window.scrollY,
  )).toBeLessThanOrEqual(2);
  return page.locator("[data-footer-peek]");
}

async function footerReveal(page: Page) {
  return page.locator("[data-footer-peek]").evaluate((frame) =>
    frame.getBoundingClientRect().bottom -
    frame.querySelector("img")!.parentElement!.getBoundingClientRect().top,
  );
}

test("footer rests at the crop, peeks on extra wheel input and settles without added height", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  const frame = await footerEnd(page);
  for (const source of ["footer-dressmaker", "footer-artisan"]) {
    const image = frame.locator(`img[src*="${source}"]`);
    await expect(image).toHaveCount(1);
    await expect.poll(() => image.evaluate((node: HTMLImageElement) =>
      node.complete && node.naturalWidth > 0,
    )).toBe(true);
  }
  await expect.poll(() => footerReveal(page)).toBeLessThanOrEqual(0.5);
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  const end = await frame.evaluate((node) => node.getBoundingClientRect().bottom + window.scrollY);
  expect(Math.abs(end - height)).toBeLessThanOrEqual(2);
  await expect(page.getByRole("button", { name: /Pausar animación|Pause animation/ })).toHaveCount(0);
  await page.mouse.move(100, 800);
  await page.mouse.wheel(0, 500);
  await expect.poll(() => footerReveal(page), { intervals: [20] }).toBeGreaterThan(5);
  expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBe(height);
  await expect.poll(() => footerReveal(page)).toBeLessThanOrEqual(0.5);
  expect(await page.evaluate(() => document.documentElement.scrollHeight)).toBe(height);
});

test("footer accumulates gentle wheel input without losing it between paint frames", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  const frame = await footerEnd(page);
  await frame.evaluate((target) => {
    for (let step = 0; step < 10; step++) {
      target.dispatchEvent(new WheelEvent("wheel", { bubbles: true, deltaY: 8 }));
    }
  });
  await expect.poll(() => footerReveal(page), { intervals: [20] }).toBeGreaterThan(50);
  await expect.poll(() => footerReveal(page)).toBeLessThanOrEqual(0.5);
});

test("footer preserves upward wheel and keyboard navigation", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  await footerEnd(page);
  const bottom = await page.evaluate(() => window.scrollY);
  await page.mouse.move(100, 800);
  await page.mouse.wheel(0, 500);
  await expect.poll(() => footerReveal(page), { intervals: [20] }).toBeGreaterThan(5);
  await page.mouse.wheel(0, -350);
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThan(bottom - 100);
  await expect.poll(() => footerReveal(page)).toBeLessThanOrEqual(0.5);
  await footerEnd(page);
  await page.keyboard.press("PageUp");
  await expect.poll(() => page.evaluate(() => window.scrollY)).toBeLessThan(bottom - 100);
});

test("footer holds a dispatched touch drag open until release", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  await footerEnd(page);
  await page.locator("[data-footer-peek]").evaluate((target) => {
    const touch = (clientY: number) => new Touch({ identifier: 1, target, clientX: 100, clientY });
    target.dispatchEvent(new TouchEvent("touchstart", { bubbles: true, touches: [touch(700)] }));
    target.dispatchEvent(new TouchEvent("touchmove", { bubbles: true, touches: [touch(500)] }));
  });
  await expect.poll(() => footerReveal(page), { intervals: [20] }).toBeGreaterThan(5);
  await page.waitForTimeout(650);
  expect(await footerReveal(page)).toBeGreaterThan(100);
  await page.locator("[data-footer-peek]").dispatchEvent("touchend", { touches: [] });
  await expect.poll(() => footerReveal(page)).toBeLessThanOrEqual(0.5);
});

test("reduced motion keeps the crop fixed under extra scroll input", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/");
  await footerEnd(page);
  await page.mouse.move(100, 800);
  await page.mouse.wheel(0, 500);
  await page.waitForTimeout(250);
  expect(await footerReveal(page)).toBeLessThanOrEqual(0.5);
});

test("reduced motion is static and small screens do not overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 740 });
  await page.emulateMedia({ reducedMotion: "reduce" });
  for (const path of [
    "/",
    "/en",
    "/personal",
    "/en/personal",
    "/contacto",
    "/en/contact",
    "/privacidad",
    "/en/privacy",
  ]) {
    await page.goto(path);
    await expect(
      page.getByRole("button", { name: /Pausar animación|Pause animation/ }),
    ).toBeHidden();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow, path).toBeLessThanOrEqual(1);
    const external = await page
      .locator('img[src^="http://127.0.0.1:4511"]')
      .count();
    expect(external).toBe(0);
  }
});

for (const path of ["/", "/en"]) {
  test(`${path} loads editorial photographs without the withdrawn product capture`, async ({
    page,
  }) => {
    await page.goto(path);
    await expect(
      page.locator('img[src*="business-review"], a[href*="business-review"]'),
    ).toHaveCount(0);
    const photographs = page.locator(
      'main img[src*="florist"], main img[src*="accountant"]',
    );
    await expect(photographs).toHaveCount(2);
    for (const image of await photographs.all()) {
      await image.scrollIntoViewIfNeeded();
      await expect
        .poll(() =>
          image.evaluate(
            (element: HTMLImageElement) =>
              element.complete && element.naturalWidth > 0,
          ),
        )
        .toBe(true);
    }
  });
}
