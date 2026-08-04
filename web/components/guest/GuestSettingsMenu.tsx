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
import LanguageModal from "@/components/settings/LanguageModal";

export default function GuestSettingsMenu({
  feedbackEnabled,
  onFeedback,
}: {
  feedbackEnabled: boolean;
  onFeedback: () => void;
}) {
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

  return (
    <div className="relative" ref={menuRef}>
      <button
        ref={gearButtonRef}
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        className="flex h-11 w-11 items-center justify-center rounded-full transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/25 dark:hover:bg-white/5 dark:focus-visible:ring-white/30"
        aria-label={t("guest.shell.settings", "Guest settings")}
        aria-haspopup="menu"
        aria-expanded={isOpen}
      >
        <Settings className="h-[18px] w-[18px]" />
      </button>

      {isOpen ? (
        <div
          className="absolute left-1/2 top-full mt-2 w-[min(244px,calc(100vw-1.5rem))] -translate-x-1/2 rounded-[18px] border border-black/8 bg-white p-2.5 text-black shadow-[0_16px_44px_rgba(15,23,42,0.13)] sm:left-auto sm:right-0 sm:translate-x-0 dark:border-white/10 dark:bg-[#1f2225] dark:text-white dark:shadow-[0_16px_44px_rgba(0,0,0,0.3)]"
          role="menu"
          aria-label={t("guest.shell.settings", "Guest settings")}
        >
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
