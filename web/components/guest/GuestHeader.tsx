"use client";

import { useTranslation } from "react-i18next";
import GuestSettingsMenu from "./GuestSettingsMenu";
import { formatGuestExpiry } from "./GuestLegalFooter";

export default function GuestHeader({
  expiresAt,
  onFeedback,
  onSignIn,
}: {
  expiresAt: string | null | undefined;
  onFeedback: () => void;
  onSignIn: () => void;
}) {
  const { t, i18n } = useTranslation();
  const formattedExpiry = expiresAt
    ? formatGuestExpiry(expiresAt, i18n.resolvedLanguage ?? i18n.language)
    : "";

  return (
    <div
      className="flex items-center gap-1.5"
      data-guest-expires-at={expiresAt ?? undefined}
    >
      {formattedExpiry ? (
        <span className="sr-only">
          {t(
            "guest.shell.temporary_until",
            "Temporary chat · available in this browser until {{date}}",
            { date: formattedExpiry },
          )}
        </span>
      ) : null}
      <GuestSettingsMenu onFeedback={onFeedback} />
      <button
        type="button"
        onClick={onSignIn}
        className="inline-flex min-h-11 items-center justify-center rounded-full border border-black/10 bg-white/75 px-4 text-[14px] font-semibold text-black transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/25 dark:border-white/12 dark:bg-white/[0.04] dark:text-white dark:hover:bg-white/[0.08] dark:focus-visible:ring-white/30"
      >
        {t("guest.shell.sign_in", "Sign in")}
      </button>
    </div>
  );
}
