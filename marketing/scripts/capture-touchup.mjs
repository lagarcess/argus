import { chromium } from "@playwright/test";
import { mkdir, writeFile } from "node:fs/promises";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
const baseURL = process.env.MARKETING_CAPTURE_URL ?? "http://127.0.0.1:4512";
const root = new URL("../../", import.meta.url);
const output = new URL(
  "docs/reports/evidence/cuadrao-marketing-touchup/screens/",
  root,
);
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true });
const captures = [];
try {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 1000 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const load = async (route) => {
    await page.goto(new URL(route, baseURL).href);
    for (const image of await page.locator("img:visible").all()) {
      await image.scrollIntoViewIfNeeded();
      await image.evaluate(async (element) => {
        await element.decode();
      });
    }
    await page.evaluate(() => scrollTo(0, 0));
    await page.waitForTimeout(100);
  };
  for (const [route, name] of [
    ["/", "business-es"],
    ["/en", "business-en"],
    ["/personal", "personal-es"],
    ["/en/personal", "personal-en"],
    ["/contacto", "contact-es"],
    ["/en/contact", "contact-en"],
    ["/privacidad", "privacy-es"],
    ["/en/privacy", "privacy-en"],
  ]) {
    await load(route);
    await page.screenshot({
      path: fileURLToPath(new URL(`${name}.png`, output)),
      fullPage: true,
    });
    captures.push({ route, file: `${name}.png`, width: 1440 });
  }
  for (const width of [320, 390]) {
    await page.setViewportSize({ width, height: 844 });
    await load("/");
    await page.screenshot({
      path: fileURLToPath(new URL(`business-es-${width}.png`, output)),
      fullPage: true,
    });
    captures.push({ route: "/", file: `business-es-${width}.png`, width });
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.emulateMedia({ reducedMotion: "no-preference" });
  await page.goto(baseURL);
  const panel = page.locator("footer [data-paused]");
  await panel.scrollIntoViewIfNeeded();
  for (const image of await panel.locator("img").all())
    await image.evaluate(async (element) => {
      await element.decode();
    });
  await page.screenshot({
    path: fileURLToPath(new URL("footer-motion-start.png", output)),
  });
  await page.waitForTimeout(2500);
  await page.screenshot({
    path: fileURLToPath(new URL("footer-motion-later.png", output)),
  });
  await page.getByRole("button", { name: "Pausar animación" }).click();
  await page.screenshot({
    path: fileURLToPath(new URL("footer-paused.png", output)),
  });
  await context.close();
} finally {
  await browser.close();
}
await writeFile(
  new URL("manifest.json", output),
  JSON.stringify(
    {
      sourceCommit: execFileSync("git", ["rev-parse", "HEAD"], {
        cwd: fileURLToPath(root),
        encoding: "utf8",
      }).trim(),
      capturedAt: new Date().toISOString(),
      baseURL,
      browser: "Playwright Chromium headless, isolated context",
      captures,
    },
    null,
    2,
  ) + "\n",
);
console.log(fileURLToPath(output));
