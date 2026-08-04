"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "react-i18next";

export default function GuestEntry() {
  const { t } = useTranslation();
  const router = useRouter();

  useEffect(() => {
    router.replace("/chat");
  }, [router]);

  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-background px-6 text-foreground">
      <div
        aria-label={t("guest.entry.loading", "Opening Argus")}
        className="h-8 w-8 animate-spin rounded-full border-2 border-current border-t-transparent"
        role="status"
      />
    </main>
  );
}
