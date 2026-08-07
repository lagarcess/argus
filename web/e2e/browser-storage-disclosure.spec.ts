import { expect, test } from "@playwright/test";

import { STORAGE_REGISTRY } from "../lib/browser-storage";

/**
 * Observation backstop for the storage chokepoint.
 *
 * The chokepoint plus the ESLint ban make an undisclosed key hard to write.
 * This watches what a real browser actually persisted during a real journey,
 * so it does not depend on predicting syntax: an aliased handle, a wrapper, a
 * dynamic key, or a dependency writing its own key are all recorded the same
 * way, because Storage.prototype is patched before any page script runs.
 *
 * Bounded by the journey below. That bound is why the chokepoint exists too.
 */

const DISCLOSED = new Set(Object.keys(STORAGE_REGISTRY));

test("every key a real session writes is a disclosed key", async ({ page }) => {
  await page.addInitScript(() => {
    const written: string[] = [];
    (window as unknown as { __argusWrites: string[] }).__argusWrites = written;

    for (const proto of [Storage.prototype]) {
      const setItem = proto.setItem;
      proto.setItem = function (key: string, value: string) {
        written.push(key);
        return setItem.call(this, key, value);
      };
    }
  });

  // A journey that exercises the surfaces which persist anything: landing,
  // theme boot, language detection, the legal pages, and the chat shell.
  await page.goto("/");
  await page.waitForLoadState("networkidle");
  await page.goto("/privacy");
  await page.waitForLoadState("networkidle");
  await page.goto("/terms");
  await page.waitForLoadState("networkidle");
  await page.goto("/");
  await page.waitForLoadState("networkidle");

  const written = await page.evaluate(() => [
    ...new Set((window as unknown as { __argusWrites: string[] }).__argusWrites),
  ]);
  const observedKeys = await page.evaluate(() => Object.keys(window.localStorage));

  const undisclosed = [...new Set([...written, ...observedKeys])]
    .filter((key) => !DISCLOSED.has(key))
    .sort();

  expect(
    undisclosed,
    `keys persisted but not in STORAGE_REGISTRY: ${undisclosed.join(", ")}. ` +
      "Register them and disclose them in the privacy copy.",
  ).toEqual([]);

  // The instrumentation has to have seen something, or an empty result would
  // read as full coverage.
  expect(written.length).toBeGreaterThan(0);
});
