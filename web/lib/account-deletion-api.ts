import { apiFetch } from "./argus-api-transport";

export type AccountDeletionResult = {
  /** done: everything is deleted. in_progress (202): the account is locked and
   * signed out, but a third party hasn't confirmed, so the server finishes the
   * deletion later. Never show in_progress as done. */
  status: "done" | "in_progress";
  /** The third parties still owed (apple, gmail, plaid, analytics). */
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
