"use client";

import { Layout, LayoutPanelLeft, MousePointer2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import AdaptivePanel from "@/components/ui/AdaptivePanel";

export type SidebarMode = "expanded" | "collapsed" | "hover";

type SidebarPreferenceModalProps = {
  mode: SidebarMode;
  onSelect: (mode: SidebarMode) => void;
  onClose: () => void;
  onBack?: () => void;
  backLabel?: string;
};

/**
 * Centered blur modal for selecting Sidebar preference:
 * Expanded | Collapsed | Expand on Hover.
 */
export default function SidebarPreferenceModal({
  mode,
  onSelect,
  onClose,
  onBack,
  backLabel,
}: SidebarPreferenceModalProps) {
  const { t } = useTranslation();

  const handleSelect = (newMode: SidebarMode) => {
    onSelect(newMode);
    onClose();
  };

  return (
    <AdaptivePanel
      title={t("settings.sidebar.title")}
      closeLabel={t("settings.sidebar.close")}
      onClose={onClose}
      onBack={onBack}
      backLabel={backLabel}
      width="sm"
    >
      <p className="px-5 pt-3 text-[12px] text-black/50 dark:text-white/50">
        {t("settings.sidebar.description")}
      </p>
      <div className="p-3">
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
              {t("settings.sidebar.expanded")}
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
              {t("settings.sidebar.collapsed")}
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
              {t("settings.sidebar.hover")}
            </span>
          </button>
        </div>
      </div>
    </AdaptivePanel>
  );
}
