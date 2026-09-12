import { describe, expect, test } from "bun:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import ComputedRerunPanel from "../components/chat/ComputedRerunPanel";
import DecisionRerunView from "../components/chat/DecisionRerunView";
import { CurrentDecisionChip } from "../components/chat/DecisionAffordance";
import { AnswerDossierView } from "../components/sidebar/command-palette/AnswerDossierView";
import { changesAreEmpty, rerunCard, rerunChanges } from "../lib/computed-rerun";
import { decisionRerunTreatment } from "../lib/tool-outcome-treatment";
import type { AnswerDossier } from "../lib/answer-dossier-contract";
import type { ToolResultCard } from "../lib/tool-result-card";
import { translate } from "./support/i18n-instance";

const fixture = JSON.parse(
  readFileSync(join(import.meta.dir, "fixtures/calculation-cards.json"), "utf-8"),
) as { cards: Record<string, { card: ToolResultCard }> };
const stored = fixture.cards.time_value.card;
const latest = { ...stored, arguments: { ...stored.arguments, present_value: 150000 } };

function dossier(overrides: Partial<AnswerDossier> = {}): AnswerDossier {
  return {
    message_id: "m1",
    conversation_id: "c1",
    asked: "What would a 200,000 loan cost a month?",
    computed_at: "2026-09-11T12:00:00Z",
    kind: "time_value",
    symbols: [],
    card: stored,
    decision: null,
    decision_id: null,
    actions: [{ type: "answer_decision", availability: "available", message_id: "m1", decision_state: null, note: null }],
    ...overrides,
  };
}

describe("a computed re-run beside its stored result", () => {
  test("helpers read the card from a computed re-run and detect an unchanged edit", () => {
    expect(rerunCard({ kind: "time_value", inputs: {}, status: "computed", result: stored, retest: null, reason_code: null })).toEqual(stored);
    expect(rerunCard({ kind: "time_value", inputs: {}, status: "unavailable", result: null, retest: null, reason_code: "invalid_inputs" })).toBeNull();
    expect(rerunChanges(stored, { present_value: "200000" })).toEqual({});
    expect(changesAreEmpty(rerunChanges(stored, { present_value: "200000" }))).toBe(true);
    expect(rerunChanges(stored, { present_value: "150000" })).toEqual({ present_value: 150000 });
    expect(rerunChanges(stored, { payment: "1" })).toBeNull();
  });

  for (const language of ["en", "es-419"] as const) {
    test(`the panel renders the stored result, today's, and an editable input in ${language}`, async () => {
      const instance = await translate(language);
      const html = renderToStaticMarkup(
        <I18nextProvider i18n={instance}>
          <ComputedRerunPanel stored={stored} latest={latest} busy={false} unavailable={null} transportError={null} onRerun={() => undefined}
            t={instance.t.bind(instance)} locale={language} labels={{ stored: instance.t("tools.decision.stored"), latest: instance.t("tools.decision.today") }} />
        </I18nextProvider>,
      );
      expect(html).toContain('data-computed-rerun="stored"');
      expect(html).toContain('data-computed-rerun="latest"');
      expect(html).toContain(language === "en" ? "Saved result" : "Resultado guardado");
      expect(html).toContain(language === "en" ? "Today&#x27;s result" : "Resultado de hoy");
      expect(html).toContain('<input id="rerun-artifact-time_value-present_value"');
      expect(html.match(/data-tool-answer/g)?.length).toBe(2);
      expect(html).not.toMatch(/tools\.(calc|card|decision)\./);
    });
  }

  test("a decision that cannot re-run shows the reason quietly and locks the inputs", async () => {
    const instance = await translate("en");
    const html = renderToStaticMarkup(
      <I18nextProvider i18n={instance}>
        <ComputedRerunPanel stored={stored} latest={null} busy={false} unavailable={decisionRerunTreatment("invalid_inputs", instance.t.bind(instance))} transportError={null} onRerun={() => undefined}
          t={instance.t.bind(instance)} locale="en" labels={{ stored: "Saved result", latest: "Today's result" }} />
      </I18nextProvider>,
    );
    expect(html).toContain('data-testid="computed-rerun-unavailable"');
    expect(html).toContain("The saved inputs no longer fit this calculation.");
    expect(html).not.toContain('<input id="rerun-');
  });

  test("a saved decision chip opens the decision, and the view starts by opening it", async () => {
    const instance = await translate("en");
    const chip = renderToStaticMarkup(
      <I18nextProvider i18n={instance}><CurrentDecisionChip state="watching" onOpen={() => undefined} /></I18nextProvider>,
    );
    expect(chip).toContain('data-testid="open-decision"');
    expect(chip).toContain('aria-expanded="false"');
    const plain = renderToStaticMarkup(
      <I18nextProvider i18n={instance}><CurrentDecisionChip state="watching" /></I18nextProvider>,
    );
    expect(plain).not.toContain("<button");
    const view = renderToStaticMarkup(
      <I18nextProvider i18n={instance}><DecisionRerunView decisionId="d1" /></I18nextProvider>,
    );
    expect(view).toContain("Opening the decision...");
  });

  for (const language of ["en", "es-419"] as const) {
    test(`the Search dossier shows what was asked, what was used with its sources, what came out and the decision in ${language}`, async () => {
      const instance = await translate(language);
      const undecided = renderToStaticMarkup(
        <I18nextProvider i18n={instance}><AnswerDossierView dossier={dossier()} onOpenConversation={() => undefined} /></I18nextProvider>,
      );
      expect(undecided).toContain('data-answer-dossier="time_value"');
      expect(undecided).toContain(language === "en" ? "You asked" : "Preguntaste");
      expect(undecided).toContain("What would a 200,000 loan cost a month?");
      expect(undecided).toContain(language === "en" ? "Saved answer" : "Respuesta guardada");
      expect(undecided).toContain("data-tool-input-provenance");
      expect(undecided).toContain('data-tool-input-source="page"');
      expect(undecided).toContain(language === "en" ? "Add decision" : "Agregar decisión");
      expect(undecided).toContain('<input id="rerun-artifact-time_value-present_value"');
      expect(undecided).not.toMatch(/(tools|command_palette)\.[a-z_]+\.[a-z_.]+/);
      const decided = renderToStaticMarkup(
        <I18nextProvider i18n={instance}>
          <AnswerDossierView dossier={dossier({ decision: { state: "watching", note: "Wait for the rate sheet." }, decision_id: "d1",
            actions: [{ type: "answer_decision", availability: "available", message_id: "m1", decision_state: "watching", note: "Wait for the rate sheet." }] })} />
        </I18nextProvider>,
      );
      expect(decided).toContain("Wait for the rate sheet.");
      expect(decided).toContain(instance.t("chat.result_card.decision_states.watching"));
      const guest = renderToStaticMarkup(
        <I18nextProvider i18n={instance}>
          <AnswerDossierView dossier={dossier({ actions: [{ type: "answer_decision", availability: "account_conversion_required", message_id: "m1", decision_state: null, note: null }] })} />
        </I18nextProvider>,
      );
      expect(guest).not.toContain(language === "en" ? "Add decision" : "Agregar decisión");
      expect(guest).toContain(language === "en" ? "No decision saved" : instance.t("command_palette.no_decision_saved"));
    });
  }
});
