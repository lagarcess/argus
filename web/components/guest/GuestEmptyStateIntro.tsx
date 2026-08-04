"use client";

import { useTranslation } from "react-i18next";

export default function GuestEmptyStateIntro() {
  const { t } = useTranslation();
  return (
    <div className="mb-5 max-w-xl text-center">
      <p className="font-display text-[22px] font-medium tracking-tight text-black/85 dark:text-white/85">
        {t(
          "guest.shell.value_title",
          "Test an investing idea against history.",
        )}
      </p>
    </div>
  );
}
