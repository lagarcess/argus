import { apiFetch } from "./argus-api-transport";

// Wire mirror of domain/recording/schemas.py; the server owns all financial rules.
export const FINANCIAL_ACCOUNT_TYPES = [
  "cash", "checking", "savings", "investment", "credit_card", "other_debt",
  "property", "vehicle", "other_asset",
] as const;

export type FinancialAccountType = (typeof FINANCIAL_ACCOUNT_TYPES)[number];
export type FinancialAccountNature = "asset" | "liability";

export interface FinancialAccountBalance {
  state: "known" | "unknown";
  /** JSON integers can lose precision. The decimal-string amount owns display. */
  amount_minor: unknown;
  amount: string | null;
  as_of: string | null;
  basis: "opening" | null;
  activity_since_tracking_minor: unknown;
}

export interface FinancialOpeningRevision {
  revision: number;
  amount_minor: unknown;
  amount: string;
  as_of: string;
  time_zone: string;
  reason: string | null;
  recorded_by: string | null;
  recorded_at: string;
}

export interface FinancialOpening {
  record_id: string;
  revision: number;
  amount_minor: unknown;
  amount: string;
  as_of: string;
  time_zone: string;
  reason: string | null;
  recorded_at: string;
  revisions: FinancialOpeningRevision[];
}

export interface FinancialAccount {
  id: string;
  type: FinancialAccountType;
  nature: FinancialAccountNature;
  currency: string;
  currency_fraction_digits: number;
  nickname: string | null;
  archived: boolean;
  ownership_share_bps: number;
  version: number;
  created_at: string;
  updated_at: string;
  balance: FinancialAccountBalance;
  opening: FinancialOpening | null;
}

export interface CreateFinancialAccountRequest {
  type: FinancialAccountType;
  currency: string;
  nickname?: string | null;
  amount?: string | null;
  as_of?: string | null;
  time_zone?: string | null;
  ownership_share_bps?: number;
}

export interface EditFinancialAccountRequest {
  expected_version: number;
  nickname?: string | null;
  type?: FinancialAccountType | null;
  currency?: string | null;
  archived?: boolean | null;
  ownership_share_bps?: number | null;
}

export interface WriteFinancialOpeningRequest {
  expected_version: number;
  expected_revision: number | null;
  amount?: string | null;
  as_of?: string | null;
  time_zone?: string | null;
  reason?: string | null;
}

const ACCOUNTS_PATH = "/financial-accounts";

function accountPath(id: string): string {
  return `${ACCOUNTS_PATH}/${encodeURIComponent(id)}`;
}

export async function listFinancialAccounts(
  expectedUserId: string,
  signal?: AbortSignal,
): Promise<FinancialAccount[]> {
  const response = await apiFetch<{ accounts: FinancialAccount[] }>(ACCOUNTS_PATH, {
    expectedUserId, signal,
  });
  return response.accounts;
}

export function getFinancialAccount(
  expectedUserId: string,
  id: string,
  signal?: AbortSignal,
): Promise<FinancialAccount> {
  return apiFetch<FinancialAccount>(accountPath(id), { expectedUserId, signal });
}

export function createFinancialAccount(
  expectedUserId: string,
  payload: CreateFinancialAccountRequest,
  idempotencyKey: string,
  signal?: AbortSignal,
): Promise<FinancialAccount> {
  return apiFetch<FinancialAccount>(ACCOUNTS_PATH, {
    expectedUserId, signal, method: "POST",
    headers: { "Idempotency-Key": idempotencyKey },
    body: JSON.stringify(payload),
  });
}

export function editFinancialAccount(
  expectedUserId: string,
  id: string,
  payload: EditFinancialAccountRequest,
  signal?: AbortSignal,
): Promise<FinancialAccount> {
  return apiFetch<FinancialAccount>(accountPath(id), {
    expectedUserId, signal, method: "PATCH", body: JSON.stringify(payload),
  });
}

export function writeFinancialOpening(
  expectedUserId: string,
  id: string,
  payload: WriteFinancialOpeningRequest,
  signal?: AbortSignal,
): Promise<FinancialAccount> {
  return apiFetch<FinancialAccount>(`${accountPath(id)}/opening`, {
    expectedUserId, signal, method: "PUT", body: JSON.stringify(payload),
  });
}
