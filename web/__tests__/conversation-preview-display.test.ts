import { describe, expect, test } from "bun:test";
import { createInstance } from "i18next";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";
import { conversationPreviewText } from "../lib/conversation-preview-display";

describe("persisted conversation preview language", () => {
  test("the same saved result follows the reader language", async () => {
    const i18n = createInstance();
    await i18n.init({ lng: "en", resources: { en: { translation: en }, "es-419": { translation: es } } });
    const preview = { kind: "result" as const, symbols: ["NVDA"], template: "dca_accumulation" };
    expect(conversationPreviewText(preview, i18n.t)).toBe(`Backtest result · NVDA · ${en.chat.strategy_type.dca_accumulation}`);
    await i18n.changeLanguage("es-419");
    expect(conversationPreviewText(preview, i18n.t)).toBe(`Resultado de simulación · NVDA · ${es.chat.strategy_type.dca_accumulation}`);
  });

  test("user wording remains intact and missing facts never use saved prose", async () => {
    const i18n = createInstance();
    await i18n.init({ lng: "es-419", resources: { "es-419": { translation: es } } });
    expect(conversationPreviewText({ kind: "text", text: "My own idea", symbols: [] }, i18n.t)).toBe("My own idea");
    expect(conversationPreviewText(undefined, i18n.t)).toBe("Abre la conversación para ver los detalles");
  });

});
