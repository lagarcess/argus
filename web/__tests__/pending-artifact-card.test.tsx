import { describe, expect, test } from "bun:test";
import i18next from "i18next";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";

import ChatMessage from "../components/chat/ChatMessage";
import { hydrateMessagesFromApi } from "../components/chat/chat-message-projection";
import type { Message, StrategyConfirmationPayload } from "../components/chat/types";
import type { ApiMessage } from "../lib/argus-api";
import { confirmationEditDisclosureText } from "../lib/confirmation-edit-disclosure";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";

const noChange = {
  unapplied: [{ op: "edit", target: "requested_change", reason: "no_change_applied" }],
  note: "A stale planner note must not override the materialized outcome.",
};

function card(): StrategyConfirmationPayload {
  return {
    confirmation_id: "pending-artifact-1",
    confirmation_state: "active",
    title: "AAPL",
    status: "ready_to_run",
    statusLabel: "Ready to run",
    summary: "Review this backtest before running it.",
    strategy_type: "buy_and_hold",
    rows: [{ key: "assets", label: "Assets", value: "AAPL" }],
    actions: [{
      id: "run-backtest",
      type: "run_backtest",
      label: "Run backtest",
      labelKey: "chat.confirmation.actions.run_backtest",
      payload: { confirmation_id: "pending-artifact-1" },
    }],
  };
}

function persisted(confirmation: Record<string, unknown>): ApiMessage {
  return {
    id: "assistant-card-1",
    conversation_id: "conversation-card-1",
    role: "assistant",
    content: "The artifact response remains available.",
    created_at: "2026-09-08T12:00:00Z",
    metadata: { confirmation_card: confirmation },
  };
}

async function translations(locale: "en" | "es-419") {
  const i18n = i18next.createInstance();
  await i18n.init({
    lng: locale,
    fallbackLng: false,
    interpolation: { escapeValue: false },
    resources: { en: { translation: en }, "es-419": { translation: es } },
  });
  return i18n;
}

async function renderMessage(message: Message, locale: "en" | "es-419" = "en") {
  return renderToStaticMarkup(createElement(
    I18nextProvider,
    { i18n: await translations(locale) },
    createElement(ChatMessage, { message }),
  ));
}

describe("pending artifact card boundary", () => {
  test.each([undefined, "backtest"])("hydrates legacy/explicit backtest kind %p", (kind) => {
    const raw = { ...card(), ...(kind ? { kind } : {}) };
    const [message] = hydrateMessagesFromApi([persisted(raw)]).messages;
    expect(message.confirmation).toMatchObject({ kind: "backtest" });
    expect(message.kind).toBe("strategy_confirmation");
    expect(message.actions?.[0].type).toBe("run_backtest");
    if (!kind) expect(raw).not.toHaveProperty("kind");
  });

  test.each(["future_calculation", "", null, 4])("does not hydrate explicit kind %p as a backtest", (kind) => {
    const [message] = hydrateMessagesFromApi([
      persisted({ ...card(), kind }),
    ]).messages;
    expect(message.confirmation).toBeUndefined();
    expect(message.kind).toBe("text");
    expect(message.content).toBe("The artifact response remains available.");
    expect(message.actions).toBeUndefined();
  });

  test("render dispatch does not launch an unknown card passed directly", async () => {
    const message = {
      id: "unknown-card",
      role: "ai",
      kind: "strategy_confirmation",
      content: "The artifact response remains available.",
      confirmation: { ...card(), kind: "future_calculation" },
    } as unknown as Message;
    const markup = await renderMessage(message);
    expect(markup).not.toContain("Run backtest");
    expect(markup).toContain(message.content!);
  });
});

describe("shared edit disclosure", () => {
  test.each([
    { locale: "en" as const, unchanged: "No requested changes were applied.", restate: "Please restate what you want to change." },
    { locale: "es-419" as const, unchanged: "No se aplicó ninguno de los cambios que pediste.", restate: "Vuelve a decir qué quieres cambiar." },
  ])("shows no application and restatement above the card in $locale", async ({ locale, unchanged, restate }) => {
    const [message] = hydrateMessagesFromApi([
      persisted({ ...card(), kind: "backtest", edit_disclosure: noChange }),
    ]).messages;
    const markup = await renderMessage(message, locale);
    expect(markup).toContain('data-testid="confirmation-edit-disclosure"');
    expect(markup).toContain(unchanged);
    expect(markup).toContain(restate);
    expect(markup.indexOf(unchanged)).toBeLessThan(markup.indexOf("AAPL"));
    expect(markup).not.toContain(noChange.note);
  });

  test.each(["en", "es-419"] as const)("preserves typed refusal and note-only behavior in %s", async (locale) => {
    const { t } = await translations(locale);
    const refusal = confirmationEditDisclosureText({
      unapplied: [{ op: "set", target: "capital", reason: "invalid_value" }],
      note: "This note incorrectly claims the capital changed.",
    }, t);
    expect(refusal).toBe(t("chat.confirmation.edit_disclosure.unapplied", {
      targets: t("chat.confirmation.edit_disclosure.targets.capital"),
    }));
    expect(confirmationEditDisclosureText({ unapplied: [], note: "  Planner refusal.  " }, t))
      .toBe("Planner refusal.");
    expect(confirmationEditDisclosureText(undefined, t)).toBeNull();
  });
});
