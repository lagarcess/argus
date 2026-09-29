import type {
  CreateFinancialAccountRequest,
  EditFinancialAccountRequest,
  FinancialAccount,
  FinancialAccountType,
  WriteFinancialOpeningRequest,
} from "@/lib/financial-accounts-api";
import {
  liabilityAmountInput,
  parseAccountAmountInput,
} from "@/lib/financial-accounts-format";

export type AccountFormKind = "create" | "edit" | "opening" | "archive";
export type AccountDraft = {
  type: FinancialAccountType;
  currency: string;
  nickname: string;
  amount: string;
  asOf: string;
  timeZone: string;
  reason: string;
  ownershipShare: string;
  archived: boolean;
};

export function accountDraft(account: FinancialAccount): AccountDraft {
  return {
    type: account.type,
    currency: account.currency,
    nickname: account.nickname ?? "",
    amount: account.opening
      ? liabilityAmountInput(account.opening.amount, account.nature)
      : "",
    asOf: account.opening?.as_of ?? "",
    timeZone: account.opening?.time_zone ?? "",
    reason: "",
    ownershipShare: String(account.ownership_share_bps / 100),
    archived: account.archived,
  };
}

export function emptyAccountDraft(currency: string): AccountDraft {
  return {
    type: "cash", currency, nickname: "", amount: "", asOf: "", timeZone: "",
    reason: "", ownershipShare: "100", archived: false,
  };
}

export class AccountFormError extends Error {
  constructor(public readonly code: string) { super(code); }
}

export function createAccountPayload(
  draft: AccountDraft,
  locale: string,
  instant: string,
  timeZone: string,
): CreateFinancialAccountRequest {
  return {
    type: draft.type,
    currency: draft.currency,
    nickname: draft.nickname,
    ...(draft.amount.trim() ? {
      amount: parseAccountAmountInput(draft.amount, locale),
      as_of: instant,
      time_zone: timeZone,
    } : {}),
  };
}

export function editAccountPayload(
  snapshot: FinancialAccount,
  draft: AccountDraft,
): EditFinancialAccountRequest {
  const original = accountDraft(snapshot);
  const payload: EditFinancialAccountRequest = { expected_version: snapshot.version };
  if (draft.nickname !== original.nickname) payload.nickname = draft.nickname;
  if (draft.type !== original.type) payload.type = draft.type;
  if (draft.currency !== original.currency) payload.currency = draft.currency;
  if (draft.archived !== original.archived) payload.archived = draft.archived;
  if (draft.ownershipShare !== original.ownershipShare) {
    if (!/^\d+(?:\.\d{1,2})?$/.test(draft.ownershipShare)) {
      throw new AccountFormError("ownership_share_invalid");
    }
    const [whole, fraction = ""] = draft.ownershipShare.split(".");
    const bps = Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
    if (!Number.isSafeInteger(bps) || bps < 1 || bps > 10000) {
      throw new AccountFormError("ownership_share_invalid");
    }
    payload.ownership_share_bps = bps;
  }
  if (Object.keys(payload).length === 1) throw new AccountFormError("no_changes");
  return payload;
}

export function openingAccountPayload(
  snapshot: FinancialAccount,
  draft: AccountDraft,
  locale: string,
): WriteFinancialOpeningRequest {
  const original = accountDraft(snapshot);
  const payload: WriteFinancialOpeningRequest = {
    expected_version: snapshot.version,
    expected_revision: snapshot.opening?.revision ?? null,
  };
  if (!snapshot.opening || draft.amount !== original.amount) {
    payload.amount = parseAccountAmountInput(draft.amount, locale);
  }
  if (draft.asOf !== original.asOf) payload.as_of = draft.asOf;
  if (draft.timeZone !== original.timeZone) payload.time_zone = draft.timeZone;
  if (snapshot.opening || draft.reason.trim()) payload.reason = draft.reason;
  if (snapshot.opening && !draft.reason.trim()) throw new AccountFormError("reason_required");
  if (snapshot.opening && payload.amount === undefined && payload.as_of === undefined && payload.time_zone === undefined) {
    throw new AccountFormError("no_changes");
  }
  return payload;
}

/** Keep deliberate edits, while untouched fields follow the explicitly adopted read. */
export function reconcileAccountDraft(
  previous: FinancialAccount,
  current: FinancialAccount,
  draft: AccountDraft,
): AccountDraft {
  const original = accountDraft(previous);
  const latest = accountDraft(current);
  const reconciled = Object.fromEntries(
    Object.entries(draft).map(([key, value]) => [
      key, value === original[key as keyof AccountDraft] ? latest[key as keyof AccountDraft] : value,
    ]),
  ) as AccountDraft;
  if (previous.currency !== current.currency || previous.nature !== current.nature) {
    reconciled.amount = "";
  }
  return reconciled;
}

export function accountErrorCode(error: unknown): string {
  if (typeof error !== "object" || error === null) return "request_failed";
  if ("code" in error && typeof error.code === "string" && error.code !== "unknown") return error.code;
  if ("status" in error && error.status === 401) return "unauthorized";
  return "request_failed";
}

export function accountErrorStatus(error: unknown): number | null {
  return typeof error === "object" && error !== null && "status" in error && typeof error.status === "number"
    ? error.status : null;
}

export function isRetiredAccountRequest(error: unknown): boolean {
  return error instanceof Error && (error.name === "AbortError" || error.name === "ChatAccountChangedError");
}

export function requiresAccountReconciliation(error: unknown): boolean {
  const status = accountErrorStatus(error);
  return accountErrorCode(error) === "stale_version" || status === null || status >= 500;
}

export const ACCOUNT_ERROR_FIELDS: Readonly<Record<string, keyof AccountDraft>> = {
  amount_invalid: "amount", amount_precision: "amount", amount_out_of_range: "amount",
  nickname_invalid: "nickname", currency_unsupported: "currency", currency_locked: "currency",
  type_locked: "type", nature_change_requires_empty_account: "type",
  date_invalid: "asOf", date_in_future: "asOf", time_zone_invalid: "timeZone",
  reason_required: "reason", reason_invalid: "reason", ownership_share_invalid: "ownershipShare",
};
