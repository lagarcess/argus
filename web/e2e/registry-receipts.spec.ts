import { appendFileSync, mkdirSync } from "node:fs";
import path from "node:path";
import { expect, test, type Locator, type Route } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";
import { REGISTRY_RECEIPT_CONVERSATION, registryReceiptFixture } from "./support/registry-receipt-fixture";
import { receiptCopy, receiptTranslator } from "../lib/receipt-copy";
import { localizedToolText, toolFactValue } from "../lib/tool-result-card";

const json = (route: Route, value: unknown) => route.fulfill({ json: value });

for (const language of ["en", "es-419"] as const) for (const width of [390, 1280]) {
  test.describe(`${language} ${width}`, () => {
    test.use({ locale: language });
    test(`selected mixed receipt keeps DCA and sibling tool answers ${language} ${width}`, async ({ page }) => {
      await page.setViewportSize({ width, height: 900 });
      await installMobileShellFixture(page, { language, theme: "light", account: "registered" });
      const fixture = registryReceiptFixture(language);
      const copy = receiptCopy(language);
      const t = receiptTranslator(language);
      const mutations: unknown[] = [];
      const errors: string[] = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.route("**/api/v1/**", async (route) => {
        const request = route.request();
        const url = new URL(request.url());
        if (url.pathname.endsWith("/messages")) return json(route, { items: fixture.messages, next_cursor: null });
        if (url.pathname.endsWith("/public-excerpt-candidates")) return json(route, fixture.candidates);
        if (url.pathname.endsWith("/public-excerpt-preview")) {
          expect(request.postDataJSON().message_ids).toEqual(fixture.candidates.items.map((item) => item.message_id));
          return json(route, { payload: fixture.payload, kind: "mixed", payload_digest: "b".repeat(64) });
        }
        if (url.pathname.endsWith("/public-excerpt")) {
          mutations.push(request.postDataJSON());
          return json(route, { receipt: fixture.receipt });
        }
        return route.fallback();
      });
      const verify = async (main: Locator) => {
        const groups = main.locator("[data-receipt-tool-cards]");
        await expect(groups).toHaveCount(2);
        await expect(main.locator("[data-tool-answer]")).toHaveCount(3);
        await expect(main.locator("[data-tool-visual]")).toHaveCount(1);
        await expect(main.getByRole("link", { name: fixture.payload.turns[0].kind === "research_answer" ? fixture.payload.turns[0].sources[0].title : "" })).toBeVisible();
        for (const [index, turn] of fixture.payload.turns.filter((turn) => turn.kind === "tool_result").entries()) {
          for (const card of turn.cards) {
            await expect(groups.nth(index)).toContainText(toolFactValue(card.presentation.answer!, t, language));
            for (const input of card.presentation.inputs) await expect(groups.nth(index)).toContainText(toolFactValue(input, t, language));
            for (const note of card.presentation.notes) await expect(groups.nth(index)).toContainText(localizedToolText(note, t));
          }
        }
        await expect(groups.last().locator("[data-tool-answer]").first()).toContainText("0");
        await expect(groups.last().locator("[data-tool-answer]").last()).toContainText("40");
        await expect(groups.last().locator("input,select")).toHaveCount(0);
        await expect(main).not.toContainText("artifact-call");
        await expect(main).not.toContainText("test_echo");
        await expect(main).not.toContainText("receipt.");
      };
      const capture = async (name: string, fullPage = false) => {
        if (!process.env.REGISTRY_SCREENSHOT_DIR) return;
        mkdirSync(process.env.REGISTRY_SCREENSHOT_DIR, { recursive: true });
        await page.screenshot({ path: path.join(process.env.REGISTRY_SCREENSHOT_DIR, `${name}-${language}-${width}.png`), fullPage, animations: "disabled" });
        const scroll = await page.evaluate(() => ({
          windowY: window.scrollY,
          containers: Array.from(document.querySelectorAll("*")).filter((element) => element.scrollTop > 0)
            .map((element) => ({ role: element.getAttribute("role"), top: element.scrollTop, height: element.clientHeight, contentHeight: element.scrollHeight })),
        }));
        appendFileSync(path.join(process.env.REGISTRY_SCREENSHOT_DIR, "receipt-captures.jsonl"), JSON.stringify({ name, language, viewport: page.viewportSize(), fullPage, scroll }) + "\n");
      };
      await page.goto(`/chat?conversation=${REGISTRY_RECEIPT_CONVERSATION}`, { waitUntil: "networkidle" });
      await page.getByRole("button", { name: copy.selection.title, exact: true }).click();
      const dialog = page.getByRole("dialog", { name: copy.selection.title, exact: true });
      await expect(dialog.getByRole("checkbox")).toHaveCount(fixture.candidates.items.length);
      await dialog.getByRole("button", { name: copy.selection.all, exact: true }).click();
      await capture("receipt-selection");
      await dialog.getByRole("button", { name: copy.selection.preview, exact: true }).click();
      const preview = dialog.locator("main");
      await verify(preview);
      await expect(dialog.getByRole("link", { name: copy.cta.action, exact: true })).toHaveCount(0);
      const siblings = preview.locator("[data-receipt-tool-cards]").last().locator(":scope > div");
      for (const [index, name] of ["first", "second"].entries()) {
        await siblings.nth(index).scrollIntoViewIfNeeded();
        await capture(`receipt-preview-${name}`);
      }
      expect(mutations).toEqual([]);
      await dialog.getByRole("button", { name: copy.owner.create, exact: true }).click();
      await expect(dialog.getByRole("textbox", { name: copy.owner.copy, exact: true })).toHaveValue(new URL(fixture.receipt.path, page.url()).href);
      expect(mutations).toEqual([{ message_ids: fixture.candidates.items.map((item) => item.message_id), owner_note: null, payload_digest: "b".repeat(64) }]);
      const publicResponse = await page.goto(fixture.receipt.path, { waitUntil: "networkidle" });
      expect(await publicResponse?.request().headerValue("accept-language")).toContain(language);
      await verify(page.locator("main"));
      await expect(page.getByRole("link", { name: copy.cta.action, exact: true })).toHaveAttribute("href", "/");
      expect(await page.locator('meta[name="robots"]').getAttribute("content")).toContain("noindex");
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
      await page.locator("main p").last().scrollIntoViewIfNeeded();
      await capture("receipt-public-mixed", true);
      expect(errors).toEqual([]);
    });
  });
}
