import type { TFunction } from "i18next";

import {
  retestEffectiveDurationLabel,
  retestPeriodTransformationLabel,
} from "@/lib/chat-retest";
import type { ConfirmationCardViewModel } from "@/lib/confirmation-card-view-model";
import type { ResultCardViewModel } from "@/lib/result-card-view-model";

const ASSUMPTION_SEPARATOR = " • ";

/** Copy serializes the card's own view model, never the payload the card was
 * built from, so the clipboard reads in the workspace language the card does. */
export function confirmationCardCopyText(
  view: ConfirmationCardViewModel,
  t: TFunction,
  locale: string,
): string {
  return joinCopyLines([
    view.strategyLabel,
    labelledLine(copyHeadings(t).assets, view.assetSymbols.join(", ")),
    ...[...view.summaryRows, ...view.detailRows].map((row) =>
      labelledLine(row.label, row.value),
    ),
    ...retestPeriodLines(view.retestPeriod, t, locale),
    labelledLine(
      copyHeadings(t).assumptions,
      view.assumptions.join(ASSUMPTION_SEPARATOR),
    ),
  ]);
}

export function resultCardCopyText(
  view: ResultCardViewModel,
  t: TFunction,
  explanation?: string | null,
): string {
  const headings = copyHeadings(t);
  const { evidence } = view;
  const period = evidence.timeframeDisplay
    ? `${view.periodDisplay} · ${evidence.timeframeDisplay}`
    : view.periodDisplay;
  return joinCopyLines([
    view.strategyLabel,
    labelledLine(headings.assets, view.symbols.join(", ")),
    labelledLine(headings.period, period),
    view.statusLabel,
    labelledLine(evidence.hero.label, evidence.hero.value),
    evidence.hero.detail,
    labelledLine(evidence.benchmark.label, evidence.benchmark.value),
    labelledLine(evidence.worstDrop.label, evidence.worstDrop.value),
    ...evidence.details.map((detail) => labelledLine(detail.label, detail.value)),
    ...evidence.trustGroups,
    explanation?.trim()
      ? `${headings.assistantExplanation}:\n${explanation.trim()}`
      : null,
  ]);
}

function copyHeadings(t: TFunction) {
  return {
    assets: t("chat.copy_card.assets", "Assets"),
    period: t("chat.copy_card.period", "Period"),
    assumptions: t("chat.copy_card.assumptions", "Assumptions"),
    assistantExplanation: t(
      "chat.copy_card.assistant_explanation",
      "Assistant explanation",
    ),
  };
}

function retestPeriodLines(
  period: ConfirmationCardViewModel["retestPeriod"],
  t: TFunction,
  locale: string,
): string[] {
  if (!period) {
    return [];
  }
  return [
    retestPeriodTransformationLabel(period, locale),
    t("chat.retest.updated_duration", {
      defaultValue: "Updated span: {{duration}}",
      duration: retestEffectiveDurationLabel(period.duration, t, locale),
    }),
  ];
}

function labelledLine(label: string, value: string): string | null {
  return value.trim() ? `${label}: ${value}` : null;
}

function joinCopyLines(lines: (string | null | undefined)[]): string {
  return lines.filter((line): line is string => Boolean(line?.trim())).join("\n");
}
