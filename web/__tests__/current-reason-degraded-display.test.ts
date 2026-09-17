import { test, expect } from "bun:test";
import i18next from "i18next";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";
import probes from "../../docs/reports/evidence/current-reason-date-range/measurement/targeted-replies.json";
import { recoveryDisplayFromMetadata, recoveryDisplayText } from "../lib/chat-recovery-display";

for (const language of ["en", "es-419"]) {
  test(`degraded date reply states its current reason in ${language}`, async () => {
    const i18n = i18next.createInstance();
    await i18n.init({ lng: language, resources: { en: { translation: en }, "es-419": { translation: es } }, interpolation: { escapeValue: false } });
    const probe = probes.find((row) => row.language === "es-419" && row.turn === 1)!;
    const display = recoveryDisplayFromMetadata(probe.patch);
    const text = recoveryDisplayText(display, i18n.t.bind(i18n), language);
    expect(text).toBe(i18n.t("chat.clarification.data_window_unavailable"));
    expect(text).not.toContain("chat.clarification.");
    expect(text).not.toBe(probe.patch.assistant_prompt);
  });
  test(`missing capital bounds never reveal compatibility prose in ${language}`, async () => {
    const i18n = i18next.createInstance();
    await i18n.init({ lng: language, resources: { en: { translation: en }, "es-419": { translation: es } } });
    const probe = probes.find((row) => row.language === "es-419" && row.turn === 3)!;
    const patch = { ...probe.patch, clarification: { ...probe.patch.clarification, prompt_source: "degraded_fallback" } };
    const text = recoveryDisplayText(recoveryDisplayFromMetadata(patch), i18n.t.bind(i18n), language);
    expect(text).toBe(i18n.t("chat.clarification.starting_capital_unavailable_bounds"));
    expect(text).not.toContain("chat.clarification.");
    expect(text).not.toContain("100,000,000");
    expect(text.length).toBeGreaterThan(0);
  });
}
