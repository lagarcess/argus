import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { createInstance } from "i18next";
import { I18nextProvider } from "react-i18next";
import { renderToStaticMarkup } from "react-dom/server";
import ChatMessage from "../components/chat/ChatMessage";
import StrategyResultCard from "../components/chat/StrategyResultCard";
import { resultCardPlaygroundFixtures } from "../lib/result-card-playground-fixtures";
import { receiptCopy } from "../lib/receipt-copy";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";
import { researchTurn } from "./fixtures/receipt-turns";

const oldShortcutProps = { conversationId: "conversation", messageId: "answer", onShare: () => {} };

describe.each(["en", "es-419"] as const)("header-only sharing in %s", (language) => {
  test("research keeps its source control without a share pill", async () => {
    const i18n = createInstance();
    await i18n.init({ lng: language, resources: { en: { translation: en }, "es-419": { translation: es } } });
    for (const degraded of [false, true]) {
      const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><ChatMessage
        {...oldShortcutProps}
        message={{ id: "answer", role: "ai", kind: "text", content: researchTurn.answer, researchSources: researchTurn.sources, ...(degraded ? { researchDegradedCode: "research_figures_unverified" } : {}) }}
      /></I18nextProvider>);
      expect(markup).not.toContain(receiptCopy(language).owner.share);
      expect(markup).toContain(degraded ? i18n.t("chat.discovery_results.sources_panel_open_withheld") : i18n.t("chat.discovery_results.sources_panel_open", { count: researchTurn.sources.length }));
      expect(markup).toContain(i18n.t("chat.more_actions"));
    }
  });

  test("result cards retain their evidence without a share shortcut", async () => {
    const i18n = createInstance();
    await i18n.init({ lng: language, resources: { en: { translation: en }, "es-419": { translation: es } } });
    for (const fixture of resultCardPlaygroundFixtures.slice(0, 2)) {
      const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><StrategyResultCard {...oldShortcutProps} result={fixture.result} /></I18nextProvider>);
      expect(markup).not.toContain(receiptCopy(language).owner.share);
      expect(markup).toContain("<section");
    }
  });
});

test("the header is the sole component that mounts the sharing entry", () => {
  for (const name of ["ChatMessage", "StrategyResultCard"]) {
    const source = readFileSync(new URL(`../components/chat/${name}.tsx`, import.meta.url), "utf8");
    expect(source).not.toContain("ShareReceiptAction");
    expect(source).not.toContain("listReceiptCandidates");
    expect(source).not.toContain("onShare");
  }
  const header = readFileSync(new URL("../components/chat/ChatHeaderMenu.tsx", import.meta.url), "utf8");
  expect(header).toContain("<ShareReceiptAction");
  expect(header.indexOf("<ShareReceiptAction")).toBeLessThan(header.indexOf("<MoreVertical"));
});
