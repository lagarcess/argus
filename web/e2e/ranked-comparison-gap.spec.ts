import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";
import type { ComputationComparison } from "../lib/computation-contract";
import { parseToolResultCard, localizedToolText } from "../lib/tool-result-card";
import { translate } from "../__tests__/support/i18n-instance";

const fixture = JSON.parse(readFileSync(path.resolve(__dirname, "../__tests__/fixtures/calculation-cards.json"), "utf8"));
const comparison: ComputationComparison = fixture.ranked_comparison;
const conversationId = "conversation-alpha";

for (const language of ["en", "es-419"] as const) {
  test(`changed leaders retain both gap differences in ${language}`, async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await installMobileShellFixture(page, { language, theme: "light" });
    const instance = await translate(language);
    const t = instance.t.bind(instance);
    const card = parseToolResultCard(comparison.left.card)!;
    const errors: string[] = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.route("**/api/v1/**", async (route) => {
      const url = new URL(route.request().url());
      const json = (body: unknown) => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(body) });
      if (url.pathname === `/api/v1/conversations/${conversationId}/messages`) return json({ items: [{
        id: comparison.left.message_id, conversation_id: conversationId, role: "assistant", content: "",
        created_at: comparison.left.computed_at,
        metadata: { tool_result_cards: [card], computation: { kind: card.tool_name, inputs: card.arguments } },
      }], next_cursor: null });
      if (url.pathname === "/api/v1/computations/answers") return json({ items: [{ ...comparison.right, kind: card.tool_name, symbols: [] }] });
      if (url.pathname === "/api/v1/computations/compare") return json(comparison);
      return route.fallback();
    });
    await page.goto(`/chat?conversation=${conversationId}`, { waitUntil: "networkidle" });
    await expect(page.locator("[data-tool-result-card]")).toHaveCount(1);
    await page.locator('[data-compute-action="compare"]').click();
    await page.locator(`[data-compare-choice="${comparison.right.message_id}"]`).click();
    const view = page.locator("[data-computation-comparison]");
    await expect(view).toBeVisible();
    for (const side of ["left", "right"] as const) {
      const rankedCard = parseToolResultCard(comparison[side].card)!;
      const leaderGap = rankedCard.presentation.rows.find((row) => row.name === "gap_0")!;
      await expect(view.locator(`[data-compared="${side}"]`)).not.toContainText(localizedToolText(leaderGap.label, t));
    }
    for (const gap of comparison.differences.filter((fact) => fact.name.startsWith("gap_"))) {
      await expect(view.locator(`[data-difference="${gap.name}"]`)).toContainText(localizedToolText(gap.label, t));
    }
    expect(errors).toEqual([]);
    if (process.env.RANKED_GAP_SCREENSHOT_DIR) {
      mkdirSync(process.env.RANKED_GAP_SCREENSHOT_DIR, { recursive: true });
      await view.locator("[data-computation-differences]").screenshot({ path: path.join(process.env.RANKED_GAP_SCREENSHOT_DIR, `ranked-gap-${language}.png`), animations: "disabled" });
      for (const side of ["left", "right"]) {
        await view.locator(`[data-compared="${side}"]`).screenshot({ path: path.join(process.env.RANKED_GAP_SCREENSHOT_DIR, `ranked-card-${side}-${language}.png`), animations: "disabled" });
      }
    }
  });
}
