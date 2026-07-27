"use client";

import { useState } from "react";
import { useTranslation } from "react-i18next";
import AuthForm, {
  type AuthFormMode,
} from "@/components/auth/AuthForm";
import { linkGuestIdentity } from "@/lib/guest-api";
import { loginWithEmail } from "@/lib/argus-api";
import { retryGuestSession } from "@/lib/guest-session";

type ExpiredGuestSessionProps = {
  publicAccountAccessEnabled: boolean;
};

export default function ExpiredGuestSession({
  publicAccountAccessEnabled,
}: ExpiredGuestSessionProps) {
  const { t, i18n } = useTranslation();
  const [authMode, setAuthMode] = useState<AuthFormMode | null>(null);
  const [isRestarting, setIsRestarting] = useState(false);
  const [restartError, setRestartError] = useState<string | null>(null);

  const startNewTemporaryChat = async () => {
    setIsRestarting(true);
    setRestartError(null);
    try {
      await retryGuestSession(i18n.resolvedLanguage ?? i18n.language);
      window.location.assign("/chat");
    } catch {
      setRestartError(
        t(
          "guest.expired.restart_error",
          "Argus could not start a new temporary chat. Try again.",
        ),
      );
      setIsRestarting(false);
    }
  };

  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-background px-6 py-10 text-foreground">
      <section className="w-full max-w-md rounded-[2rem] border border-black/10 bg-white p-7 shadow-xl dark:border-white/10 dark:bg-[#1d1f24] sm:p-9">
        <p className="text-center font-display text-3xl font-medium tracking-tight">
          argus
        </p>
        <h1 className="mt-7 text-center text-2xl font-semibold tracking-tight">
          {t(
            "guest.expired.title",
            "This temporary chat has expired",
          )}
        </h1>
        <p className="mt-3 text-center text-sm leading-6 text-black/60 dark:text-white/60">
          {t(
            "guest.expired.detail",
            "Its messages and results can’t be recovered.",
          )}
        </p>

        {authMode ? (
          <div
            aria-label={
              authMode === "signup"
                ? t("guest.expired.create_account", "Create account")
                : t("guest.expired.sign_in", "Sign in")
            }
            className="mt-7"
            role="dialog"
          >
            <AuthForm
              mode={authMode}
              allowModeSwitch={publicAccountAccessEnabled}
              onModeChange={setAuthMode}
              onSubmit={async ({ mode, email, password }) => {
                if (mode === "signup") {
                  await linkGuestIdentity({ email, password });
                } else {
                  await loginWithEmail({ email, password });
                }
                window.location.assign("/chat");
              }}
            />
            <button
              type="button"
              className="mt-4 min-h-11 w-full rounded-full border border-black/15 px-5 py-3 text-sm font-medium dark:border-white/20"
              onClick={() => setAuthMode(null)}
            >
              {t("common.back", "Back")}
            </button>
          </div>
        ) : (
          <div className="mt-7 grid gap-3">
            <button
              type="button"
              disabled={isRestarting}
              onClick={() => void startNewTemporaryChat()}
              className="min-h-11 rounded-full bg-black px-6 py-3 text-base font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
            >
              {isRestarting
                ? t("common.loading", "Loading...")
                : t(
                    "guest.expired.start_new",
                    "Start a new temporary chat",
                  )}
            </button>
            <button
              type="button"
              className="min-h-11 rounded-full border border-black/15 px-6 py-3 text-base font-medium dark:border-white/20"
              onClick={() => setAuthMode("login")}
            >
              {t("guest.expired.sign_in", "Sign in")}
            </button>
            {publicAccountAccessEnabled && (
              <button
                type="button"
                className="min-h-11 rounded-full border border-black/15 px-6 py-3 text-base font-medium dark:border-white/20"
                onClick={() => setAuthMode("signup")}
              >
                {t("guest.expired.create_account", "Create account")}
              </button>
            )}
          </div>
        )}

        {restartError && (
          <p className="mt-4 text-center text-sm text-red-600 dark:text-red-300" role="alert">
            {restartError}
          </p>
        )}
      </section>
    </main>
  );
}
