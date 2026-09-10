import { installRegistryEvidenceHooks } from "./registry-evidence-hooks";
import { mkdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { installMobileShellFixture } from "./support/mobile-shell-fixture";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";

const root = "/private/tmp/registry-declaration-browser-b17d2577";
const fixture = JSON.parse(readFileSync(path.join(root, "signal-cards.json"), "utf8"));
installRegistryEvidenceHooks();
for (const language of ["en", "es-419"] as const) {
  test(`authored signal card retains MACD windows and chart across reload ${language}`, async ({ page }) => {
    await page.setViewportSize({ width: language === "en" ? 1280 : 390, height: 1000 });
    await installMobileShellFixture(page, { language, theme: "light" });
    let messageReads = 0;
    await page.route("**/api/v1/conversations/conversation-alpha/messages**", route => {
      messageReads += 1;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ items: [{ id: "signal-message", conversation_id: "conversation-alpha", role: "assistant", content: "", created_at: "2026-09-10T12:00:00Z", metadata: { tool_result_cards: [fixture.cards[language]] } }], next_cursor: null }) });
    });
    const copy = (language === "en" ? en : es).receipt;
    const assertFacts = async () => {
      const card = page.locator("[data-tool-result-card]");
      await expect(card).toHaveCount(1);
      await expect(card.getByText(copy.strategy_type_values["macd crossover"], { exact: true })).toBeVisible();
      for (const key of ["fast_period", "slow_period", "signal_period"] as const) {
        const label = card.getByText(copy.strategy_facts[key], { exact: true });
        await expect(label).toBeVisible();
        await expect(label.locator("..")).toContainText(String(fixture.expected[key]));
      }
      await expect(card.locator("[data-tool-answer]")).toContainText(copy.metric_labels.total_return_pct);
      await expect(card.getByText(copy.assumptions.modeled_fee_bps.replace("{{bps}}", "10"), { exact: true })).toBeVisible();
      await expect(card.getByText(copy.assumptions.modeled_slippage_bps.replace("{{bps}}", "5"), { exact: true })).toBeVisible();
      await expect(card.locator("[data-tool-visual] canvas").first()).toBeVisible();
      await expect(card.locator("input, select")).toHaveCount(0);
      return card;
    };
    await page.goto("/chat?conversation=conversation-alpha", { waitUntil: "networkidle" });
    await assertFacts();
    await page.reload({ waitUntil: "networkidle" });
    const card = await assertFacts();
    expect(messageReads).toBe(2);
    mkdirSync(path.join(root, "screenshots"), { recursive: true });
    await card.screenshot({ path: path.join(root, "screenshots", `signal-card-${language}.png`), animations: "disabled" });
  });
}
