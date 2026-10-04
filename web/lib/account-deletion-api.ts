import { logoutFromApi, postFeedback } from "./argus-api";
import { apiFetch } from "./argus-api-transport";

export type AccountDeletionResult = {
  /** done: everything is deleted. in_progress (202): the account is locked and
   * signed out, but a step hasn't finished, so a retry or the operator-run
   * sweep finishes the deletion later. Never show in_progress as done. */
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

/** success: deleted. in_progress: locked and signed out, finishing later.
 * requested: the in-app command is off here, so support got a ticket.
 * unavailable: off here and the ticket failed too, so only email is left. */
export type AccountDeletionOutcome =
  | "success"
  | "in_progress"
  | "requested"
  | "unavailable";

/** The account is gone, or locked while it finishes: the session is dead either
 * way, so the browser signs out as soon as this result arrives, not when the
 * dialog closes (Marcus #801 re-check N2). The dialog stays up as the
 * signed-out confirmation; its Done only cleans up and leaves. */
export function deletionEndsSession(
  outcome: AccountDeletionOutcome | string,
): boolean {
  return outcome === "success" || outcome === "in_progress";
}

/** Passed to onLogout after the account was just deleted.
 * afterAccountDeletion: sign this browser out now (the one logout call), but
 * keep the current surface (the confirmation dialog) mounted.
 * sessionEnded: Done or back on that confirmation; the sign-out already
 * happened, so only clear this browser's state and leave, never a second
 * logout call. */
export type LogoutOptions = { afterAccountDeletion?: boolean; sessionEnded?: boolean };

/** The account was just deleted: end this browser's session now. The chat's
 * account boundary is told first, so the sign-out doesn't swap the surface
 * for the account-changed screen and the dialog stays as the signed-out
 * confirmation. This is the only logout call: its Done passes sessionEnded,
 * which clears local state and leaves without signing out again. If this
 * call fails, the server still refuses the session (the account is gone or
 * locked), so nothing is gained by a second one. */
export async function endSessionKeepingSurface(
  boundary: { beginConversion: () => void },
  signOut: () => Promise<unknown> = logoutFromApi,
): Promise<void> {
  boundary.beginConversion();
  await signOut().catch(() => undefined);
}

/** The Delete account button. Throws only when nothing happened and a retry
 * is the right answer (network, account_deletion_unavailable, rate limit). */
export async function requestAccountDeletion(
  profileLanguage: string,
): Promise<AccountDeletionOutcome> {
  try {
    const result = await deleteAccount();
    return result.status === "in_progress" ? "in_progress" : "success";
  } catch (err) {
    const { status, code } = err as { status?: number; code?: string };
    // A 503 account_deletion_incomplete comes after the run opened and the
    // account was locked: the session is dead and the run finishes later.
    if (status === 503 && code === "account_deletion_incomplete") {
      return "in_progress";
    }
    if (status !== 404) throw err;
  }
  // 404: the command is switched off on this server. Support still gets a
  // ticket with the account, as before Lane 6.
  try {
    await postFeedback({
      type: "account_deletion_request",
      message: "Private alpha account deletion requested.",
      context: { source: "profile_modal", profile_language: profileLanguage },
    });
    return "requested";
  } catch (err) {
    console.error("Failed to submit account deletion request", err);
    return "unavailable";
  }
}
