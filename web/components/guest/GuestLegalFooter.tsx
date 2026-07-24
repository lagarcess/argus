"use client";

import { useTranslation } from "react-i18next";
import { localeForLanguage } from "@/lib/language-features";

export type GuestLegalFooterVariant = "before_message" | "after_message";

export function formatGuestExpiryDate(
  expiresAt: string,
  language: string,
): string {
  const expires = new Date(expiresAt);
  if (Number.isNaN(expires.getTime())) return "";
  return new Intl.DateTimeFormat(localeForLanguage(language), {
    dateStyle: "medium",
  }).format(expires);
}

export function formatGuestExpiryTimestamp(
  expiresAt: string,
  language: string,
): string {
  const expires = new Date(expiresAt);
  if (Number.isNaN(expires.getTime())) return "";
  return new Intl.DateTimeFormat(localeForLanguage(language), {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(expires);
}

export default function GuestLegalFooter({
  expiresAt,
  variant,
}: {
  expiresAt: string | null | undefined;
  variant: GuestLegalFooterVariant;
}) {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage ?? i18n.language;
  const expiryDate = expiresAt
    ? formatGuestExpiryDate(expiresAt, language)
    : "";
  const accessibleExpiry = expiresAt
    ? formatGuestExpiryTimestamp(expiresAt, language)
    : "";
  const linkClass =
    "font-medium underline decoration-black/20 underline-offset-2 transition-colors hover:text-black hover:decoration-black/50 focus-visible:rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/25 dark:decoration-white/25 dark:hover:text-white dark:hover:decoration-white/55 dark:focus-visible:ring-white/30";

  return (
    <div
      data-testid={`guest-legal-${variant}`}
      className="mt-3 text-center text-[13px] font-normal leading-[1.5] text-black/45 dark:text-white/45"
    >
      <p>
        {variant === "before_message" ? (
          <>
            {t("guest.shell.before_message.prefix", "By messaging Argus, you agree to ")}
            <a className={linkClass} href="/terms">
              {t("guest.shell.before_message.terms", "Terms")}
            </a>
            {t("guest.shell.before_message.middle", " and acknowledge ")}
            <a className={linkClass} href="/privacy">
              {t("guest.shell.before_message.privacy", "Privacy")}
            </a>
            .
          </>
        ) : (
          <>
            {t(
              "guest.shell.after_message.safety",
              "Argus can make mistakes. For education only. Not financial advice.",
            )}{" "}
            <a className={linkClass} href="/terms">
              {t("guest.shell.after_message.terms", "Terms")}
            </a>
            {" · "}
            <a className={linkClass} href="/privacy">
              {t("guest.shell.after_message.privacy", "Privacy")}
            </a>
            .
          </>
        )}
      </p>
      {expiresAt && expiryDate ? (
        <time
          data-testid="guest-temporary-notice"
          dateTime={expiresAt}
          title={expiresAt}
          aria-label={accessibleExpiry}
          className="mt-1 block text-[12px] text-black/35 dark:text-white/35"
        >
          {t(
            "guest.shell.temporary_until",
            "Temporary chat · available until {{date}}",
            { date: expiryDate },
          )}
        </time>
      ) : null}
    </div>
  );
}
