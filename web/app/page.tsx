"use client";

import Link from "next/link";
import { SettingsMenu } from "@/components/SettingsMenu";
import { useTranslation } from "react-i18next";
import { OnboardingGate } from "@/components/onboarding/OnboardingGate";

export default function LandingPage() {
  const { t } = useTranslation();

  return (
    <OnboardingGate postCompleteHref="/chat">
      <main className="relative flex min-h-[100dvh] w-full flex-col justify-between overflow-hidden px-6 py-8 md:px-12">
        <SettingsMenu />
        {/* ... rest of the code ... */}
        <div className="flex flex-grow items-center justify-center">
          <h1 className="text-6xl md:text-[80px] font-medium tracking-tight text-black dark:text-white z-10 select-none transition-colors">
            argus
          </h1>
        </div>

        <div className="relative z-10 flex w-full flex-col items-center gap-6 pb-2 md:pb-4">
          <Link href="/chat" className="w-full max-w-sm rounded-[9999px] bg-black text-white dark:bg-white dark:text-black px-[32px] py-[14px] text-[16px] font-medium transition-opacity hover:opacity-85 focus:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black dark:focus-visible:ring-white flex items-center justify-center">
            {t('landing.sign_up_email')}
          </Link>
          <p className="text-[16px] tracking-wide text-gray-500 dark:text-gray-400">
            {t('landing.already_account')}{" "}
            <Link
              className="font-medium text-black dark:text-white transition-opacity hover:opacity-80"
              href="/login"
            >
              {t('landing.sign_in')}
            </Link>
          </p>

          <p className="mt-4 w-full px-4 text-center text-[11px] md:text-[12px] text-zinc-500 tracking-tight">
            {t('landing.legal_prefix')}{" "}
            <a href="#" className="font-semibold text-zinc-800 dark:text-zinc-400 hover:text-black dark:hover:text-white transition-colors">
              {t('landing.terms')}
            </a>{" "}
            {t('common.and', 'and')}{" "}
            <a href="#" className="font-semibold text-zinc-800 dark:text-zinc-400 hover:text-black dark:hover:text-white transition-colors">
              {t('landing.privacy')}
            </a>.
          </p>
        </div>
      </main>
    </OnboardingGate>
  );
}
