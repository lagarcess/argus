import { expect, test } from "@playwright/test";

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
    await expect(
      page.getByRole("img", { name: /Cuadrao Business/ }),
    ).toBeVisible();
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

test("footer moves automatically, pauses and ends at the page edge", async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto("/");
  const control = page.getByRole("button", { name: "Pausar animación" });
  await control.scrollIntoViewIfNeeded();
  const panel = page.locator("footer [data-paused]");
  await expect(panel).toHaveAttribute("data-visible", "true");
  const positions = () =>
    panel
      .locator("i")
      .first()
      .evaluate((node) => getComputedStyle(node).left);
  const before = await positions();
  await expect.poll(positions).not.toBe(before);
  await control.click();
  const stopped = await positions();
  await page.waitForTimeout(250);
  expect(await positions()).toBe(stopped);
  await expect(
    page.getByRole("button", { name: "Reanudar animación" }),
  ).toHaveAttribute("aria-pressed", "true");
  const bottom = await panel.evaluate((node) =>
    Math.abs(
      node.getBoundingClientRect().bottom +
        window.scrollY -
        document.documentElement.scrollHeight,
    ),
  );
  expect(bottom).toBeLessThanOrEqual(2);
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

test("editorial photographs and product evidence load", async ({ page }) => {
  await page.goto("/");
  for (const image of await page.locator("main img").all()) {
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
