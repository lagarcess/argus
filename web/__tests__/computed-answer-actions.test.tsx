import { afterEach, describe, expect, test } from "bun:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ComputationComparisonView } from "../components/chat/ComputationCompare";
import ComputedAnswerActions from "../components/chat/ComputedAnswerActions";
import { AnswerDossierView } from "../components/sidebar/command-palette/AnswerDossierView";
import type { AnswerDossier } from "../lib/answer-dossier-contract";
import { continuedFromMetadata, type ComputationComparison } from "../lib/computation-contract";
import { comparedValueText, differenceText, hasCitedInputs } from "../lib/computation-compare";
import {
  compareComputedAnswers,
  continueComputedAnswer,
  listComputedAnswers,
  refreshComputedAnswer,
} from "../lib/computations-api";
import type { ToolResultCard } from "../lib/tool-result-card";
import { translate } from "./support/i18n-instance";

const fixture = JSON.parse(
  readFileSync(join(import.meta.dir, "fixtures/calculation-cards.json"), "utf-8"),
) as { cards: Record<string, { card: ToolResultCard }>; comparison: ComputationComparison };
const comparison = fixture.comparison;

function dossier(card: ToolResultCard, availability: "available" | "account_conversion_required"): AnswerDossier {
  return {
    message_id: "m1",
    conversation_id: "c1",
    asked: "Is Apple expensive at this P/E?",
    computed_at: "2026-09-11T12:00:00Z",
    kind: card.tool_name,
    symbols: ["AAPL"],
    card,
    decision: null,
    decision_id: null,
    actions: [{ type: "answer_decision", availability, message_id: "m1", decision_state: null, note: null }],
  };
}

describe("two computed answers side by side", () => {
  for (const language of ["en", "es-419"] as const) {
    test(`differences come from the backend and print signed in their unit in ${language}`, async () => {
      const instance = await translate(language);
      const t = instance.t.bind(instance);
      const answer = comparison.differences.find((difference) => difference.section === "answer");
      expect(answer?.difference).toBe(4.8);
      expect(differenceText(answer!, t, language).startsWith("+")).toBe(true);
      const price = comparison.differences.find((difference) => difference.name === "price");
      expect(differenceText(price!, t, language)).toContain("USD");
      expect(comparedValueText(price!, "right", t, language)).toContain("180");
      const html = renderToStaticMarkup(
        <I18nextProvider i18n={instance}>
          <ComputationComparisonView comparison={comparison} t={t} locale={language} />
        </I18nextProvider>,
      );
      expect(html).toContain('data-compared="left"');
      expect(html).toContain('data-compared="right"');
      expect(html).toContain("Apple at 150?");
      expect(html).toContain('data-difference="multiple"');
      expect(html).toContain(language === "en" ? "Differences" : "Diferencias");
      expect(html).not.toContain("—");
    });
  }
});

describe("what a computed answer offers", () => {
  test("compare is always offered and continue only where a new chat can open", async () => {
    const instance = await translate("en");
    const t = instance.t.bind(instance);
    const owner = renderToStaticMarkup(
      <ComputedAnswerActions conversationId="c1" messageId="m1" kind="price_multiple" onOpenConversation={() => undefined} t={t} locale="en" />,
    );
    expect(owner).toContain('data-compute-action="compare"');
    expect(owner).toContain('data-compute-action="continue"');
    const guest = renderToStaticMarkup(
      <ComputedAnswerActions conversationId="c1" messageId="m1" kind="price_multiple" t={t} locale="en" />,
    );
    expect(guest).toContain('data-compute-action="compare"');
    expect(guest).not.toContain('data-compute-action="continue"');
  });

  test("the continued link and cited inputs are read from typed data only", () => {
    expect(continuedFromMetadata({ continued_from: { conversation_id: "c", message_id: "m" } })).toEqual({ conversationId: "c", messageId: "m" });
    expect(continuedFromMetadata({ continued_from: { conversation_id: "c" } })).toBeNull();
    expect(continuedFromMetadata({})).toBeNull();
    expect(hasCitedInputs(fixture.cards.price_multiple.card)).toBe(true);
    expect(hasCitedInputs(fixture.cards.growth_projection.card)).toBe(false);
  });

  for (const language of ["en", "es-419"] as const) {
    test(`the Search dossier offers refresh for cited inputs, compare, and continue for an owner in ${language}`, async () => {
      const instance = await translate(language);
      const owner = renderToStaticMarkup(
        <I18nextProvider i18n={instance}>
          <AnswerDossierView dossier={dossier(fixture.cards.price_multiple.card, "available")} onOpenConversationById={() => undefined} />
        </I18nextProvider>,
      );
      expect(owner).toContain("data-answer-dossier-refresh");
      expect(owner).toContain(instance.t("command_palette.answer_dossier.refresh_note"));
      expect(owner).toContain('data-compute-action="compare"');
      expect(owner).toContain('data-compute-action="continue"');
      const guest = renderToStaticMarkup(
        <I18nextProvider i18n={instance}>
          <AnswerDossierView dossier={dossier(fixture.cards.growth_projection.card, "account_conversion_required")} onOpenConversationById={() => undefined} />
        </I18nextProvider>,
      );
      expect(guest).not.toContain("data-answer-dossier-refresh");
      expect(guest).not.toContain('data-compute-action="continue"');
      expect(guest).toContain('data-compute-action="compare"');
    });
  }
});

describe("the computed-answer client", () => {
  const originalFetch = globalThis.fetch;
  const originalMock = process.env.NEXT_PUBLIC_MOCK_AUTH;
  afterEach(() => {
    globalThis.fetch = originalFetch;
    process.env.NEXT_PUBLIC_MOCK_AUTH = originalMock;
  });

  test("calls the computed-answer routes", async () => {
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    const calls: { url: string; method: string; body: string | null }[] = [];
    globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      calls.push({ url: String(input), method: init?.method ?? "GET", body: typeof init?.body === "string" ? init.body : null });
      return Response.json({ items: [] });
    }) as typeof fetch;
    await listComputedAnswers("price_multiple", "m1");
    await compareComputedAnswers({ conversation_id: "c1", message_id: "m1" }, { conversation_id: "c2", message_id: "m2" });
    await continueComputedAnswer({ conversation_id: "c1", message_id: "m1" });
    await refreshComputedAnswer({ conversation_id: "c1", message_id: "m1" });
    expect(calls.map((call) => [call.method, call.url.replace(/^.*\/api\/v1/, "")])).toEqual([
      ["GET", "/computations/answers?kind=price_multiple&exclude_message_id=m1"],
      ["POST", "/computations/compare"],
      ["POST", "/conversations/c1/messages/m1/continue"],
      ["POST", "/conversations/c1/messages/m1/computation/refresh"],
    ]);
    expect(JSON.parse(calls[1].body ?? "{}")).toEqual({
      left: { conversation_id: "c1", message_id: "m1" },
      right: { conversation_id: "c2", message_id: "m2" },
    });
  });
});
