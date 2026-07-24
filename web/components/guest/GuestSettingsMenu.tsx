"use client";

import { useEffect, useRef, useState } from "react";
import { Check, MessageSquareText, Monitor, Moon, Settings, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useTranslation } from "react-i18next";
import {
  ENABLED_LANGUAGES,
  normalizeEnabledLanguage,
} from "@/lib/language-features";

export default function GuestSettingsMenu({
  onFeedback,
}: {
  onFeedback: () => void;
}) {
  const { t, i18n } = useTranslation();
  const { theme, setTheme } = useTheme();
  const [isOpen, setIsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const language = normalizeEnabledLanguage(
    i18n.resolvedLanguage ?? i18n.language,
  );

  useEffect(() => {
    if (!isOpen) return;
    const handlePointerDown = (event: MouseEvent) => {
      if (!menuRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setIsOpen(false);
    };
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [isOpen]);

  const themeOptions = [
    { id: "light", label: t("settings.appearance.light", "Light"), icon: Sun },
    { id: "dark", label: t("settings.appearance.dark", "Dark"), icon: Moon },
    { id: "system", label: t("settings.appearance.system", "System"), icon: Monitor },
  ] as const;

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={() => setIsOpen((open) => !open)}
        className="flex h-11 w-11 items-center justify-center rounded-full transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/25 dark:hover:bg-white/5 dark:focus-visible:ring-white/30"
        aria-label={t("guest.shell.settings", "Guest settings")}
        aria-haspopup="menu"
        aria-expanded={isOpen}
      >
        <Settings className="h-5 w-5" />
      </button>

      {isOpen ? (
        <div
          className="absolute right-0 top-full mt-2 w-[min(300px,calc(100vw-2rem))] rounded-[20px] border border-black/8 bg-white p-3 text-black shadow-[0_18px_50px_rgba(15,23,42,0.14)] dark:border-white/10 dark:bg-[#1f2225] dark:text-white dark:shadow-[0_18px_50px_rgba(0,0,0,0.32)]"
          role="menu"
          aria-label={t("guest.shell.settings", "Guest settings")}
        >
          <p className="px-2 pb-2 text-[12px] font-semibold uppercase tracking-[0.12em] text-black/40 dark:text-white/40">
            {t("settings.appearance.title", "Theme")}
          </p>
          <div className="grid grid-cols-3 gap-1 rounded-[14px] bg-black/[0.04] p-1 dark:bg-black/25">
            {themeOptions.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                type="button"
                onClick={() => setTheme(id)}
                className={`flex min-h-11 items-center justify-center rounded-[11px] transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/25 dark:focus-visible:ring-white/30 ${
                  theme === id
                    ? "bg-white text-black shadow-sm dark:bg-[#34383d] dark:text-white"
                    : "text-black/50 hover:text-black dark:text-white/50 dark:hover:text-white"
                }`}
                aria-label={label}
                aria-pressed={theme === id}
              >
                <Icon className="h-[18px] w-[18px]" />
              </button>
            ))}
          </div>

          <p className="px-2 pb-2 pt-4 text-[12px] font-semibold uppercase tracking-[0.12em] text-black/40 dark:text-white/40">
            {t("settings.app.language", "Language")}
          </p>
          <div className="space-y-1">
            {ENABLED_LANGUAGES.map((option) => (
              <button
                key={option.code}
                type="button"
                onClick={async () => {
                  await i18n.changeLanguage(option.code);
                  setIsOpen(false);
                }}
                className="flex min-h-11 w-full items-center justify-between rounded-[12px] px-3 text-left text-[14px] font-medium transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/25 dark:hover:bg-white/5 dark:focus-visible:ring-white/30"
                role="menuitemradio"
                aria-checked={language === option.code}
              >
                <span>{option.name}</span>
                {language === option.code ? <Check className="h-4 w-4" /> : null}
              </button>
            ))}
          </div>

          <div className="my-2 h-px bg-black/6 dark:bg-white/8" />
          <button
            type="button"
            onClick={() => {
              setIsOpen(false);
              onFeedback();
            }}
            className="flex min-h-11 w-full items-center gap-3 rounded-[12px] px-3 text-left text-[14px] font-medium transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-black/25 dark:hover:bg-white/5 dark:focus-visible:ring-white/30"
            role="menuitem"
          >
            <MessageSquareText className="h-[18px] w-[18px] text-black/55 dark:text-white/55" />
            {t("guest.shell.feedback", "Feedback")}
          </button>
        </div>
      ) : null}
    </div>
  );
}
