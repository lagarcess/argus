"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { Check, Search } from "lucide-react";
import { useTranslation } from "react-i18next";
import { patchMe } from "@/lib/argus-api";
import { useModalSurface } from "@/components/layout/useModalSurface";
import {
  ENABLED_LANGUAGES,
  localeForLanguage,
  normalizeEnabledLanguage,
} from "@/lib/language-features";

type LanguageModalProps = {
  onClose: () => void;
  persistProfile?: boolean;
};

/**
 * Centered blur modal with search + language list.
 * Extracted from SettingsView for reuse in ProfileMenu.
 */
export default function LanguageModal({
  onClose,
  persistProfile = true,
}: LanguageModalProps) {
  const overlayId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  // Reachable from the drawer, so it must own Escape, focus, and system back
  // or dismissing it takes the drawer underneath with it.
  //
  // The container is the full-screen wrapper, whose first focusable child is
  // the invisible backdrop dismiss button. Without naming the field, keyboard
  // users opened straight onto an undisclosed close control where Enter shut
  // the modal.
  useModalSurface({
    isOpen: true,
    overlayId,
    containerRef: panelRef,
    onDismiss: onClose,
    onEscape: onClose,
    initialFocusRef: searchInputRef,
  });
  const { t, i18n } = useTranslation();
  const [searchQuery, setSearchQuery] = useState("");
  const lang = i18n.language || "en";

  const filteredLanguages = useMemo(
    () =>
      ENABLED_LANGUAGES.filter(
        (entry) =>
          entry.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          entry.translation.toLowerCase().includes(searchQuery.toLowerCase()),
      ),
    [searchQuery],
  );

  useEffect(() => {
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previousOverflow;
    };
  }, []);

  const handleSelect = async (code: string) => {
    const nextLanguage = normalizeEnabledLanguage(code);
    await i18n.changeLanguage(nextLanguage);
    onClose();
    if (persistProfile) {
      try {
        await patchMe({
          language: nextLanguage,
          locale: localeForLanguage(nextLanguage),
        });
      } catch {
        // Keep the immediate browser-language change if profile persistence fails.
      }
    }
  };

  return (
    <div
      ref={panelRef}
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/25 p-4 backdrop-blur-sm dark:bg-black/60"
      role="dialog"
      aria-modal="true"
      aria-label={t("guest.shell.language", "Language")}
    >
      <button
        tabIndex={-1}
        className="absolute inset-0"
        aria-label={t("settings.app.close_language_modal", "Close language modal")}
        onClick={() => {
          onClose();
          setSearchQuery("");
        }}
      />
      <div className="relative w-full max-w-sm overflow-hidden rounded-[18px] border border-black/5 bg-white dark:border-white/10 dark:bg-[#111111]">
        <div className="flex items-center px-4 py-3 border-b border-black/5 dark:border-white/5">
          <Search className="w-4 h-4 text-black/40 dark:text-white/40 mr-3" />
          <input
            ref={searchInputRef}
            type="text"
            autoFocus
            placeholder={t("settings.search_language")}
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            className="w-full bg-transparent border-none outline-none text-[15px] text-black dark:text-white placeholder:text-black/35 dark:placeholder:text-white/35"
          />
        </div>
        <div className="max-h-[340px] overflow-y-auto py-1">
          {filteredLanguages.length === 0 ? (
            <div className="px-4 py-8 text-center text-[14px] text-black/45 dark:text-white/45">
              {t("settings.no_languages")}
            </div>
          ) : (
            filteredLanguages.map((entry) => (
              <button
                key={entry.code}
                type="button"
                onClick={() => void handleSelect(entry.code)}
                className="w-full flex items-center justify-between px-4 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                <span className="text-[15px] font-medium text-black dark:text-white">
                  {entry.name}
                </span>
                {entry.code === normalizeEnabledLanguage(lang) ? (
                  <Check className="w-4 h-4 text-black dark:text-white" />
                ) : (
                  <span className="text-[14px] text-black/45 dark:text-white/45">
                    {entry.translation}
                  </span>
                )}
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
