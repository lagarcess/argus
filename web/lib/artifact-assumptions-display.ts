import type { TFunction } from "i18next";
import type { AssetClass } from "./argus-types";
import { assetClassDisplayLabel } from "./asset-class-display";
import { confirmationDisplayFacts, type ConfirmationDisplayFacts } from "./confirmation-assumptions-display";

export type ArtifactAssumptionsFacts = {
  artifact_kind: "confirmation" | "current_idea";
  asset_class?: AssetClass;
  display_facts: ConfirmationDisplayFacts;
};

const displayFactKeys = [
  "capital", "starting_capital", "recurring_contribution", "contribution_period",
  "benchmark_symbol", "data_through", "fees", "slippage", "timeframe",
] as const;

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? value as Record<string, unknown> : null;
}

export function artifactAssumptionsFacts(value: unknown): ArtifactAssumptionsFacts {
  const facts = record(value);
  const display = record(facts?.display_facts);
  const display_facts: Record<string, string | number | null> = {};
  for (const key of displayFactKeys) {
    const entry = display?.[key];
    if (typeof entry === "string" || (typeof entry === "number" && Number.isFinite(entry))) {
      display_facts[key] = entry;
    }
  }
  const assetClass = facts?.asset_class;
  return {
    artifact_kind: facts?.artifact_kind === "current_idea" ? "current_idea" : "confirmation",
    ...(assetClass === "equity" || assetClass === "crypto" || assetClass === "currency_pair"
      ? { asset_class: assetClass } : {}),
    display_facts: display_facts as ConfirmationDisplayFacts,
  };
}

export function artifactAssumptionsText(facts: ArtifactAssumptionsFacts, t: TFunction, locale: string): string {
  const values = confirmationDisplayFacts(facts.display_facts, locale, t, { includeMoney: true });
  const assetClass = assetClassDisplayLabel(facts.asset_class, t);
  if (assetClass) values.unshift(assetClass);
  if (values.length === 0) return t("chat.artifact_assumptions.unavailable");
  return t(`chat.artifact_assumptions.${facts.artifact_kind}`, { assumptions: values.join("; ") });
}
