import type {
  ChatActionOption,
  StrategyConfirmationPayload,
  StrategyConfirmationRow,
  StrategyConfirmationRowKey,
  StrategyConfirmationStatus,
} from "./types";

const CONFIRMATION_STATUS_LABELS: Record<StrategyConfirmationStatus, string> = {
  could_not_run: "Could not run",
  draft_canceled: "Draft canceled",
  editing: "Editing",
  needs_change: "Needs change",
  not_completed: "Not completed",
  ready_to_run: "Ready to run",
  request_sent: "Request sent",
  run_complete: "Run complete",
  running: "Running",
  updated: "Updated",
};

const CONFIRMATION_STATUS_LABEL_KEYS: Record<StrategyConfirmationStatus, string> = {
  could_not_run: "chat.confirmation.status.could_not_run",
  draft_canceled: "chat.confirmation.status.draft_canceled",
  editing: "chat.confirmation.status.editing",
  needs_change: "chat.confirmation.status.needs_change",
  not_completed: "chat.confirmation.status.not_completed",
  ready_to_run: "chat.confirmation.status.ready_to_run",
  request_sent: "chat.confirmation.status.request_sent",
  run_complete: "chat.confirmation.status.run_complete",
  running: "chat.confirmation.status.running",
  updated: "chat.confirmation.status.updated",
};

const CONFIRMATION_ROW_LABEL_KEYS: Record<StrategyConfirmationRowKey, string> = {
  assets: "chat.confirmation.rows.assets",
  buy_rule: "chat.confirmation.rows.buy_rule",
  cadence: "chat.confirmation.rows.cadence",
  contribution: "chat.confirmation.rows.contribution",
  exit_rule: "chat.confirmation.rows.exit_rule",
  period: "chat.confirmation.rows.period",
  starting_capital: "chat.confirmation.rows.starting_capital",
  strategy: "chat.confirmation.rows.strategy",
};

const CONFIRMATION_ACTION_LABEL_KEYS: Partial<
  Record<NonNullable<ChatActionOption["type"]>, string>
> = {
  adjust_assumptions: "chat.confirmation.actions.adjust_assumptions",
  cancel_confirmation: "chat.confirmation.actions.cancel",
  change_asset: "chat.confirmation.actions.change_asset",
  change_dates: "chat.confirmation.actions.change_dates",
  run_backtest: "chat.confirmation.actions.run_backtest",
};

const LABEL_TO_STATUS: Record<string, StrategyConfirmationStatus> = {
  "could not run": "could_not_run",
  "draft canceled": "draft_canceled",
  editing: "editing",
  "needs change": "needs_change",
  "not completed": "not_completed",
  ready: "ready_to_run",
  "ready to run": "ready_to_run",
  "request sent": "request_sent",
  "run complete": "run_complete",
  running: "running",
  updated: "updated",
};

const LABEL_TO_ROW_KEY: Record<string, StrategyConfirmationRowKey> = {
  assets: "assets",
  "buy rule": "buy_rule",
  cadence: "cadence",
  contribution: "contribution",
  "exit rule": "exit_rule",
  period: "period",
  "starting capital": "starting_capital",
  strategy: "strategy",
};

const LABEL_KEY_TO_ROW_KEY = Object.fromEntries(
  Object.entries(CONFIRMATION_ROW_LABEL_KEYS).map(([key, labelKey]) => [
    labelKey,
    key,
  ]),
) as Record<string, StrategyConfirmationRowKey>;

const NON_ACTIONABLE_CONFIRMATION_STATUSES = new Set<StrategyConfirmationStatus>([
  "could_not_run",
  "draft_canceled",
  "not_completed",
  "request_sent",
  "run_complete",
  "running",
]);

function hasOwn<T extends object>(object: T, key: PropertyKey): key is keyof T {
  return Object.prototype.hasOwnProperty.call(object, key);
}

export function confirmationStatusLabel(status: StrategyConfirmationStatus): string {
  return CONFIRMATION_STATUS_LABELS[status];
}

export function confirmationStatusLabelKey(
  status: StrategyConfirmationStatus,
): string {
  return CONFIRMATION_STATUS_LABEL_KEYS[status];
}

export function confirmationStatusFromLabel(
  label: string | null | undefined,
): StrategyConfirmationStatus | null {
  const normalized = label?.trim().toLowerCase();
  if (!normalized) {
    return null;
  }
  return hasOwn(LABEL_TO_STATUS, normalized) ? LABEL_TO_STATUS[normalized] : null;
}

export function confirmationStatusFromValue(
  value: string | StrategyConfirmationStatus | null | undefined,
): StrategyConfirmationStatus | null {
  if (!value) {
    return null;
  }
  if (hasOwn(CONFIRMATION_STATUS_LABELS, value)) {
    return value as StrategyConfirmationStatus;
  }
  return confirmationStatusFromLabel(value);
}

export function confirmationStatusFromPayload(
  confirmation: Pick<
    StrategyConfirmationPayload,
    "confirmation_state" | "status" | "statusLabel"
  >,
): StrategyConfirmationStatus {
  const explicit = confirmationStatusFromValue(confirmation.status);
  if (explicit) {
    return explicit;
  }
  const legacy = confirmationStatusFromLabel(confirmation.statusLabel);
  if (legacy) {
    return legacy;
  }
  if (confirmation.confirmation_state === "cancelled") {
    return "draft_canceled";
  }
  if (confirmation.confirmation_state === "superseded") {
    return "updated";
  }
  return "ready_to_run";
}

export function confirmationStatusAllowsActions(
  status: StrategyConfirmationStatus,
): boolean {
  return !NON_ACTIONABLE_CONFIRMATION_STATUSES.has(status);
}

export function confirmationActionStatus(
  actionOrType: ChatActionOption | NonNullable<ChatActionOption["type"]> | undefined,
): StrategyConfirmationStatus {
  const type = typeof actionOrType === "string" ? actionOrType : actionOrType?.type;
  if (type === "cancel_confirmation") {
    return "draft_canceled";
  }
  if (type === "run_backtest") {
    return "running";
  }
  if (
    type === "change_dates" ||
    type === "change_asset" ||
    type === "adjust_assumptions"
  ) {
    return "editing";
  }
  return "updated";
}

export function confirmationRowKey(
  row: Pick<StrategyConfirmationRow, "key" | "labelKey" | "label">,
): StrategyConfirmationRowKey | null {
  if (row.key && hasOwn(CONFIRMATION_ROW_LABEL_KEYS, row.key)) {
    return row.key;
  }
  if (row.labelKey && hasOwn(LABEL_KEY_TO_ROW_KEY, row.labelKey)) {
    return LABEL_KEY_TO_ROW_KEY[row.labelKey];
  }
  const normalized = row.label.trim().toLowerCase();
  return hasOwn(LABEL_TO_ROW_KEY, normalized) ? LABEL_TO_ROW_KEY[normalized] : null;
}

export function confirmationRowLabelKey(
  row: Pick<StrategyConfirmationRow, "key" | "labelKey" | "label">,
): string | null {
  if (row.labelKey) {
    return row.labelKey;
  }
  const key = confirmationRowKey(row);
  return key ? CONFIRMATION_ROW_LABEL_KEYS[key] : null;
}

export function confirmationActionLabelKey(action: ChatActionOption): string | null {
  if (action.labelKey) {
    return action.labelKey;
  }
  return action.type ? CONFIRMATION_ACTION_LABEL_KEYS[action.type] ?? null : null;
}
