"use client";

import { useTheme } from "next-themes";
import { Sun, Moon, Monitor } from "lucide-react";
import { useTranslation } from "react-i18next";
import { patchMe } from "@/lib/argus-api";

type AppearanceModalProps = {
  onClose: () => void;
};

/**
 * Centered blur modal with segmented pill toggle for Light / Dark / System.
 * Extracted from SettingsView for reuse in ProfileMenu.
 */
export default function AppearanceModal({ onClose }: AppearanceModalProps) {
  const { t } = useTranslation();
  const { theme, setTheme } = useTheme();

  const handleSelect = (newTheme: "light" | "dark" | "system") => {
    setTheme(newTheme);
    onClose();
    void patchMe({ theme: newTheme }).catch(() => {
      // Silently ignore if not logged in
    });
  };

  return (
    <div className="fixed inset-0 z-[70] bg-black/25 dark:bg-black/60 backdrop-blur-sm p-4 flex items-end sm:items-center justify-center">
      <button
        className="absolute inset-0"
        aria-label="Close appearance modal"
        onClick={onClose}
      />
      <div className="relative w-full max-w-sm bg-white dark:bg-[#1b1d20] rounded-[18px] border border-black/5 dark:border-white/10 overflow-hidden p-3">
        <div className="flex items-center justify-between p-1 bg-black/5 dark:bg-black/35 rounded-2xl">
          <button
            onClick={() => handleSelect("light")}
            className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl transition-colors ${
              theme === "light"
                ? "bg-white text-black"
                : "text-black/45 dark:text-white/45 hover:text-black dark:hover:text-white"
            }`}
          >
            <Sun className="w-[16px] h-[16px]" />
            <span className="text-[14px] font-medium">
              {t("settings.app.appearance_options.light")}
            </span>
          </button>
          <button
            onClick={() => handleSelect("dark")}
            className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl transition-colors ${
              theme === "dark"
                ? "bg-white dark:bg-[#32363d] text-black dark:text-white"
                : "text-black/45 dark:text-white/45 hover:text-black dark:hover:text-white"
            }`}
          >
            <Moon className="w-[16px] h-[16px]" />
            <span className="text-[14px] font-medium">
              {t("settings.app.appearance_options.dark")}
            </span>
          </button>
          <button
            onClick={() => handleSelect("system")}
            className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl transition-colors ${
              theme === "system"
                ? "bg-white dark:bg-[#32363d] text-black dark:text-white"
                : "text-black/45 dark:text-white/45 hover:text-black dark:hover:text-white"
            }`}
          >
            <Monitor className="w-[16px] h-[16px]" />
            <span className="text-[14px] font-medium">
              {t("settings.app.appearance_options.system")}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
