"use client";

import { useTranslation } from "react-i18next";
import { Terminal } from "lucide-react";

export function DevModeBadge() {
  const { t } = useTranslation();
  const isMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH === "true";

  if (!isMockAuth) return null;

  return (
    <div className="fixed bottom-6 right-6 z-[200] animate-in fade-in slide-in-from-bottom-4 duration-1000">
      <div className="group flex items-center gap-2.5 rounded-full border border-blue-500/20 bg-white/80 px-4 py-2 text-blue-600 shadow-[0_8px_32px_rgba(0,0,0,0.08)] backdrop-blur-md transition-all hover:bg-white dark:border-blue-400/20 dark:bg-[#191c1f]/80 dark:text-blue-400 dark:hover:bg-[#191c1f]">
        <div className="relative flex h-2 w-2">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75"></span>
          <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500"></span>
        </div>
        <div className="flex items-center gap-1.5 overflow-hidden whitespace-nowrap">
          <Terminal className="h-3.5 w-3.5" />
          <span className="text-[12px] font-medium tracking-tight font-mono uppercase">
            Mock Auth Mode
          </span>
        </div>
      </div>
    </div>
  );
}
