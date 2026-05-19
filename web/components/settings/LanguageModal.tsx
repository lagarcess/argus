"use client";

import { useMemo, useState } from "react";
import { Check, Search } from "lucide-react";
import { useTranslation } from "react-i18next";
import { patchMe } from "@/lib/argus-api";
import { ENABLED_LANGUAGES, normalizeEnabledLanguage } from "@/lib/language-features";

type LanguageModalProps = {
  onClose: () => void;
};

/**
 * Centered blur modal with search + language list.
 * Extracted from SettingsView for reuse in ProfileMenu.
 */
export default function LanguageModal({ onClose }: LanguageModalProps) {
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

  const handleSelect = async (code: string) => {
    await i18n.changeLanguage(code);
    onClose();
    try {
      await patchMe({ language: normalizeEnabledLanguage(code) });
    } catch {
      // Silently ignore if not logged in
    }
  };

  return (
    <div className="fixed inset-0 z-[70] bg-black/25 dark:bg-black/60 backdrop-blur-sm p-4 flex items-center justify-center">
      <button
        className="absolute inset-0"
        aria-label="Close language modal"
        onClick={() => {
          onClose();
          setSearchQuery("");
        }}
      />
      <div className="relative w-full max-w-sm bg-white dark:bg-[#111111] rounded-[18px] border border-black/5 dark:border-white/10 overflow-hidden">
        <div className="flex items-center px-4 py-3 border-b border-black/5 dark:border-white/5">
          <Search className="w-4 h-4 text-black/40 dark:text-white/40 mr-3" />
          <input
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
