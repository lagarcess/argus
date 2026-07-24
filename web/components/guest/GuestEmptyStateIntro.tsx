"use client";

import { useTranslation } from "react-i18next";

export default function GuestEmptyStateIntro() {
  const { t } = useTranslation();
  return (
    <div className="mb-6 max-w-xl text-center">
      <p className="font-display text-[22px] font-medium tracking-tight text-black/85 dark:text-white/85">
        {t(
          "guest.shell.value_title",
          "Test an investing idea against history.",
        )}
      </p>
      <p className="mx-auto mt-2 max-w-lg text-[15px] leading-[1.55] text-black/50 dark:text-white/50">
        {t(
          "guest.shell.value_body",
          "Describe your idea naturally. Argus will clarify the setup, show what it can test, and run a historical simulation.",
        )}
      </p>
    </div>
  );
}
