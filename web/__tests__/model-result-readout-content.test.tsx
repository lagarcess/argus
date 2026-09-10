import { describe, expect, test } from "bun:test";
import { createInstance } from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";
import ChatMessage from "../components/chat/ChatMessage";
import { hydrateMessagesFromApi } from "../components/chat/chat-message-projection";
import { resultCardFromRun, type ApiMessage, type BacktestRun } from "../lib/argus-api";
import { applyBacktestJobUpdate } from "../lib/chat-backtest-jobs";
import { resultCardViewModel } from "../lib/result-card-view-model";
import { resultCardCopyText } from "../lib/chat-card-copy-text";
import { resultBreakdownText, resultQuickTakeText } from "../lib/result-readout-display";
import { resultReadoutFacts } from "../lib/result-readout-facts";
import { chatMessageCopyText } from "../lib/chat-message-copy-text";
import { mergeFinalTextMessage } from "../lib/chat-final-message";
import { resultReadoutContentFromMetadata } from "../lib/result-readout-content";
import { localizeArtifactFinalPayload } from "../lib/artifact-response-transport";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";

const bank = {
  symbols: ["DOCN"], benchmark_symbol: "SPY", asset_class: "equity",
  config_snapshot: { template: "buy_and_hold", resolved_parameters: { starting_capital: 1000 } },
  figures: { total_return_pct: 12.5, benchmark_return_pct: 20, delta_vs_benchmark_pct: -7.5,
    benchmark_comparison_claim: "lagged_benchmark", max_drawdown_pct: -25 },
};
const privateText = "PRIVATE LEGACY PROSE";
const texts = {
  en: { quick_take: "The gain came with a rough ride and trailed the benchmark.", breakdown: "Volatility describes how uneven the journey was. The worst drop measures the fall from a prior peak." },
  "es-419": { quick_take: "La ganancia vino con altibajos y quedó por debajo del referente.", breakdown: "La volatilidad describe los altibajos del recorrido. La peor caída mide el descenso desde un máximo anterior." },
};
type Surface = "quick_take" | "breakdown";
type Language = keyof typeof texts;
const envelope = (surface: Surface, language: Language) => ({ schema_version: "result_readout/v1" as const, surface, language, text: texts[language][surface] });
async function translations(language: string) {
  const i18n = createInstance();
  await i18n.init({ lng: language, fallbackLng: "en", resources: { en: { translation: en }, "es-419": { translation: es } }, interpolation: { escapeValue: false } });
  return i18n;
}
function savedMessage(surface: Surface, value?: unknown): ApiMessage {
  return { id: crypto.randomUUID(), conversation_id: crypto.randomUUID(), role: "assistant",
    created_at: new Date().toISOString(), content: privateText, metadata: {
      artifact_presentation_kind: surface === "quick_take" ? "result" : "breakdown", result_fact_bank: bank,
      ...(surface === "breakdown" ? { chat_action: { type: "show_breakdown" }, response_intent: { kind: "result_breakdown", facts: { result_fact_bank: bank } } } : {}),
      ...(value === undefined ? {} : { result_readout_content: value }),
    } };
}
function run(value?: ReturnType<typeof envelope>): BacktestRun {
  return { id: crypto.randomUUID(), status: "completed", asset_class: "equity", symbols: bank.symbols,
    benchmark_symbol: bank.benchmark_symbol, allocation_method: "equal_weight", config_snapshot: bank.config_snapshot,
    metrics: { aggregate: {}, by_symbol: {} }, figures: bank.figures, created_at: new Date().toISOString(),
    conversation_result_card: { title: "DOCN", status_label: "Simulation Complete", rows: [], actions: [], assumptions: [],
      date_range: { start: "2023-09-01", end: "2026-09-09", display: "" }, result_readout_content: value } };
}

for (const surface of ["quick_take", "breakdown"] as const) {
  describe(`${surface} creation-language boundary`, () => {
    const template = surface === "quick_take" ? resultQuickTakeText : resultBreakdownText;
    for (const language of ["en", "es-419"] as const) {
      test(`renders complete ${language} model content in the existing frame`, async () => {
        const i18n = await translations(language);
        const message = hydrateMessagesFromApi([savedMessage(surface, envelope(surface, language))]).messages[0];
        const html = renderToStaticMarkup(<I18nextProvider i18n={i18n}><ChatMessage message={message} /></I18nextProvider>);
        expect(html).toContain(texts[language][surface]);
        expect(chatMessageCopyText(message, i18n.t, language)).toBe(texts[language][surface]);
        expect(html).toContain(i18n.t(surface === "quick_take" ? "chat.result_readout.quick_take" : "chat.result_breakdown.label"));
        expect(html).not.toContain(privateText);
      });
      test(`language mismatch and old ${language} results keep exactly today's template`, async () => {
        const i18n = await translations(language);
        const other = language === "en" ? "es-419" : "en";
        const expected = template(resultReadoutFacts(bank), i18n.t, language);
        for (const value of [undefined, envelope(surface, other)]) {
          const message = hydrateMessagesFromApi([savedMessage(surface, value)]).messages[0];
          const html = renderToStaticMarkup(<I18nextProvider i18n={i18n}><ChatMessage message={message} /></I18nextProvider>);
          for (const paragraph of expected.split("\n\n")) expect(html).toContain(paragraph);
          expect(chatMessageCopyText(message, i18n.t, language)).toBe(expected);
          expect(html).not.toContain(privateText);
          expect(html).not.toContain(texts[other][surface]);
        }
      });
    }
    test.each(["en", "en-US", "EN-us", "es", "es-419", "es-MX"])("matches workspace language alias %s", async (locale) => {
      const language = locale.toLowerCase().startsWith("es") ? "es-419" : "en";
      const i18n = await translations(language);
      expect(template(resultReadoutFacts(bank), i18n.t, locale, envelope(surface, language))).toBe(texts[language][surface]);
    });
    test.each([
      { schema_version: "result_readout/v0" }, { surface: "other" }, { language: "fr" }, { language: "en-US" },
      { text: null }, { text: " " }, { text: 42 }, { private_extra: privateText },
    ])("rejects malformed or failed envelopes: %j", async (patch) => {
      const i18n = await translations("en");
      expect(template(resultReadoutFacts(bank), i18n.t, "en", { ...envelope(surface, "en"), ...patch })).toBe(template(resultReadoutFacts(bank), i18n.t, "en"));
    });
    test("requires every field, rejects the other frame and unsupported workspace language", async () => {
      const i18n = await translations("en");
      const expected = template(resultReadoutFacts(bank), i18n.t, "en");
      for (const key of Object.keys(envelope(surface, "en"))) {
        const value: Record<string, unknown> = { ...envelope(surface, "en") };
        delete value[key];
        expect(template(resultReadoutFacts(bank), i18n.t, "en", value)).toBe(expected);
      }
      expect(template(resultReadoutFacts(bank), i18n.t, "en", envelope(surface === "quick_take" ? "breakdown" : "quick_take", "en"))).toBe(expected);
      expect(template(resultReadoutFacts(bank), i18n.t, "fr", envelope(surface, "en"))).not.toBe(texts.en[surface]);
    });
  });
}

describe("model readout transport", () => {
  test.each(["en", "es-419"] as const)("result card read and copy preserve accepted %s text", async (language) => {
    const i18n = await translations(language);
    const result = resultCardFromRun(run(envelope("quick_take", language)));
    const view = resultCardViewModel(result, { t: i18n.t, locale: language });
    expect(view.readout).toBe(texts[language].quick_take);
    expect(resultCardCopyText(view, i18n.t)).toContain(texts[language].quick_take);
    const opposite = language === "en" ? "es-419" : "en";
    const mismatch = resultCardViewModel(result, { t: (await translations(opposite)).t, locale: opposite });
    expect(resultCardCopyText(mismatch, i18n.t)).not.toContain(texts[language].quick_take);
  });
  test("job completion transports the envelope without reviving the old readout field", async () => {
    const completed = run();
    const currentJob = { id: crypto.randomUUID(), conversation_id: crypto.randomUUID(), status: "queued" as const, retryable: false };
    const [message] = applyBacktestJobUpdate([{ id: crypto.randomUUID(), role: "ai", kind: "backtest_job", backtestJob: currentJob }], {
      job: { ...currentJob, status: "succeeded", result_run_id: completed.id }, run: completed,
      result_readout_content: envelope("quick_take", "en"), result_readout: privateText as never,
    });
    const i18n = await translations("en");
    expect(resultCardViewModel(message.result!, { t: i18n.t, locale: "en" }).readout).toBe(texts.en.quick_take);
    expect(message.content).toBe("");
  });
  test.each(["en", "es-419"] as const)("a live %s breakdown keeps the envelope through terminal localization", async (language) => {
    const i18n = await translations(language);
    const result_readout_content = envelope("breakdown", language);
    const payload = localizeArtifactFinalPayload({ assistant_response: "", result_readout_content,
      response_intent: { kind: "result_breakdown", facts: { result_fact_bank: bank } } }, i18n.t, language);
    expect(payload.assistant_response).toBe(texts[language].breakdown);
    expect(payload.result_readout_content).toEqual(result_readout_content);
  });
});


describe("transport authority and live state", () => {
  test.each(["missing", "accepted", "null", "malformed"])("a %s message envelope respects root ownership over the card", async (state) => {
    const card = run(envelope("quick_take", "en")).conversation_result_card;
    const root = state === "missing" ? {} : { result_readout_content: state === "accepted"
      ? { ...envelope("quick_take", "en"), text: "The accepted root draft." }
      : state === "null" ? null : { ...envelope("quick_take", "en"), private_extra: "untrusted" } };
    const source = savedMessage("quick_take");
    const [message] = hydrateMessagesFromApi([{ ...source, metadata: { ...source.metadata, result_card: card, ...root } }]).messages;
    const i18n = await translations("en");
    const view = resultCardViewModel(message.result!, { t: i18n.t, locale: "en" });
    if (state === "missing") expect(view.readout).toBe(texts.en.quick_take);
    else if (state === "accepted") expect(view.readout).toBe("The accepted root draft.");
    else expect(view.readout).toBe(resultQuickTakeText(message.result?.readoutFacts, i18n.t, "en"));
  });
  test("a live final preserves creation language through later workspace switches", async () => {
    const saved = savedMessage("breakdown", envelope("breakdown", "en"));
    const original = hydrateMessagesFromApi([saved]).messages[0];
    const final = mergeFinalTextMessage({ ...original, resultReadoutContent: undefined }, {
      assistantId: original.id, finalText: "", finalActions: [], contentPresentation: "result_breakdown",
      resultReadoutContent: resultReadoutContentFromMetadata(saved.metadata), recoveryDisplay: original.recoveryDisplay,
    });
    expect(chatMessageCopyText(final, (await translations("en")).t, "en")).toBe(texts.en.breakdown);
    expect(chatMessageCopyText(final, (await translations("es-419")).t, "es-419")).not.toContain(texts.en.breakdown);
    const failedFinal = mergeFinalTextMessage(final, {
      assistantId: final.id, finalText: "", finalActions: [], resultReadoutContent: null,
    });
    expect(chatMessageCopyText(failedFinal, (await translations("en")).t, "en")).not.toContain(texts.en.breakdown);
  });
  test("live result-only finals are visible and retain the new envelope", async () => {
    const i18n = await translations("en");
    const result_readout_content = envelope("quick_take", "en");
    const payload = localizeArtifactFinalPayload({ assistant_response: "", artifact_presentation_kind: "result",
      result_fact_bank: bank, result_readout_content }, i18n.t, "en");
    expect(payload.assistant_response).toBe(texts.en.quick_take);
    expect(payload.result_readout_content).toEqual(result_readout_content);
  });
});


test("a typed Breakdown needs no legacy action and keeps response-intent facts for fallback", async () => {
  const source = savedMessage("breakdown", envelope("breakdown", "en"));
  delete source.metadata!.chat_action;
  delete source.metadata!.result_fact_bank;
  source.metadata!.result_card = run(envelope("quick_take", "en")).conversation_result_card;
  const [message] = hydrateMessagesFromApi([source]).messages;
  expect(message.contentPresentation).toBe("result_breakdown");
  const i18n = await translations("es-419");
  expect(chatMessageCopyText(message, i18n.t, "es-419")).toBe(resultBreakdownText(resultReadoutFacts(bank), i18n.t, "es-419"));
});

for (const language of ["en", "es-419"] as const) {
  test(`the hydrated ${language} result message copies card facts and its visible Quick take exactly once`, async () => {
    const i18n = await translations(language);
    const otherLanguage = language === "en" ? "es-419" : "en";
    for (const value of [envelope("quick_take", language), envelope("quick_take", otherLanguage), undefined]) {
      const source = savedMessage("quick_take", value);
      source.metadata!.result_card = run(value).conversation_result_card;
      const [message] = hydrateMessagesFromApi([source]).messages;
      expect(message.kind).toBe("strategy_result");
      const expectedReadout = value?.language === language
        ? texts[language].quick_take
        : resultQuickTakeText(message.result?.readoutFacts, i18n.t, language);
      const html = renderToStaticMarkup(<I18nextProvider i18n={i18n}><ChatMessage message={message} /></I18nextProvider>);
      const copy = chatMessageCopyText(message, i18n.t, language);
      expect(html).toContain(expectedReadout);
      expect(copy.split(expectedReadout)).toHaveLength(2);
      expect(copy).toContain(i18n.t("chat.copy_card.assets"));
      expect(copy).toContain("DOCN");
      expect(copy).not.toContain(texts[otherLanguage].quick_take);
      expect(copy).not.toContain(privateText);
    }
  });
}
