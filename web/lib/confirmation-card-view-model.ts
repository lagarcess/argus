import type { TFunction } from "i18next";

import { splitSymbolList } from "@/components/chat/card-formatting";
import {
  confirmationRowKey,
  confirmationRowLabelKey,
} from "@/components/chat/confirmation-display";
import type {
  StrategyConfirmationPayload,
  StrategyConfirmationRow,
  StrategyConfirmationRowKey,
} from "@/components/chat/types";
import { retestPeriodFromValue, type RetestPeriod } from "@/lib/chat-retest";
import { confirmationAssumptionDisplay } from "@/lib/confirmation-assumptions-display";
import { contributionPhrase } from "@/lib/contribution-period-display";
import { compactDateRangeDisplay } from "@/lib/date-range-display";
import { formatCurrency } from "@/lib/result-card-display";
import {
  strategyDisplayLabel,
  strategyTypeFromConfirmation,
} from "@/lib/strategy-display";

/** A confirmation row after localization: the label and value the card paints,
 * so the render and the clipboard read one source instead of two. */
export type ConfirmationCardRow = {
  key: StrategyConfirmationRowKey | null;
  label: string;
  value: string;
  /** Untruncated period text, shown as the compact value's tooltip. */
  fullValue?: string;
};

export type ConfirmationCardViewModel = {
  assetSymbols: string[];
  strategyLabel: string | null;
  summaryRows: ConfirmationCardRow[];
  detailRows: ConfirmationCardRow[];
  assumptions: string[];
  retestPeriod: RetestPeriod | null;
};

export function confirmationCardViewModel(
  confirmation: StrategyConfirmationPayload,
  t: TFunction,
  language: string,
): ConfirmationCardViewModel {
  const rows = confirmation.rows.map((row) =>
    localizedConfirmationRow(row, confirmation, t, language),
  );
  const assetRow = rowForKey(rows, "assets");
  const strategyRow = rowForKey(rows, "strategy");
  const periodRow = rowForKey(rows, "period");
  const startingCapitalRow = rowForKey(rows, "starting_capital");
  const contributionRow = rowForKey(rows, "contribution");
  const assetSymbols = splitSymbolList(assetRow?.value ?? "");
  // A recurring plan's headline money is what goes in every period; its
  // starting capital, usually $0, reads as a detail beneath.
  const primaryCapitalRow = contributionRow ?? startingCapitalRow;
  const compactPeriod = compactDateRangeDisplay(confirmation.date_range, language);
  const displayPeriodRow =
    periodRow && compactPeriod
      ? {
          ...periodRow,
          value: compactPeriod,
          fullValue: confirmation.date_range?.display ?? periodRow.value,
        }
      : periodRow;
  const summaryRows = [primaryCapitalRow, displayPeriodRow].filter(isConfirmationRow);
  const promotedKeys = new Set<StrategyConfirmationRowKey>([
    "assets",
    "strategy",
    ...summaryRows.map((row) => row.key).filter(isConfirmationRowKey),
  ]);
  if (primaryCapitalRow === contributionRow) {
    promotedKeys.add("contribution");
  }
  const summaryRowSet = new Set(summaryRows);
  const detailRows = rows.filter(
    (row) =>
      !summaryRowSet.has(row) && (row.key === null || !promotedKeys.has(row.key)),
  );
  const localizedStrategyLabel = strategyDisplayLabel(
    strategyTypeFromConfirmation(confirmation),
    t,
    strategyRow?.value,
  );

  return {
    assetSymbols,
    strategyLabel:
      localizedStrategyLabel ??
      confirmationAssetTitle(assetSymbols, confirmation.title, t),
    summaryRows,
    detailRows,
    assumptions: confirmationAssumptionDisplay({
      assetClass: confirmation.asset_class,
      displayFacts: confirmation.display_facts,
      locale: language,
      t,
    }),
    retestPeriod: retestPeriodFromValue(confirmation.retest_period),
  };
}

/** Money rows are composed from typed facts, so the amount carries the
 * viewer's separators and the period reads in the viewer's language. Row
 * strings stay the fallback for cards persisted before the facts existed. */
function localizedConfirmationRow(
  row: StrategyConfirmationRow,
  confirmation: StrategyConfirmationPayload,
  t: TFunction,
  language: string,
): ConfirmationCardRow {
  const key = confirmationRowKey(row);
  const labelKey = confirmationRowLabelKey(row);
  const facts = confirmation.display_facts;
  let value = row.value;
  if (key === "contribution" && typeof facts?.recurring_contribution === "number") {
    value = contributionPhrase(
      formatCurrency(facts.recurring_contribution, language),
      facts.contribution_period,
      t,
    );
  } else if (
    key === "starting_capital" &&
    typeof facts?.starting_capital === "number"
  ) {
    value = formatCurrency(facts.starting_capital, language);
  }
  return {
    key,
    label: labelKey ? t(labelKey, row.label) : row.label,
    value,
  };
}

function isConfirmationRow(
  row: ConfirmationCardRow | undefined,
): row is ConfirmationCardRow {
  return Boolean(row);
}

function isConfirmationRowKey(
  key: StrategyConfirmationRowKey | null,
): key is StrategyConfirmationRowKey {
  return key !== null;
}

function rowForKey(rows: ConfirmationCardRow[], key: StrategyConfirmationRowKey) {
  return rows.find((row) => row.key === key);
}

function confirmationAssetTitle(
  assetSymbols: string[],
  fallbackTitle: string,
  t: TFunction,
) {
  if (assetSymbols.length === 1 || assetSymbols.length === 2) {
    return null;
  }
  if (assetSymbols.length > 2) {
    return t("chat.confirmation.asset_count", "{{count}} assets", {
      count: assetSymbols.length,
    });
  }
  return fallbackTitle.trim() || t("chat.confirmation.selected_asset", "Selected asset");
}
