"use client";

import { useEffect, useRef, useState } from "react";
import {
  Languages,
  MessageSquareText,
  Monitor,
  Moon,
  Settings,
  Sun,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useTranslation } from "react-i18next";
import { useResponsiveLayout } from "@/components/layout/useResponsiveLayout";
import AdaptivePanel from "@/components/ui/AdaptivePanel";
import LanguageModal from "@/components/settings/LanguageModal";

/** Top bar on desktop; the drawer bottom below the mobile threshold (spec section 10). */
export type GuestSettingsPlacement = "top-bar" | "drawer";

export default function GuestSettingsMenu({
  feedbackEnabled,
  onFeedback,
  placement = "top-bar",
}: {
  feedbackEnabled: boolean;
  onFeedback: () => void;
  placement?: GuestSettingsPlacement;
}) {
  const isDrawerPlacement = placement === "drawer";
  const { isBelowDesktop } = useResponsiveLayout();
  // The last floating panel inside the drawer, and the only surface still
  // shaped like the settings menu that moved to the sheet. Small, so it hugs
  // its content rather than taking the screen.
  const asSheet = isBelowDesktop;
  const { t } = useTranslation();
  const { theme, setTheme } = useTheme();
  const [isOpen, setIsOpen] = useState(false);
  const [isLanguageModalOpen, setIsLanguageModalOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const gearButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!isOpen) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsOpen(false);
        requestAnimationFrame(() => gearButtonRef.current?.focus());
      }
    };
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const themeOptions = [
    {
      id: "light",
      label: t("settings.app.appearance_options.light", "Light"),
      icon: Sun,
    },
    {
      id: "dark",
      label: t("settings.app.appearance_options.dark", "Dark"),
      icon: Moon,
    },
    {
      id: "system",
      label: t("settings.app.appearance_options.system", "System"),
      icon: Monitor,
    },
  ] as const;

  const settingsBody = (
    <>
        <div
          className="grid grid-cols-3 gap-1 rounded-[14px] bg-black/[0.035] p-1 dark:bg-black/20"
          role="group"
          aria-label={t("settings.app.appearance", "Theme")}
        >
          {themeOptions.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setTheme(id)}
              className={`flex min-h-11 items-center justify-center rounded-[11px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/25 dark:focus-visible:ring-white/30 ${
                theme === id
                  ? "bg-black/[0.065] text-black dark:bg-white/[0.1] dark:text-white"
                  : "text-black/45 hover:bg-black/[0.035] hover:text-black dark:text-white/45 dark:hover:bg-white/[0.05] dark:hover:text-white"
              }`}
              aria-label={label}
              aria-pressed={theme === id}
            >
              <Icon className="h-[17px] w-[17px]" />
            </button>
          ))}
        </div>

        <div className="mt-2 space-y-0.5">
          <button
            type="button"
            onClick={() => {
              setIsOpen(false);
              setIsLanguageModalOpen(true);
            }}
            className="flex min-h-11 w-full items-center gap-3 rounded-[12px] px-3 text-left text-[14px] font-medium transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/25 dark:hover:bg-white/5 dark:focus-visible:ring-white/30"
            role="menuitem"
          >
            <Languages className="h-[17px] w-[17px] text-black/50 dark:text-white/50" />
            {t("guest.shell.language", "Language")}
          </button>
          {feedbackEnabled ? (
            <button
              type="button"
              onClick={() => {
                setIsOpen(false);
                onFeedback();
              }}
              className="flex min-h-11 w-full items-center gap-3 rounded-[12px] px-3 text-left text-[14px] font-medium transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/25 dark:hover:bg-white/5 dark:focus-visible:ring-white/30"
              role="menuitem"
            >
              <MessageSquareText className="h-[17px] w-[17px] text-black/50 dark:text-white/50" />
              {t("guest.shell.feedback", "Feedback")}
            </button>
          ) : null}
        </div>
    </>
  );

  return (
    <div className="relative" ref={menuRef} data-guest-settings-placement={placement}>
      <button
        ref={gearButtonRef}
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        className={
          isDrawerPlacement
            ? "flex min-h-11 w-full items-center gap-3 rounded-[12px] px-3 text-left text-[14px] font-medium transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black/25 dark:hover:bg-white/5 dark:focus-visible:ring-white/30"
            : "flex h-11 w-11 items-center justify-center rounded-full transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/25 dark:hover:bg-white/5 dark:focus-visible:ring-white/30"
        }
        aria-label={t("guest.shell.settings", "Guest settings")}
        aria-haspopup="menu"
        aria-expanded={isOpen}
      >
        <Settings className="h-[18px] w-[18px] shrink-0" />
        {isDrawerPlacement ? (
          <span className="truncate">{t("common.settings", "Settings")}</span>
        ) : null}
      </button>

      {isOpen && asSheet ? (
        <AdaptivePanel
          title={t("common.settings", "Settings")}
          closeLabel={t("common.close", "Close")}
          onClose={() => setIsOpen(false)}
          width="sm"
        >
          <div className="p-3">{settingsBody}</div>
        </AdaptivePanel>
      ) : null}

      {isOpen && !asSheet ? (
        <div
          className={
            isDrawerPlacement
              ? "absolute bottom-full left-0 mb-2 w-[min(280px,calc(100vw-3rem))] rounded-[18px] border border-black/8 bg-white p-2.5 text-black shadow-[0_16px_44px_rgba(15,23,42,0.13)] dark:border-white/10 dark:bg-[#1f2225] dark:text-white dark:shadow-[0_16px_44px_rgba(0,0,0,0.3)]"
              : "absolute left-1/2 top-full mt-2 w-[min(244px,calc(100vw-1.5rem))] -translate-x-1/2 rounded-[18px] border border-black/8 bg-white p-2.5 text-black shadow-[0_16px_44px_rgba(15,23,42,0.13)] mobile:left-auto mobile:right-0 mobile:translate-x-0 dark:border-white/10 dark:bg-[#1f2225] dark:text-white dark:shadow-[0_16px_44px_rgba(0,0,0,0.3)]"
          }
          role="menu"
          aria-label={t("guest.shell.settings", "Guest settings")}
        >
          {settingsBody}
        </div>
      ) : null}

      {isLanguageModalOpen ? (
        <LanguageModal
          persistProfile={false}
          onClose={() => {
            setIsLanguageModalOpen(false);
            requestAnimationFrame(() => gearButtonRef.current?.focus());
          }}
        />
      ) : null}
    </div>
  );
}
