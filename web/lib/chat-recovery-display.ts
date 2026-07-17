import type { TFunction } from "i18next";
import type { ChatActionOption } from "@/components/chat/types";

export type RecoveryDisplay =
  | {
      kind: "recovery_code";
      code: string;
      values?: Record<string, string>;
    }
  | {
      kind: "coverage_recovery";
      code: string;
    }
  | {
      kind: "unsupported_recovery";
      values: {
        rawValue?: string;
        symbol?: string;
        options: Array<{
          label?: string;
          replacementValues?: Record<string, unknown> | null;
        }>;
      };
    }
  | {
      kind: "clarification";
      reasonCode?: string;
      requestedField?: string;
      semanticNeeds: string[];
      values?: Record<string, string>;
    }
  | {
      kind: "artifact_action_recovery";
      status: string;
      values?: Record<string, string>;
    };

function recordOrNull(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function stringArrayOrNull(value: unknown): string[] | null {
  if (!Array.isArray(value)) {
    return null;
  }
  const values = value.map((item) => String(item ?? "").trim()).filter(Boolean);
  return values.length > 0 ? values : null;
}

export function recoveryDisplayFromMetadata(
  metadata: Record<string, unknown>,
): RecoveryDisplay | null {
  return (
    recoveryDisplayFromRecoveryState(metadata.recovery) ??
    recoveryDisplayFromClarification(metadata.clarification) ??
    recoveryDisplayFromResponseIntent(metadata.response_intent) ??
    recoveryDisplayFromResponseIntent(
      recordOrNull(metadata.pending_strategy)?.response_intent,
    )
  );
}

export function recoveryDisplayFromRecoveryState(
  value: unknown,
): RecoveryDisplay | null {
  const recovery = recordOrNull(value);
  const code = stringOrNull(recovery?.code);
  if (!code) {
    return null;
  }
  const params = recordOrNull(recovery?.params);
  return {
    kind: "recovery_code",
    code,
    values: stringValues(params),
  };
}

export function recoveryDisplayFromResponseIntent(
  value: unknown,
): RecoveryDisplay | null {
  const intent = recordOrNull(value);
  const kind = stringOrNull(intent?.kind);
  if (!intent || !kind) {
    return null;
  }
  if (kind === "unsupported_recovery") {
    return unsupportedRecoveryDisplay(intent);
  }
  if (kind === "artifact_action_recovery") {
    const facts = recordOrNull(intent.facts);
    const status = stringOrNull(facts?.status) ?? "invalid_state";
    const userSafeMessage = stringOrNull(facts?.user_safe_message);
    return {
      kind: "artifact_action_recovery",
      status,
      values: userSafeMessage ? { userSafeMessage } : undefined,
    };
  }
  return null;
}

export function recoveryDisplayText(
  display: RecoveryDisplay | null | undefined,
  t: TFunction,
): string {
  if (!display) {
    return "";
  }
  if (display.kind === "recovery_code") {
    return t(`chat.recovery.${display.code}`, recoveryCodeValues(display, t));
  }
  if (display.kind === "coverage_recovery") {
    return t(`chat.coverage_recovery.${display.code}`);
  }
  if (display.kind === "unsupported_recovery") {
    const optionsText = joinLocalizedOptions(
      display.values.options.map((option) => optionDisplayText(option, t)),
      t,
    );
    if (!optionsText) {
      return "";
    }
    const symbol = display.values.symbol;
    const rawValue = display.values.rawValue;
    const key = rawValue
      ? symbol
        ? "chat.clarification.unsupported_recovery_with_raw_value_for_asset"
        : "chat.clarification.unsupported_recovery_with_raw_value"
      : symbol
        ? "chat.clarification.unsupported_recovery_for_asset"
        : "chat.clarification.unsupported_recovery";
    return t(key, {
      rawValue,
      symbol,
      options: optionsText,
    });
  }
  if (display.kind === "clarification") {
    return clarificationDisplayText(display, t);
  }
  const statusKey = artifactActionStatusKey(display.status);
  return t(`chat.recovery.${statusKey}`, artifactActionValues(display));
}

function recoveryCodeValues(
  display: Extract<RecoveryDisplay, { kind: "recovery_code" }>,
  t: TFunction,
): Record<string, string> {
  const values = display.values ?? {};
  if (display.code === "execution_data_unavailable") {
    const dataKind = values.data_kind;
    const dataLabel =
      dataKind === "benchmark"
        ? t("chat.recovery.data_kind.benchmark")
        : t("chat.recovery.data_kind.market");
    return { ...values, dataLabel };
  }
  return values;
}

function unsupportedRecoveryDisplay(
  intent: Record<string, unknown>,
): RecoveryDisplay | null {
  const options = Array.isArray(intent.options)
    ? intent.options
        .map((option) => recordOrNull(option))
        .filter((option): option is Record<string, unknown> => Boolean(option))
        .map((option) => ({
          label: stringOrNull(option.label) ?? undefined,
          replacementValues: recordOrNull(option.replacement_values),
        }))
        .slice(0, 3)
    : [];
  if (options.length === 0) {
    return null;
  }
  const facts = recordOrNull(intent.facts);
  return {
    kind: "unsupported_recovery",
    values: {
      rawValue: unsupportedRawValue(facts),
      symbol: primarySymbol(recordOrNull(facts?.strategy)),
      options,
    },
  };
}

function recoveryDisplayFromClarification(value: unknown): RecoveryDisplay | null {
  const clarification = recordOrNull(value);
  const kind = stringOrNull(clarification?.kind);
  if (!clarification || !kind) {
    return null;
  }
  const promptSource = stringOrNull(clarification.prompt_source);
  if (promptSource && promptSource !== "degraded_fallback") {
    return null;
  }
  if (kind === "coverage_recovery") {
    const code = stringOrNull(clarification.reason_code);
    return code ? { kind: "coverage_recovery", code } : null;
  }
  if (kind === "unsupported_recovery") {
    return unsupportedRecoveryDisplayFromClarification(clarification);
  }
  if (kind !== "clarification") {
    return null;
  }
  const payload = recordOrNull(clarification.payload);
  const semanticNeeds = stringArrayOrNull(clarification.semantic_needs) ?? [];
  return {
    kind: "clarification",
    reasonCode: stringOrNull(clarification.reason_code) ?? undefined,
    requestedField: stringOrNull(clarification.requested_field) ?? undefined,
    semanticNeeds,
    values: strategyValues(payload?.strategy),
  };
}

export function coverageRecoveryActionsFromMetadata(
  metadata: Record<string, unknown>,
): ChatActionOption[] {
  const clarification = recordOrNull(metadata.clarification);
  if (stringOrNull(clarification?.kind) !== "coverage_recovery") {
    return [];
  }
  const options = Array.isArray(clarification?.options)
    ? clarification.options
    : [];
  const allowed = new Map([
    ["change_dates", { field: "date_range", label: "Change dates" }],
    ["change_asset", { field: "asset_universe", label: "Change asset" }],
    [
      "change_benchmark",
      { field: "comparison_baseline", label: "Change benchmark" },
    ],
  ]);
  return options.flatMap((rawOption): ChatActionOption[] => {
    const option = recordOrNull(rawOption);
    const id = stringOrNull(option?.id);
    const definition = id ? allowed.get(id) : undefined;
    const replacementValues = recordOrNull(option?.replacement_values);
    if (
      !id ||
      !definition ||
      stringOrNull(replacementValues?.requested_field) !== definition.field
    ) {
      return [];
    }
    return [
      {
        id: `coverage-${id.replaceAll("_", "-")}`,
        label: definition.label,
        labelKey: `chat.coverage_recovery.actions.${id}`,
        type: "select_response_option",
        payload: {
          option_id: id,
          replacement_values: { requested_field: definition.field },
        },
      },
    ];
  });
}

function unsupportedRecoveryDisplayFromClarification(
  clarification: Record<string, unknown>,
): RecoveryDisplay | null {
  const options = Array.isArray(clarification.options)
    ? clarification.options
        .map((option) => recordOrNull(option))
        .filter((option): option is Record<string, unknown> => Boolean(option))
        .map((option) => ({
          label:
            stringOrNull(option.compatibility_label) ??
            stringOrNull(option.label) ??
            undefined,
          replacementValues: recordOrNull(option.replacement_values),
        }))
        .slice(0, 3)
    : [];
  if (options.length === 0) {
    return null;
  }
  const payload = recordOrNull(clarification.payload);
  const rawValue = stringOrNull(payload?.raw_value);
  return {
    kind: "unsupported_recovery",
    values: {
      rawValue:
        rawValue && !looksLikeInternalCode(rawValue) ? rawValue : undefined,
      symbol: primarySymbol(recordOrNull(payload?.strategy)),
      options,
    },
  };
}

function strategyValues(value: unknown): Record<string, string> | undefined {
  const strategy = recordOrNull(value);
  const symbol = primarySymbol(strategy);
  const assets = stringArrayOrNull(strategy?.asset_universe);
  const assetText = assets?.join(", ");
  return {
    ...(symbol ? { symbol } : {}),
    ...(assetText ? { assetText } : {}),
  };
}

function clarificationDisplayText(
  display: Extract<RecoveryDisplay, { kind: "clarification" }>,
  t: TFunction,
): string {
  const key = clarificationKey(display);
  return key ? t(key, display.values ?? {}) : "";
}

function clarificationKey(
  display: Extract<RecoveryDisplay, { kind: "clarification" }>,
): string | null {
  const semanticNeeds = new Set(display.semanticNeeds);
  const requestedField = fieldBase(display.requestedField);
  const symbol = display.values?.symbol;
  const assetText = display.values?.assetText;
  if (requestedField === "date_range" || semanticNeeds.has("period")) {
    return symbol ? "chat.clarification.period_for_asset" : "chat.clarification.period";
  }
  if (requestedField === "asset_universe" || semanticNeeds.has("asset_target")) {
    return "chat.clarification.asset_target";
  }
  if (requestedField === "assumption" || semanticNeeds.has("assumption")) {
    return symbol
      ? "chat.clarification.assumption_for_asset"
      : "chat.clarification.assumption";
  }
  if (semanticNeeds.has("sizing_amount") && semanticNeeds.has("schedule")) {
    return "chat.clarification.sizing_amount_schedule";
  }
  if (requestedField === "capital_amount" || semanticNeeds.has("sizing_amount")) {
    return "chat.clarification.sizing_amount";
  }
  if (requestedField === "cadence" || semanticNeeds.has("schedule")) {
    return "chat.clarification.schedule";
  }
  if (
    requestedField === "entry_logic" ||
    requestedField === "exit_logic" ||
    semanticNeeds.has("rule_definition")
  ) {
    return "chat.clarification.rule_definition";
  }
  if (requestedField === "refinement" || semanticNeeds.has("refinement")) {
    return assetText
      ? "chat.clarification.refinement_for_asset"
      : "chat.clarification.refinement";
  }
  return null;
}

function fieldBase(value: string | undefined): string | null {
  return value ? value.split("[", 1)[0] : null;
}

function primarySymbol(strategy: Record<string, unknown> | null): string | undefined {
  const assets = stringArrayOrNull(strategy?.asset_universe);
  return assets?.[0]?.toUpperCase();
}

function unsupportedRawValue(
  facts: Record<string, unknown> | null,
): string | undefined {
  const constraints = Array.isArray(facts?.unsupported_constraints)
    ? facts?.unsupported_constraints
    : [];
  for (const item of constraints) {
    const constraint = recordOrNull(item);
    const value = stringOrNull(constraint?.raw_value);
    if (value && !looksLikeInternalCode(value)) {
      return value;
    }
  }
  return undefined;
}

function looksLikeInternalCode(value: string): boolean {
  return (
    value.includes("_") &&
    value === value.toLowerCase() &&
    !/\s/.test(value)
  );
}

function optionDisplayText(
  option: { label?: string; replacementValues?: Record<string, unknown> | null },
  t: TFunction,
): string {
  const key = simplificationOptionKey(option.replacementValues);
  if (key) {
    return t(`chat.simplification_options.${key}`);
  }
  return option.label ?? "";
}

function simplificationOptionKey(
  values: Record<string, unknown> | null | undefined,
): string | null {
  if (!values) {
    return null;
  }
  if (values.simplify_logic === "rsi_only") {
    return "rsi_threshold";
  }
  if (ruleType(values.entry_rule) === "rsi_threshold") {
    return "rsi_threshold";
  }
  if (ruleType(values.exit_rule) === "rsi_threshold") {
    return "rsi_threshold";
  }
  if (
    ruleType(values.entry_rule) === "moving_average_crossover" ||
    ruleType(values.exit_rule) === "moving_average_crossover" ||
    values.rule_family === "moving_average_crossover" ||
    values.strategy_type === "moving_average_crossover"
  ) {
    return "moving_average_crossover";
  }
  if (values.strategy_type === "buy_and_hold") {
    return "buy_and_hold";
  }
  return null;
}

function ruleType(value: unknown): string | null {
  return stringOrNull(recordOrNull(value)?.type);
}

function joinLocalizedOptions(values: string[], t: TFunction): string {
  const options = values.map((value) => value.trim()).filter(Boolean);
  if (options.length <= 1) {
    return options[0] ?? "";
  }
  const orText = t("common.or");
  if (options.length === 2) {
    return `${options[0]} ${orText} ${options[1]}`;
  }
  return `${options.slice(0, -1).join(", ")}, ${orText} ${
    options[options.length - 1]
  }`;
}

function artifactActionStatusKey(status: string): string {
  if (status === "stale") {
    return "artifact_action_retry_stale";
  }
  if (status === "missing_artifact_id") {
    return "artifact_action_retry_missing_artifact_id";
  }
  if (status === "missing_payload") {
    return "artifact_action_retry_missing_payload";
  }
  if (status === "non_retryable") {
    return "artifact_action_retry_non_retryable";
  }
  if (status === "rebuilt_confirmation") {
    return "artifact_action_retry_rebuilt_confirmation";
  }
  if (status === "invalid_state") {
    return "artifact_action_invalid_state";
  }
  return "artifact_action_retry_inactive";
}

function artifactActionValues(
  display: Extract<RecoveryDisplay, { kind: "artifact_action_recovery" }>,
): Record<string, string> {
  const values = display.values ?? {};
  if (display.status !== "non_retryable") {
    return values;
  }
  const userSafeMessage = values.userSafeMessage?.trim();
  return {
    ...values,
    blockerSuffix: userSafeMessage ? `: ${userSafeMessage}` : "",
  };
}

function stringValues(
  value: Record<string, unknown> | null,
): Record<string, string> | undefined {
  if (!value) {
    return undefined;
  }
  const entries = Object.entries(value)
    .map(([key, item]) => [key, stringOrNull(item)] as const)
    .filter((entry): entry is readonly [string, string] => Boolean(entry[1]));
  return entries.length > 0 ? Object.fromEntries(entries) : undefined;
}
