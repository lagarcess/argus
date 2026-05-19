"use client";

import { Layout, LayoutPanelLeft, MousePointer2 } from "lucide-react";
import { useTranslation } from "react-i18next";

export type SidebarMode = "expanded" | "collapsed" | "hover";

type SidebarPreferenceModalProps = {
  mode: SidebarMode;
  onSelect: (mode: SidebarMode) => void;
  onClose: () => void;
};

/**
 * Centered blur modal for selecting Sidebar preference:
 * Expanded | Collapsed | Expand on Hover.
 */
export default function SidebarPreferenceModal({
  mode,
  onSelect,
  onClose,
}: SidebarPreferenceModalProps) {
  const { t } = useTranslation();

  const handleSelect = (newMode: SidebarMode) => {
    onSelect(newMode);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[70] bg-black/25 dark:bg-black/60 backdrop-blur-sm p-4 flex items-end sm:items-center justify-center animate-in fade-in duration-200">
      <button
        className="absolute inset-0"
        aria-label="Close sidebar preference modal"
        onClick={onClose}
      />
      <div className="relative w-full max-w-sm bg-white dark:bg-[#1b1d20] rounded-[18px] border border-black/5 dark:border-white/10 overflow-hidden p-3 shadow-2xl">
        <div className="mb-3 px-1">
          <h3 className="text-[14px] font-semibold text-black/90 dark:text-white/90">
            {t("settings.sidebar.title", "Sidebar Preference")}
          </h3>
          <p className="text-[12px] text-black/50 dark:text-white/50">
            {t("settings.sidebar.description", "Choose how the sidebar behaves.")}
          </p>
        </div>
        
        <div className="flex items-center justify-between p-1 bg-black/5 dark:bg-black/35 rounded-2xl">
          <button
            onClick={() => handleSelect("expanded")}
            className={`flex-1 flex flex-col items-center justify-center gap-1.5 py-3 rounded-xl transition-all ${
              mode === "expanded"
                ? "bg-white dark:bg-[#32363d] text-black dark:text-white shadow-sm"
                : "text-black/45 dark:text-white/45 hover:text-black dark:hover:text-white"
            }`}
          >
            <Layout className="w-[18px] h-[18px]" />
            <span className="text-[12px] font-medium">
              {t("settings.sidebar.expanded", "Expanded")}
            </span>
          </button>
          
          <button
            onClick={() => handleSelect("collapsed")}
            className={`flex-1 flex flex-col items-center justify-center gap-1.5 py-3 rounded-xl transition-all ${
              mode === "collapsed"
                ? "bg-white dark:bg-[#32363d] text-black dark:text-white shadow-sm"
                : "text-black/45 dark:text-white/45 hover:text-black dark:hover:text-white"
            }`}
          >
            <LayoutPanelLeft className="w-[18px] h-[18px]" />
            <span className="text-[12px] font-medium">
              {t("settings.sidebar.collapsed", "Icons Only")}
            </span>
          </button>
          
          <button
            onClick={() => handleSelect("hover")}
            className={`flex-1 flex flex-col items-center justify-center gap-1.5 py-3 rounded-xl transition-all ${
              mode === "hover"
                ? "bg-white dark:bg-[#32363d] text-black dark:text-white shadow-sm"
                : "text-black/45 dark:text-white/45 hover:text-black dark:hover:text-white"
            }`}
          >
            <MousePointer2 className="w-[18px] h-[18px]" />
            <span className="text-[12px] font-medium">
              {t("settings.sidebar.hover", "On Hover")}
            </span>
          </button>
        </div>
      </div>
    </div>
  );
}
