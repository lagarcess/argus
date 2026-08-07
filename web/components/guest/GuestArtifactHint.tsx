"use client";

import { useEffect, useState } from "react";
import { CheckCircle2, X } from "lucide-react";
import { useTranslation } from "react-i18next";
import { readStored, writeStored, type StorageKey } from "@/lib/browser-storage";

export type GuestArtifactHintKind = "confirmation" | "result";

const STORAGE_KEYS: Record<GuestArtifactHintKind, StorageKey> = {
  confirmation: "argus:guest-hint:confirmation:v1",
  result: "argus:guest-hint:result:v1",
};

export default function GuestArtifactHint({
  kind,
}: {
  kind: GuestArtifactHintKind;
}) {
  const { t } = useTranslation();
  const [isDismissed, setIsDismissed] = useState(true);

  useEffect(() => {
    setIsDismissed(readStored(STORAGE_KEYS[kind]) === "dismissed");
  }, [kind]);

  if (isDismissed) return null;

  return (
    <aside
      className="flex items-center gap-3 rounded-[14px] border border-[#70a38d]/20 bg-[#70a38d]/[0.07] px-3 py-2.5 text-[13px] text-[#3f6658] dark:border-[#9bc6b4]/18 dark:bg-[#9bc6b4]/[0.07] dark:text-[#b4d5c8]"
      data-testid={`guest-${kind}-hint`}
      aria-label={t(`guest.hints.${kind}`)}
    >
      <CheckCircle2 className="h-4 w-4 shrink-0" aria-hidden="true" />
      <p className="flex-1 leading-[1.45]">{t(`guest.hints.${kind}`)}</p>
      <button
        type="button"
        onClick={() => {
          setIsDismissed(true);
          writeStored(STORAGE_KEYS[kind], "dismissed");
        }}
        className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-current/60 transition-colors hover:bg-black/5 hover:text-current focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-current/25 dark:hover:bg-white/5"
        aria-label={t("guest.hints.dismiss", "Dismiss hint")}
      >
        <X className="h-4 w-4" />
      </button>
    </aside>
  );
}
