import { describe, expect, test } from "bun:test";
import i18next, { createInstance } from "i18next";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";
import StrategyConfirmationCard from "../components/chat/StrategyConfirmationCard";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";
import {
  recoveryDisplayFromMetadata,
  recoveryDisplayText,
  recoveryDisplayCopyText,
} from "../lib/chat-recovery-display";
import { localizeArtifactFinalPayload } from "../lib/artifact-response-transport";
import { streamChatMessage, type ChatStreamEvent } from "../lib/argus-api";

const displayFacts = {
  starting_capital: 0,
  recurring_contribution: 500,
  contribution_period: "monthly",
  fees: 0,
  slippage: 0,
  benchmark_symbol: "SPY",
  timeframe: "1D",
};
const response_intent = {
  kind: "artifact_assumptions",
  facts: { artifact_kind: "confirmation", asset_class: "equity", display_facts: displayFacts },
};

describe("typed artifact assumptions", () => {
  test.each(["en", "es-419"])("renders live, rehydrated and copied facts in %s", async (language) => {
    const i18n = createInstance();
    await i18n.init({ lng: language, resources: { en: { translation: en }, "es-419": { translation: es } } });
    const t = i18n.t.bind(i18n);
    const display = recoveryDisplayFromMetadata({ response_intent, content: "Private English prose" });
    expect(display?.kind).toBe("artifact_assumptions");
    const text = recoveryDisplayText(display, t, language);
    expect(text).not.toContain("Private English prose");
    expect(text).toContain("500");
    expect(text).toContain("SPY");
    expect(text).toContain(language === "en" ? "No fees" : "Sin comisiones");
    expect(text).toContain(language === "en" ? "No slippage" : "Sin deslizamiento");
    expect(text).toContain(language === "en" ? "Starting capital" : "Capital inicial");
    expect(text).toContain(t("chat.confirmation.contribution_periods.monthly"));
    expect(recoveryDisplayCopyText(display, t, language)).toBe(text);
    const payload = localizeArtifactFinalPayload({ response_intent, assistant_response: "" }, t, language);
    expect(payload.assistant_response).toBe(text);
    expect(payload).not.toHaveProperty("recovery");
    expect(payload.response_intent).toBe(response_intent);
  });

  test("missing legacy typed facts produce localized unavailable copy", async () => {
    const i18n = createInstance();
    await i18n.init({ lng: "es-419", resources: { "es-419": { translation: es } } });
    const display = recoveryDisplayFromMetadata({
      response_intent: { kind: "artifact_assumptions", facts: {} },
      content: "English legacy assumptions",
    });
    const text = recoveryDisplayText(display, i18n.t.bind(i18n), "es-419");
    expect(text).toBeTruthy();
    expect(text).not.toContain("English legacy assumptions");
  });

  test("a successful typed answer takes precedence over stale recovery metadata", () => {
    const display = recoveryDisplayFromMetadata({
      response_intent,
      recovery: { code: "interpreter_unavailable", retryable: true },
      clarification: { prompt_source: "llm_generated" },
    });
    expect(display?.kind).toBe("artifact_assumptions");
  });

  test("the rendered Spanish confirmation cannot use retained assumption prose", async () => {
    const poison = "PRIVATE_ENGLISH_ASSUMPTION_MUST_NEVER_RENDER";
    const i18n = createInstance();
    await i18n.init({ lng: "es-419", resources: { "es-419": { translation: es } } });
    const markup = renderToStaticMarkup(createElement(I18nextProvider, { i18n },
      createElement(StrategyConfirmationCard, { confirmation: {
        title: "AAPL", summary: poison,
        status: "ready_to_run", statusLabel: "Ready to run",
        strategy_type: "dca_accumulation", asset_class: "equity",
        rows: [{ key: "assets", label: "Assets", value: "AAPL" }],
        display_facts: displayFacts, assumptions: [poison], actions: [],
      } }),
    ));
    expect(markup).not.toContain(poison);
    expect(markup).toContain("Sin comisiones");
    expect(markup).toContain("Sin deslizamiento");
    expect(markup).toContain("SPY");
  });

  test("the live stream delivers a nonempty localized successful answer", async () => {
    const priorFetch = globalThis.fetch;
    const priorMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH;
    const priorLanguage = i18next.language;
    try {
      process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
      await i18next.init({ lng: "es-419", resources: { en: { translation: en }, "es-419": { translation: es } } });
      const frame = { type: "final", payload: { assistant_response: "", response_intent } };
      globalThis.fetch = (async () => new Response(`data: ${JSON.stringify(frame)}\n\ndata: [DONE]\n\n`, {
        status: 200,
        headers: { "Content-Type": "text/event-stream" },
      })) as typeof fetch;
      const events: ChatStreamEvent[] = [];
      await streamChatMessage("typed-assumptions", "Explain the assumptions", "es-419", event => events.push(event));
      const final = events.find(event => event.event === "final");
      expect(final?.event).toBe("final");
      if (final?.event !== "final") throw new Error("Missing final");
      expect(final.data.assistant_response).toContain("Sin comisiones");
      expect(final.data.response_intent).toEqual(response_intent);
      expect(final.data.recovery).toBeUndefined();
    } finally {
      globalThis.fetch = priorFetch;
      if (priorMockAuth === undefined) delete process.env.NEXT_PUBLIC_MOCK_AUTH;
      else process.env.NEXT_PUBLIC_MOCK_AUTH = priorMockAuth;
      await i18next.changeLanguage(priorLanguage ?? "en");
    }
  });
});
