import { describe, expect, test } from "bun:test";
import React from "react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";
import ChatMessage from "../components/chat/ChatMessage";
import { hydrateMessagesFromApi } from "../components/chat/chat-message-projection";
import type { Message } from "../components/chat/types";
import type { ApiMessage } from "../lib/argus-api";
import { mergeFinalTextMessage } from "../lib/chat-final-message";
import {
  answerAssumptionsFromMetadata,
  answerAssumptionsText,
  applyToolResultMessage,
  toolCardsFromMetadata,
  toolFactValue,
  type ToolResultCard,
} from "../lib/tool-result-card";
import { translate } from "./support/i18n-instance";

/** Cards and markers come from scripts/dump_calculation_fixtures.py. */
const fixture = JSON.parse(
  readFileSync(join(import.meta.dir, "fixtures/calculation-cards.json"), "utf-8"),
) as { cards: Record<string, { card: ToolResultCard; computation: { kind: string; inputs: Record<string, unknown> } }> };
const growth = fixture.cards.growth_projection;
const loan = fixture.cards.time_value;
const cards = [growth.card, loan.card];
const contribution = { artifact_id: growth.card.artifact_id, name: "contribution" };
const periodsPerYear = { artifact_id: loan.card.artifact_id, name: "periods_per_year" };
const PROSE = "Your savings reach the goal.";

const inputOf = (card: ToolResultCard, name: string) =>
  card.presentation.inputs.find((input) => input.name === name)!;

const lineIn = (html: string) => html.match(/<p data-answer-assumptions[^>]*>([^<]*)<\/p>/)?.[1] ?? null;

function answer(metadata: Record<string, unknown>, answerCards: ToolResultCard[] = cards): ApiMessage {
  return {
    id: "answer-1",
    conversation_id: "c1",
    role: "assistant",
    content: PROSE,
    created_at: "2026-09-13T12:00:00Z",
    metadata: { tool_result_cards: answerCards, ...metadata },
  };
}

async function render(message: Message) {
  const i18n = await translate("en");
  return renderToStaticMarkup(<I18nextProvider i18n={i18n}><ChatMessage message={message} /></I18nextProvider>);
}

describe("assumed inputs listed under a computed answer", () => {
  test("parsing keeps well-formed items and ignores malformed ones", () => {
    expect(answerAssumptionsFromMetadata({ answer_assumptions: [
      contribution, null, "contribution", [contribution], { artifact_id: 7, name: "contribution" },
      { artifact_id: growth.card.artifact_id }, { artifact_id: "", name: "contribution" },
      { artifact_id: loan.card.artifact_id, name: "" }, { ...periodsPerYear, source: "assumption" },
    ] })).toEqual([contribution, periodsPerYear]);
    expect(answerAssumptionsFromMetadata({})).toBeNull();
    expect(answerAssumptionsFromMetadata({ answer_assumptions: [] })).toBeNull();
    expect(answerAssumptionsFromMetadata({ answer_assumptions: contribution })).toBeNull();
    expect(answerAssumptionsFromMetadata({ answer_assumptions: [null, { name: "contribution" }] })).toBeNull();
  });

  for (const language of ["en", "es-419"] as const) {
    test(`one line names two inputs across two cards in ${language}`, async () => {
      const i18n = await translate(language);
      const t = i18n.t.bind(i18n);
      const money = toolFactValue(inputOf(growth.card, "contribution"), t, language);
      const line = answerAssumptionsText({ toolResultCards: cards, answerAssumptions: [contribution, periodsPerYear] }, t, language);
      expect(line).toBe(language === "en"
        ? `Assumed for this calculation: contribution per period ${money} and periods per year 12.`
        : `Supuestos de este cálculo: aporte por período ${money} y períodos por año 12.`);
      expect(line).not.toContain("\u2014");
    });
  }

  test("an item whose card, input or value is missing is skipped, and none resolved is no line", async () => {
    const i18n = await translate("en");
    const t = i18n.t.bind(i18n);
    const unresolved = [
      { artifact_id: "artifact-missing", name: "contribution" },
      { artifact_id: loan.card.artifact_id, name: "undeclared" },
      { artifact_id: loan.card.artifact_id, name: "payment" },
    ];
    expect(inputOf(loan.card, "payment").value).toBeNull();
    expect(answerAssumptionsText({ toolResultCards: cards, answerAssumptions: [...unresolved, periodsPerYear] }, t, "en"))
      .toBe("Assumed for this calculation: periods per year 12.");
    expect(answerAssumptionsText({ toolResultCards: cards, answerAssumptions: unresolved }, t, "en")).toBe("");
    const [message] = hydrateMessagesFromApi([answer({ answer_assumptions: unresolved })]).messages;
    expect(lineIn(await render(message))).toBeNull();
  });

  test("reload projects the list, and the line renders between the prose and the cards", async () => {
    const marker = { calculations: [growth.computation, loan.computation].map(({ kind, inputs }) => ({ kind, inputs })) };
    const [computed] = hydrateMessagesFromApi([answer({ computation: marker, answer_assumptions: [contribution, periodsPerYear] })]).messages;
    expect(computed.computation).toBeTruthy();
    expect(computed.answerAssumptions).toEqual([contribution, periodsPerYear]);

    const [message] = hydrateMessagesFromApi([answer({ answer_assumptions: [contribution, periodsPerYear] })]).messages;
    const html = await render(message);
    expect(lineIn(html)).toStartWith("Assumed for this calculation: contribution per period ");
    expect(html).toContain(PROSE);
    expect(html).toContain("data-tool-answer");
    const line = html.indexOf("data-answer-assumptions");
    expect(line).toBeGreaterThan(html.indexOf(PROSE));
    expect(line).toBeLessThan(html.indexOf("data-tool-answer"));

    const [plain] = hydrateMessagesFromApi([answer({})]).messages;
    expect(plain.answerAssumptions).toBeUndefined();
    expect(lineIn(await render(plain))).toBeNull();
  });

  test("the live final carries the list into the answer message", async () => {
    const finalPayload: Record<string, unknown> = { assistant_response: PROSE, tool_result_cards: cards, answer_assumptions: [contribution, periodsPerYear] };
    const message = mergeFinalTextMessage(
      { id: "assistant-1", role: "ai", kind: "text", content: "" },
      {
        assistantId: "assistant-1", finalText: PROSE, finalActions: [],
        toolResultCards: toolCardsFromMetadata(finalPayload),
        answerAssumptions: answerAssumptionsFromMetadata(finalPayload),
      },
    );
    expect(message.answerAssumptions).toEqual([contribution, periodsPerYear]);
    expect(lineIn(await render(message))).toStartWith("Assumed for this calculation: ");

    const chat = readFileSync(join(import.meta.dir, "..", "components/chat/ChatInterface.tsx"), "utf-8");
    expect(chat).toContain("const finalAnswerAssumptions = answerAssumptionsFromMetadata(finalPayload);");
    const textFinal = chat.slice(
      chat.indexOf("} else if (finalText || finalToolCards.length || finalToolCardsUnavailable || finalToolJobs.length) {"),
      chat.indexOf("terminalReadiness.accept(event.data, identityAuthorized)"),
    );
    expect(textFinal.split("answerAssumptions: finalAnswerAssumptions,")).toHaveLength(3);
  });

  test("a recompute response with a changed list updates the line", async () => {
    const messages = hydrateMessagesFromApi([answer({ answer_assumptions: [contribution, periodsPerYear] })]).messages;
    const revised: ToolResultCard = {
      ...loan.card,
      input_revision: loan.card.input_revision + 1,
      presentation: { ...loan.card.presentation, inputs: loan.card.presentation.inputs.map((input) =>
        input.name === "periods_per_year" ? { ...input, value: 4 } : input) },
    };
    const sooner = "Your savings reach the goal sooner.";
    const recomputed = applyToolResultMessage(messages, {
      ...answer({ answer_assumptions: [periodsPerYear] }, [growth.card, revised]),
      content: sooner,
    });
    expect(lineIn(await render(recomputed[0]))).toBe("Assumed for this calculation: periods per year 4.");
    expect(recomputed[0].content).toBe(sooner);

    const stale = applyToolResultMessage(recomputed, answer({ answer_assumptions: [contribution] }));
    expect(stale[0].answerAssumptions).toEqual([periodsPerYear]);
    expect(stale[0].content).toBe(sooner);

    const emptied = applyToolResultMessage(recomputed, answer({ answer_assumptions: [] }, [growth.card, { ...revised, input_revision: revised.input_revision + 1 }]));
    expect(emptied[0].answerAssumptions).toBeNull();
    expect(lineIn(await render(emptied[0]))).toBeNull();
  });
});
