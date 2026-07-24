"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";
import { retryGuestSession, startGuestSession } from "@/lib/guest-session";

export default function GuestEntry() {
  const { t, i18n } = useTranslation();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [retrying, setRetrying] = useState(false);

  const openChat = useCallback(
    async (retry = false) => {
      setError(null);
      setRetrying(retry);
      try {
        const bootstrap = retry ? retryGuestSession : startGuestSession;
        await bootstrap(i18n.resolvedLanguage ?? i18n.language);
        router.replace("/chat");
        router.refresh();
      } catch (cause) {
        setError(
          cause instanceof Error
            ? cause.message
            : t(
                "guest.entry.error",
                "Argus could not start this temporary workspace.",
              ),
        );
      } finally {
        setRetrying(false);
      }
    },
    [i18n.language, i18n.resolvedLanguage, router, t],
  );

  useEffect(() => {
    void openChat();
  }, [openChat]);

  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-background px-6 text-foreground">
      {error ? (
        <div className="max-w-sm text-center">
          <h1 className="font-display text-4xl font-medium tracking-tight">
            argus
          </h1>
          <p className="mt-4 text-sm text-black/60 dark:text-white/60">
            {t(
              "guest.entry.error",
              "Argus could not start this temporary workspace.",
            )}
          </p>
          <button
            type="button"
            disabled={retrying}
            onClick={() => void openChat(true)}
            className="mt-6 min-h-11 rounded-full bg-black px-6 py-3 text-base font-medium text-white disabled:opacity-50 dark:bg-white dark:text-black"
          >
            {retrying
              ? t("common.loading", "Loading...")
              : t("common.try_again", "Try again")}
          </button>
        </div>
      ) : (
        <div
          aria-label={t("guest.entry.loading", "Opening Argus")}
          className="h-8 w-8 animate-spin rounded-full border-2 border-current border-t-transparent"
          role="status"
        />
      )}
    </main>
  );
}
