import { apiFetch } from "./argus-api-transport";

export type AccountDeletionResult = {
  status: "done" | "auth_deleted";
  /** Provider revocations still owed; the account is already gone. */
  pending: string[];
};

/** Deletes the signed-in account (Lane 6). The server takes the account from
 * the session; the body is only a confirmation. */
export async function deleteAccount() {
  return apiFetch<AccountDeletionResult>("/account/delete", {
    method: "POST",
    body: JSON.stringify({ confirm: true }),
  });
}
