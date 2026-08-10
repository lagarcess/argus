"use client";

import { useCallback, type Dispatch, type SetStateAction } from "react";

import { applyProfileUpdate, greetingNameFor } from "@/lib/account-profile";
import type { ApiUser, UserResponse } from "@/lib/guest-account";

/**
 * The shell's profile state: the greeting's name, and the callback that keeps
 * the shell's copy current when a setting is saved.
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
