"use client";

import { useTranslation } from "react-i18next";
import { Terminal, RefreshCw } from "lucide-react";
import { patchMe } from "@/lib/argus-api";
import { useRouter } from "next/navigation";

export function DevModeBadge() {
  const { t } = useTranslation();
  const router = useRouter();
  const isMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";

  const handleResetOnboarding = async () => {
    try {
      await patchMe({
        onboarding: {
          completed: false,
          stage: "language_selection",
          language_confirmed: false,
          primary_goal: null
        }
      });
      window.location.reload();
    } catch (err) {
      console.error("Failed to reset onboarding:", err);
    }
  };

  if (!isMockAuth) return null;

  return (
    <div className="fixed bottom-6 right-6 z-[200] animate-in fade-in slide-in-from-bottom-4 duration-1000 flex flex-col items-end gap-3">
      <button
        onClick={handleResetOnboarding}
        className="flex items-center gap-2 rounded-full border border-black/5 bg-white/80 px-4 py-2 text-[12px] font-medium text-black/60 backdrop-blur-md transition-all hover:bg-white hover:text-black dark:border-white/5 dark:bg-[#191c1f]/80 dark:text-white/60 dark:hover:bg-[#191c1f] dark:hover:text-white"
      >
        <RefreshCw className="h-3.5 w-3.5" />
        Reset Onboarding
      </button>

      <div className="flex items-center gap-2 rounded-full border border-black/5 bg-white/80 px-4 py-2 text-[12px] font-medium text-black/60 backdrop-blur-md transition-all hover:bg-white hover:text-black dark:border-white/5 dark:bg-[#191c1f]/80 dark:text-white/60 dark:hover:bg-[#191c1f] dark:hover:text-white">
        <div className="flex h-1.5 w-1.5 rounded-full bg-black/20 dark:bg-white/20" />
        <div className="flex items-center gap-1.5 overflow-hidden whitespace-nowrap">
          <Terminal className="h-3.5 w-3.5" />
          <span className="tracking-tight">
            Mock Auth Mode
          </span>
        </div>
      </div>
    </div>
  );
}
