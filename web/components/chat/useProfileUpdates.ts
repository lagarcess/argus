"use client";

import { useCallback, type Dispatch, type SetStateAction } from "react";

import { applyProfileUpdate, greetingNameFor } from "@/lib/account-profile";
import type { ApiUser, UserResponse } from "@/lib/guest-account";

/**
 * Everything the chat shell needs about the account's profile, from one place.
 *
 * The menu keeps its own copy while it is open; this is the copy surfaces read.
 * `PATCH /me` returns the whole updated user, so a save folds the response in
 * rather than spending a second request re-reading what it just carried.
 */
export function useProfileUpdates(
  account: UserResponse | null,
  setAccount: Dispatch<SetStateAction<UserResponse | null>>,
): { onProfileUpdated: (user: ApiUser) => void; greetingName: string | null } {
  const onProfileUpdated = useCallback(
    (user: ApiUser) => {
      setAccount((current) => applyProfileUpdate(current, user));
    },
    [setAccount],
  );
  return { onProfileUpdated, greetingName: greetingNameFor(account) };
}
