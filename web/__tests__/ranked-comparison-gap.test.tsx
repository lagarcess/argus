import { describe, expect, test } from "bun:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ComputationComparisonView } from "../components/chat/ComputationCompare";
import ToolCardPresentation from "../components/chat/ToolCardPresentation";
import type { ComputationComparison } from "../lib/computation-contract";
import { differenceText } from "../lib/computation-compare";
import { localizedToolText, parseToolResultCard, shownToolRows, toolCardCopyText } from "../lib/tool-result-card";
import { translate } from "./support/i18n-instance";

const fixture = JSON.parse(readFileSync(join(import.meta.dir, "fixtures/calculation-cards.json"), "utf-8"));
const comparison: ComputationComparison = fixture.ranked_comparison;

describe("a ranked leader's comparison-only gap", () => {
  for (const language of ["en", "es-419"] as const) {
    test(`both changed leaders' gaps compare without extra card rows in ${language}`, async () => {
      const instance = await translate(language);
      const t = instance.t.bind(instance);
      const gaps = comparison.differences.filter((fact) => fact.name.startsWith("gap_"));
      expect(gaps).toHaveLength(2);
      const html = renderToStaticMarkup(<ComputationComparisonView comparison={comparison} t={t} locale={language} />);
      for (const gap of gaps) {
        expect(html).toContain(`data-difference="${gap.name}"`);
        expect(html).toContain(localizedToolText(gap.label, t));
        expect(html).toContain(differenceText(gap, t, language));
      }
      expect(html).toContain(language === "en" ? "Differences" : "Diferencias");
      for (const answer of [comparison.left, comparison.right]) {
        const card = parseToolResultCard(answer.card)!;
        expect(card).not.toBeNull();
        const leaderGap = card.presentation.rows.find((row) => row.name === "gap_0")!;
        expect(leaderGap.value).toBe(0);
        expect(leaderGap.comparison_only).toBe(true);
        const rendered = renderToStaticMarkup(<ToolCardPresentation presentation={card.presentation} t={t} locale={language} />);
        const copied = toolCardCopyText(card, t, language);
        const label = localizedToolText(leaderGap.label, t);
        expect(rendered).not.toContain(label);
        expect(copied).not.toContain(label);
        for (const row of shownToolRows(card.presentation)) {
          expect(rendered).toContain(localizedToolText(row.label, t));
          expect(copied).toContain(localizedToolText(row.label, t));
        }
      }
    });
  }

  test("older rows stay visible and malformed comparison markers are refused", () => {
    const card = structuredClone(parseToolResultCard(comparison.left.card)!);
    for (const row of card.presentation.rows) delete row.comparison_only;
    expect(parseToolResultCard(card)).not.toBeNull();
    expect(shownToolRows(card.presentation)).toEqual(card.presentation.rows);
    const malformed = { ...card, presentation: { ...card.presentation, rows: [{ ...card.presentation.rows[0], comparison_only: "true" }] } };
    expect(parseToolResultCard(malformed)).toBeNull();
  });
});
