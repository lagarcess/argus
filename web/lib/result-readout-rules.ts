import type { TFunction } from "i18next";

type ResultRuleSeries = number | {
  kind: "price" | "volume" | "indicator";
  key?: string;
  field?: string;
  period?: number;
  output?: string;
  parameters?: Record<string, number>;
};
type ResultRuleCondition = {
  left: ResultRuleSeries;
  right: ResultRuleSeries;
  operator: "lt" | "lte" | "gt" | "gte" | "cross_above" | "cross_below";
};
export type ResultRuleGroup = {
  side: "entry" | "exit";
  combinator: "all" | "any";
  conditions: ResultRuleCondition[];
};

function record(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

function series(value: unknown): ResultRuleSeries | null {
  if (typeof value === "number") return Number.isFinite(value) ? value : null;
  const source = record(value);
  if (source.kind === "volume") return { kind: "volume" };
  if (source.kind === "price" && ["open", "high", "low", "close"].includes(String(source.field))) {
    return { kind: "price", field: String(source.field) };
  }
  if (source.kind !== "indicator" || typeof source.key !== "string" || !/^[a-z][a-z0-9_]{0,31}$/.test(source.key)) return null;
  return {
    kind: "indicator", key: source.key,
    period: typeof source.period === "number" && Number.isFinite(source.period) ? source.period : undefined,
    output: typeof source.output === "string" && /^[a-z_]{1,24}$/.test(source.output) ? source.output : undefined,
    parameters: Object.fromEntries(Object.entries(record(source.parameters)).filter((entry): entry is [string, number] => ["fast", "slow", "signal", "length", "std"].includes(entry[0]) && typeof entry[1] === "number" && Number.isFinite(entry[1]))),
  };
}

/** Read the canonical rule AST, never its authored/retained description. */
export function resultRuleGroups(value: unknown): ResultRuleGroup[] {
  const spec = record(value);
  const groups: ResultRuleGroup[] = [];
  for (const side of ["entry", "exit"] as const) {
    const group = record(spec[side]);
    if (!Array.isArray(group.conditions) || group.conditions.length === 0) continue;
    if (group.combinator !== undefined && group.combinator !== "all" && group.combinator !== "any") continue;
    const conditions: ResultRuleCondition[] = [];
    for (const value of group.conditions) {
      const condition = record(value);
      const left = series(condition.left);
      const right = series(condition.right);
      const operator = condition.operator;
      if (left === null || right === null || !["lt", "lte", "gt", "gte", "cross_above", "cross_below"].includes(String(operator))) break;
      conditions.push({ left, right, operator: operator as ResultRuleCondition["operator"] });
    }
    // Partial rules would misrepresent what was tested; require the full group.
    if (conditions.length === group.conditions.length) groups.push({ side, combinator: group.combinator === "any" ? "any" : "all", conditions });
  }
  return groups;
}

function seriesText(value: ResultRuleSeries, t: TFunction, locale: string): string {
  const number = (value: number) => new Intl.NumberFormat(locale, { maximumFractionDigits: 2 }).format(value);
  if (typeof value === "number") return number(value);
  if (value.kind === "price") return t(`chat.result_readout.rule_series.${value.field}`);
  if (value.kind === "volume") return t("chat.result_readout.rule_series.volume");
  const parameters = value.parameters;
  const figures = parameters && Object.keys(parameters).length
    ? Object.entries(parameters).map(([key, value]) => `${t(`chat.result_readout.rule_parameters.${key}`)}: ${number(value)}`).join(", ")
    : value.period !== undefined ? number(value.period) : t("chat.result_readout.parameter_unavailable");
  const output = value.output ? t(`chat.result_readout.rule_outputs.${value.output}`, { defaultValue: t("chat.result_readout.rule_outputs.value") }) : "";
  return `${value.key?.toUpperCase()}(${figures})${output ? ` ${output}` : ""}`;
}

export function resultRuleGroupText(group: ResultRuleGroup, t: TFunction, locale: string): string {
  return group.conditions.map((condition) => t(`chat.result_readout.rule_operators.${condition.operator}`, {
    left: seriesText(condition.left, t, locale), right: seriesText(condition.right, t, locale),
  })).join(t(`chat.result_readout.rule_combinators.${group.combinator}`));
}
