"use client";

import { useTheme } from "next-themes";
import { Sun, Moon, Monitor } from "lucide-react";
import { useTranslation } from "react-i18next";
import AdaptivePanel from "@/components/ui/AdaptivePanel";
import { patchMe } from "@/lib/argus-api";

type AppearanceModalProps = {
  onClose: () => void;
  /** Present when opened from a parent panel, so back returns rather than closes. */
  onBack?: () => void;
  backLabel?: string;
};

/** Segmented Light / Dark / System. The shell decides sheet or dialog. */
export default function AppearanceModal({
  onClose,
  onBack,
  backLabel,
}: AppearanceModalProps) {
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
    <AdaptivePanel
      title={t("settings.app.appearance", "Appearance")}
      closeLabel={t("settings.app.close_appearance", "Close appearance")}
      onClose={onClose}
      onBack={onBack}
      backLabel={backLabel}
      width="sm"
    >
      <div className="p-3">
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
    </AdaptivePanel>
  );
}
