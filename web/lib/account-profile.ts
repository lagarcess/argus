import type { ApiUser, UserResponse } from "./guest-account";

/**
 * One owner for the profile the chat shell renders from.
 *
 * The profile menu keeps its own copy while it is open, which is fine, but the
 * shell's copy is what surfaces read. Saving a setting updated only the menu's,
 * so the greeting went on using the name the page had loaded with until a full
 * reload, including in newly opened empty chats in the same session.
 *
 * Applying the patch response rather than refetching keeps the save to one round
 * trip: `PATCH /me` already returns the whole updated user, so a second `GET`
 * would only re-read what the response just carried.
 */

/** Fold a `PATCH /me` response into the shell's account snapshot. */
export function applyProfileUpdate<T extends { user: ApiUser }>(
  account: T | null,
  user: ApiUser,
): T | null {
  return account ? { ...account, user } : account;
}

/**
 * The name the greeting addresses the user by, from one place.
 *
 * Guests carry no `preferred_name` in their projection, so they resolve to null
 * here and fall back to the nameless pool without a separate branch.
 */
export function greetingNameFor(account: UserResponse | null): string | null {
  return account?.user.preferred_name ?? null;
}
