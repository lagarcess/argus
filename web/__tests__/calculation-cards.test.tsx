import { describe, expect, test } from "bun:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import ToolResultCard from "../components/chat/ToolResultCard";
import { parseToolResultCard, toolFactSourceText, type ToolResultCard as Card } from "../lib/tool-result-card";
import { toolOutcomeTreatment } from "../lib/tool-outcome-treatment";
import { translate } from "./support/i18n-instance";

/** Every card here came out of the real declarations; nothing is hand-written. */
const fixture = JSON.parse(
  readFileSync(join(import.meta.dir, "fixtures/calculation-cards.json"), "utf-8"),
) as { cards: Record<string, { card: Card; computation: { kind: string } | null }> };

const RAW_KEY = /tools\.(calc|card)\.[a-z_.]+/;

describe("declaration-generated calculation cards", () => {
  for (const language of ["en", "es-419"] as const) {
    test(`every declared card renders in ${language} with no unresolved locale key`, async () => {
      const instance = await translate(language);
      for (const [name, { card, computation }] of Object.entries(fixture.cards)) {
        expect(parseToolResultCard(card)).not.toBeNull();
        const html = renderToStaticMarkup(
          <I18nextProvider i18n={instance}><ToolResultCard card={card} onRecompute={async () => undefined} /></I18nextProvider>,
        );
        expect(html, name).not.toMatch(RAW_KEY);
        expect(html, name).not.toContain("—");
        if (card.outcome.status === "succeeded") {
          expect(html, name).toContain("data-tool-answer");
          expect(computation?.kind).toBe(card.tool_name);
        } else {
          expect(html, name).toContain('data-tool-outcome-tone=');
        }
      }
    });
  }

  test("every input shows where it came from: stated, a dated page, or computed", async () => {
    const instance = await translate("en");
    const t = instance.t.bind(instance);
    const { card } = fixture.cards.time_value;
    const inputs = Object.fromEntries(card.presentation.inputs.map((input) => [input.name, input]));
    expect(toolFactSourceText(inputs.present_value, t, "en")).toBe("You said it");
    expect(toolFactSourceText(inputs.annual_rate_pct, t, "en")).toBe("Rate sheet, Sep 1, 2026");
    expect(toolFactSourceText(inputs.payment, t, "en")).toBe("Computed from the other inputs");
    expect(card.presentation.answer?.source?.kind).toBe("computed");
    const html = renderToStaticMarkup(
      <I18nextProvider i18n={instance}><ToolResultCard card={card} defaultOpen /></I18nextProvider>,
    );
    expect(html).toContain('data-tool-input-source="page"');
    expect(html).toContain("Rate sheet, Sep 1, 2026");
    expect(html).toContain("data-tool-visual");
  });

  test("a no-solution card names the field, offers the typed repair, and keeps its inputs typeable", async () => {
    const instance = await translate("en");
    const { card } = fixture.cards.time_value_payment_below_interest;
    const treatment = toolOutcomeTreatment(card.outcome, instance.t.bind(instance), (name) => `<${name}>`);
    expect(treatment?.tone).toBe("quiet");
    expect(treatment?.message).toBe("The <payment> is below the interest each period, so the balance never falls.");
    expect(treatment?.repair?.changes.payment).toBeGreaterThan(2100);
    const html = renderToStaticMarkup(
      <I18nextProvider i18n={instance}><ToolResultCard card={card} onRecompute={async () => undefined} /></I18nextProvider>,
    );
    expect(html).toContain('data-tool-outcome-code="payment_below_interest"');
    expect(html).toContain('data-tool-repair="set_inputs"');
    expect(html).toMatch(/data-tool-repair="set_inputs"[^>]*class="max-w-full /);
    expect(html).toContain("Use a payment that clears the balance");
    expect(html).toContain('<input id="artifact-time_value-payment"');
    expect(html).not.toContain("data-tool-answer");
  });

  test("an unavailable calculation offers no retry, since the same inputs compute the same way", async () => {
    const instance = await translate("en");
    const { card } = fixture.cards.time_value;
    const unavailable = { ...card, outcome: { status: "unavailable", result: null, failure: { code: "tool_execution_failed", fields: [] } } } as Card;
    const html = renderToStaticMarkup(
      <I18nextProvider i18n={instance}><ToolResultCard card={unavailable} onRecompute={async () => undefined} /></I18nextProvider>,
    );
    expect(html).toContain('data-tool-outcome-tone="retryable"');
    expect(html).not.toContain("data-tool-retry");
  });

  test("the Spanish card copy carries no English fallbacks", async () => {
    const instance = await translate("es-419");
    const { card } = fixture.cards.time_value_payment_below_interest;
    const html = renderToStaticMarkup(
      <I18nextProvider i18n={instance}><ToolResultCard card={card} onRecompute={async () => undefined} /></I18nextProvider>,
    );
    expect(html).toContain("Usar un pago que sí amortice el saldo");
    expect(html).toContain("Préstamo");
    expect(html).not.toContain("Use a payment");
  });
});
