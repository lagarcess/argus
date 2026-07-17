import { clearArgusSessionCookies } from "./argus-api";
import { getSupabaseClient } from "./supabase-client";

export type AuthSecurityPort = {
  exchangeCodeForSession: (
    code: string,
  ) => Promise<{ error: unknown | null }>;
  updateUser: (
    attributes: Record<string, string>,
  ) => Promise<{ error: unknown | null }>;
  signOut: (options: {
    scope: "local" | "others" | "global";
  }) => Promise<{ error: unknown | null }>;
};

export type SessionActionResult = {
  currentSessionPreserved: boolean | "unknown";
  freshLoginRequired: boolean;
  revocation: "complete" | "failed";
  cookieSync: "not_required" | "cleared" | "failed";
};

type ClearArgusCookies = () => Promise<void>;

function throwOnAuthError(error: unknown | null): void {
  if (!error) return;
  throw error instanceof Error ? error : new Error("Authentication request failed.");
}

export function createAuthSecurityActions(
  auth: AuthSecurityPort,
  clearCookies: ClearArgusCookies,
) {
  const signOut = async (
    scope: "local" | "others" | "global",
  ): Promise<SessionActionResult> => {
    let revocationError: unknown | null = null;
    try {
      const { error } = await auth.signOut({ scope });
      revocationError = error;
    } catch (error) {
      revocationError = error;
    }
    if (scope === "others") {
      throwOnAuthError(revocationError);
      return {
        currentSessionPreserved: true,
        freshLoginRequired: false,
        revocation: "complete",
        cookieSync: "not_required",
      };
    }
    let cookieSync: SessionActionResult["cookieSync"] = "cleared";
    try {
      await clearCookies();
    } catch {
      cookieSync = "failed";
    }
    return {
      currentSessionPreserved: revocationError ? "unknown" : false,
      freshLoginRequired: revocationError === null,
      revocation: revocationError ? "failed" : "complete",
      cookieSync,
    };
  };

  return {
    async exchangeRecoveryCode(code: string): Promise<void> {
      if (!code) throw new Error("Missing recovery code.");
      const { error } = await auth.exchangeCodeForSession(code);
      throwOnAuthError(error);
    },

    async resetRecoveredPassword(
      newPassword: string,
    ): Promise<SessionActionResult> {
      if (newPassword.length < 8) throw new Error("Password is too short.");
      const { error } = await auth.updateUser({ password: newPassword });
      throwOnAuthError(error);
      return signOut("global");
    },

    async changePassword({
      currentPassword,
      newPassword,
    }: {
      currentPassword: string;
      newPassword: string;
    }): Promise<SessionActionResult> {
      if (!currentPassword) throw new Error("Current password is required.");
      if (newPassword.length < 8) throw new Error("Password is too short.");
      const { error } = await auth.updateUser({
        password: newPassword,
        current_password: currentPassword,
      });
      throwOnAuthError(error);
      return signOut("global");
    },

    signOutThisBrowser: () => signOut("local"),
    signOutOtherSessions: () => signOut("others"),
    signOutAllSessions: () => signOut("global"),
  };
}

export function getAuthSecurityActions() {
  const supabase = getSupabaseClient();
  if (!supabase) {
    throw new Error("Authentication is not configured.");
  }
  const auth: AuthSecurityPort = {
    exchangeCodeForSession: (code) => supabase.auth.exchangeCodeForSession(code),
    updateUser: (attributes) => supabase.auth.updateUser(attributes),
    signOut: (options) => supabase.auth.signOut(options),
  };
  return createAuthSecurityActions(auth, async () => {
    await clearArgusSessionCookies();
  });
}

export async function requestPasswordRecovery(email: string): Promise<void> {
  const response = await fetch("/api/auth/recovery", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ email }),
  });
  if (!response.ok) {
    throw new Error("Recovery request failed.");
  }
}
