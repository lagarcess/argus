import type { ApiUser, UserResponse } from "./guest-account";

/**
 * Fold a `PATCH /me` response into the shell's account snapshot, which is the
 * copy surfaces render from. The profile menu's own copy is a different one.
 */
export function applyProfileUpdate<T extends { user: ApiUser }>(
  account: T | null,
  user: ApiUser,
): T | null {
  return account ? { ...account, user } : account;
}

/** The one source of the greeting's name. Guests carry none, so they get null. */
export function greetingNameFor(account: UserResponse | null): string | null {
  return account?.user.preferred_name ?? null;
}
