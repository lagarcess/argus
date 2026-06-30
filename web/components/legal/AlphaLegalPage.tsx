"use client";

import Link from "next/link";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

type LegalPageKind = "terms" | "privacy";

type AlphaLegalPageProps = {
  kind: LegalPageKind;
  supportEmail: string;
};

const LEGAL_SECTIONS: Record<LegalPageKind, string[]> = {
  terms: [
    "no_investment_advice",
    "no_brokerage",
    "historical_simulations",
    "alpha_changes",
    "eligibility",
    "acceptable_use",
    "third_party_services",
    "account_support",
  ],
  privacy: [
    "data_collect",
    "data_use",
    "ai_market_data",
    "infrastructure",
    "access_retention",
    "your_controls",
    "sale_personal_info",
  ],
};

export default function AlphaLegalPage({
  kind,
  supportEmail,
}: AlphaLegalPageProps) {
  const { t } = useTranslation();
  const alternateHref = kind === "terms" ? "/privacy" : "/terms";
  const alternateLabel = t(
    kind === "terms" ? "legal.privacy.title" : "legal.terms.title",
  );

  return (
    <main className="min-h-[100dvh] bg-white text-[#191c1f] dark:bg-[#191c1f] dark:text-white">
      <div className="mx-auto flex w-full max-w-3xl flex-col px-6 py-8 md:px-8 md:py-12">
        <header className="flex items-center justify-between gap-4 border-b border-black/10 pb-5 dark:border-white/10">
          <Link
            href="/"
            className="font-display text-[18px] font-medium tracking-[0] text-black dark:text-white"
          >
            argus
          </Link>
          <Link
            href={alternateHref}
            className="rounded-full border border-black/10 px-4 py-2 text-[13px] font-medium text-black/70 transition-colors hover:border-black/25 hover:text-black dark:border-white/15 dark:text-white/70 dark:hover:border-white/30 dark:hover:text-white"
          >
            {alternateLabel}
          </Link>
        </header>

        <section className="pt-14 md:pt-20">
          <p className="mb-4 text-[12px] font-medium tracking-[0] text-black/45 dark:text-white/45">
            {t("legal.eyebrow")}
          </p>
          <h1 className="font-display max-w-[720px] text-[42px] font-medium leading-[1.05] tracking-[0] text-black dark:text-white md:text-[56px]">
            {t(`legal.${kind}.title`)}
          </h1>
          <p className="mt-4 text-[14px] font-medium text-black/45 dark:text-white/45">
            {t("legal.effective_date")}
          </p>
          <p className="mt-8 max-w-[680px] text-[17px] leading-8 text-black/65 dark:text-white/65">
            {t(`legal.${kind}.intro`)}
          </p>
        </section>

        <div className="mt-12 space-y-10 border-t border-black/10 pt-10 dark:border-white/10">
          {LEGAL_SECTIONS[kind].map((sectionKey) => (
            <section key={sectionKey}>
              <h2 className="font-display text-[24px] font-medium tracking-[0]">
                {t(`legal.${kind}.sections.${sectionKey}.title`)}
              </h2>
              <p className="mt-3 text-[15px] leading-7 text-black/65 dark:text-white/65">
                {renderLegalBody(t, kind, sectionKey, supportEmail)}
              </p>
            </section>
          ))}
        </div>

        <footer className="mt-14 flex flex-col gap-3 border-t border-black/10 pt-6 text-[13px] text-black/45 dark:border-white/10 dark:text-white/45 sm:flex-row sm:items-center sm:justify-between">
          <span>{t("legal.footer_label")}</span>
          <Link
            href="/"
            className="font-medium text-black/70 transition-colors hover:text-black dark:text-white/70 dark:hover:text-white"
          >
            {t("legal.back_to_argus")}
          </Link>
        </footer>
      </div>
    </main>
  );
}

function renderLegalBody(
  t: TFunction,
  kind: LegalPageKind,
  sectionKey: string,
  supportEmail: string,
) {
  const key = `legal.${kind}.sections.${sectionKey}`;
  const supportEmailLink = (
    <a
      className="font-medium text-black underline decoration-black/25 underline-offset-4 transition-colors hover:decoration-black dark:text-white dark:decoration-white/30 dark:hover:decoration-white"
      href={`mailto:${supportEmail}`}
    >
      {supportEmail}
    </a>
  );

  if (
    (kind === "terms" && sectionKey === "account_support") ||
    (kind === "privacy" && sectionKey === "your_controls")
  ) {
    return (
      <>
        {t(`${key}.body_before_email`)} {supportEmailLink}
        {t(`${key}.body_after_email`)}
      </>
    );
  }

  return t(`${key}.body`);
}
