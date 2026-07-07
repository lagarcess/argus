type TFunction = (
  key: string,
  options?: Record<string, unknown> | string,
) => string;

export type RecoveryDisplay =
  | {
      kind: "recovery_code";
      code: string;
      values?: Record<string, string>;
    }
  | {
      kind: "clarification";
      need: string;
      values?: Record<string, string>;
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
  if (!kind) {
    return null;
  }
  if (kind === "clarification") {
    const needs = stringArrayOrNull(intent.semantic_needs);
    const need = firstSupportedClarificationNeed(needs);
    if (!need) {
      return null;
    }
    return {
      kind: "clarification",
      need,
      values: strategyValues(recordOrNull(intent.facts)?.strategy),
    };
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
  if (display.kind === "clarification") {
    const values = display.values ?? {};
    const symbol = values.symbol;
    const keySuffix = symbol ? `${display.need}_for_asset` : display.need;
    return t(`chat.clarification.${keySuffix}`, values);
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

function firstSupportedClarificationNeed(needs: string[] | null): string | null {
  if (!needs) {
    return null;
  }
  if (needs.includes("sizing_amount") && needs.includes("schedule")) {
    return "sizing_amount_schedule";
  }
  const supported = [
    "period",
    "asset_target",
    "assumption",
    "sizing_amount",
    "schedule",
    "rule_definition",
    "refinement",
  ];
  return supported.find((need) => needs.includes(need)) ?? null;
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
