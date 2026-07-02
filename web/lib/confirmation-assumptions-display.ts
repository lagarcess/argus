import type { TFunction } from "i18next";
import type { AssetClass } from "@/lib/argus-types";
import { assetClassDisplayLabel } from "@/lib/asset-class-display";
import { compactDateDisplay } from "@/lib/date-range-display";
import {
  defaultResultCardDisplayCopy,
  formatTimeframeForDisplay,
} from "@/lib/result-card-display";

export type ConfirmationDisplayFacts = {
  benchmark_symbol?: string | null;
  data_through?: string | null;
  fees?: number | string | null;
  slippage?: number | string | null;
  timeframe?: string | null;
};

type Translate = TFunction;

export function confirmationAssumptionDisplay({
  assetClass,
  displayFacts,
  fallbackAssumptions,
  locale,
  promotedValues,
  t,
}: {
  assetClass?: AssetClass | null;
  displayFacts?: ConfirmationDisplayFacts | null;
  fallbackAssumptions: string[];
  locale: string;
  promotedValues: string[];
  t: Translate;
}) {
  const assetClassLabel = assetClassDisplayLabel(assetClass, t as TFunction);
  const canonicalFacts = displayFacts
    ? confirmationDisplayFacts(displayFacts, locale, t)
    : [];
  if (canonicalFacts.length > 0) {
    return prependAssetClass(canonicalFacts, assetClassLabel);
  }
  return prependAssetClass(
    fallbackAssumptions.filter(
      (assumption) =>
        !promotedValues.some(
          (value) => value.trim() && assumption.includes(value.trim()),
        ),
    ),
    assetClassLabel,
  );
}

function confirmationDisplayFacts(
  facts: ConfirmationDisplayFacts,
  locale: string,
  t: Translate,
) {
  const display: string[] = [];
  const timeframe = formatConfirmationTimeframe(facts.timeframe, t);
  if (timeframe) {
    display.push(timeframe);
  }
  const dataThrough = compactDateDisplay(facts.data_through, locale, {
    year: false,
  });
  if (dataThrough) {
    display.push(
      t("chat.confirmation.assumptions.through", {
        date: dataThrough,
        defaultValue: "Through {{date}}",
      }),
    );
  }
  const modeledCosts = modeledCostDisplay(facts, t);
  if (modeledCosts) {
    display.push(modeledCosts);
  } else {
    if (isZeroLike(facts.fees)) {
      display.push(t("chat.confirmation.assumptions.no_fees", "No fees"));
    }
    if (isZeroLike(facts.slippage)) {
      display.push(t("chat.confirmation.assumptions.no_slippage", "No slippage"));
    }
  }
  const benchmarkSymbol = facts.benchmark_symbol?.trim();
  if (benchmarkSymbol) {
    display.push(
      t("chat.confirmation.assumptions.benchmark", {
        defaultValue: "Benchmark: {{symbol}}",
        symbol: benchmarkSymbol.toUpperCase(),
      }),
    );
  }
  return display;
}

function formatConfirmationTimeframe(timeframe: string | null | undefined, t: Translate) {
  return formatTimeframeForDisplay(timeframe ?? undefined, {
    ...defaultResultCardDisplayCopy,
    dailyData: t("chat.result_card.timeframe.daily", "Daily data"),
    hourlyData: t("chat.result_card.timeframe.hourly", "Hourly data"),
    intervalData: (amount, unit) =>
      t("chat.result_card.timeframe.interval", {
        amount,
        defaultValue: "{{amount}}-{{unit}} data",
        unit,
      }),
    timeframeData: (value) =>
      t("chat.result_card.timeframe.generic", {
        defaultValue: "{{value}} data",
        value,
      }),
  });
}

function isZeroLike(value: number | string | null | undefined) {
  if (typeof value === "number") {
    return Number.isFinite(value) && value === 0;
  }
  if (typeof value !== "string" || value.trim() === "") {
    return false;
  }
  return Number(value) === 0;
}

function modeledCostDisplay(facts: ConfirmationDisplayFacts, t: Translate) {
  const fees = numericValue(facts.fees);
  const slippage = numericValue(facts.slippage);
  if ((fees ?? 0) <= 0 && (slippage ?? 0) <= 0) {
    return null;
  }
  const feeBps = formatBps((fees ?? 0) * 10000);
  const slippageBps = formatBps((slippage ?? 0) * 10000);
  return t("chat.confirmation.assumptions.modeled_costs", {
    defaultValue: "Modeled costs: {{fee}} bps fee + {{slippage}} bps slippage",
    fee: feeBps,
    slippage: slippageBps,
  });
}

function numericValue(value: number | string | null | undefined) {
  if (typeof value === "number") {
    return Number.isFinite(value) ? value : null;
  }
  if (typeof value !== "string" || value.trim() === "") {
    return null;
  }
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
}

function formatBps(value: number) {
  const rounded = Math.round(value * 100) / 100;
  return Number.isInteger(rounded) ? String(rounded) : String(rounded);
}

function prependAssetClass(items: string[], assetClassLabel: string | undefined) {
  if (!assetClassLabel || items.includes(assetClassLabel)) {
    return items;
  }
  return [assetClassLabel, ...items];
}
