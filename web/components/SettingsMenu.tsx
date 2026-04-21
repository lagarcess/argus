"use client";

import { useEffect, useState, useRef } from "react";
import { useTheme } from "next-themes";
import { Settings, Sun, Moon, Monitor, Search, Check } from "lucide-react";

const LANGUAGES = [
  { code: "en", name: "English", translation: "English" },
  { code: "es-LA", name: "Español", translation: "Spanish" }
];

export function SettingsMenu() {
  const [mounted, setMounted] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const [isLanguageModalOpen, setIsLanguageModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const { theme, setTheme } = useTheme();

  const [lang, setLang] = useState("en");

  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMounted(true);

    function handleClickOutside(event: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Prevent background scrolling when modal is open
  useEffect(() => {
    if (isLanguageModalOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }
    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [isLanguageModalOpen]);

  if (!mounted) return null;

  const currentLangLabel = LANGUAGES.find(l => l.code === lang)?.name || "English";
  const filteredLanguages = LANGUAGES.filter(l =>
    l.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    l.translation.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <>
      <div className="hidden md:block absolute top-6 right-6 md:top-8 md:right-12 z-40 text-[var(--color-argus-fg)]" ref={popoverRef}>
        <button
          onClick={() => setIsOpen(!isOpen)}
          className="p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 transition-colors outline-none focus-visible:ring-2 focus-visible:ring-black dark:focus-visible:ring-white"
          aria-label="Settings"
        >
          <Settings className="w-6 h-6 stroke-[1.5]" />
        </button>

        {isOpen && (
          <div className="absolute right-0 mt-2 w-64 p-3 rounded-[24px] bg-[#f5f5f5] dark:bg-[#1c1f24] border border-black/5 dark:border-white/5 shadow-2xl overflow-hidden text-sm animate-in fade-in zoom-in-95 duration-100 origin-top-right">

            {/* Theme Row */}
            <div className="flex items-center justify-between p-1 bg-black/5 dark:bg-black/40 rounded-2xl mb-3 relative">
              <button
                onClick={() => setTheme('light')}
                className={`flex-1 flex justify-center py-2.5 rounded-xl z-10 transition-colors ${theme === 'light' ? 'bg-white text-black shadow-sm' : 'text-gray-500 hover:text-black dark:hover:text-white'}`}
              >
                <Sun className="w-[18px] h-[18px] stroke-[2]" />
              </button>
              <button
                onClick={() => setTheme('dark')}
                className={`flex-1 flex justify-center py-2.5 rounded-xl z-10 transition-colors ${theme === 'dark' ? 'dark:bg-[#32363d] bg-white text-black dark:text-white shadow-sm' : 'text-gray-500 hover:text-black dark:hover:text-white'}`}
              >
                <Moon className="w-[18px] h-[18px] stroke-[2]" />
              </button>
              <button
                onClick={() => setTheme('system')}
                className={`flex-1 flex justify-center py-2.5 rounded-xl z-10 transition-colors ${theme === 'system' ? 'dark:bg-[#32363d] bg-white text-black dark:text-white shadow-sm' : 'text-gray-500 hover:text-black dark:hover:text-white'}`}
              >
                <Monitor className="w-[18px] h-[18px] stroke-[2]" />
              </button>
            </div>

            {/* Language Setting Row */}
            <button
              onClick={() => { setIsLanguageModalOpen(true); setIsOpen(false); }}
              className="w-full flex items-center justify-between px-3 py-2.5 rounded-xl transition-colors hover:bg-black/5 dark:hover:bg-white/5"
            >
              <span className="font-medium text-[15px] text-black dark:text-white tracking-tight">Language</span>
              <span className="text-[14px] text-gray-500 dark:text-gray-400">{currentLangLabel}</span>
            </button>
          </div>
        )}
      </div>

      {/* Language Search Modal */}
      {isLanguageModalOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/20 dark:bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
          {/* Modal Backdrop overlay to click outside */}
          <div className="absolute inset-0" onClick={() => setIsLanguageModalOpen(false)} />

          {/* Modal Content */}
          <div className="relative w-full max-w-sm bg-white dark:bg-[#111111] rounded-[16px] shadow-2xl border border-black/5 dark:border-white/10 overflow-hidden flex flex-col animate-in zoom-in-95 duration-200" role="dialog" aria-modal="true" aria-label="Select Language">

            {/* Search Input */}
            <div className="flex items-center px-4 py-3 border-b border-black/5 dark:border-white/5">
              <Search className="w-4 h-4 text-gray-400 dark:text-gray-500 mr-3" />
              <input
                type="text"
                placeholder="Search language"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                autoFocus
                className="flex-1 bg-transparent border-none outline-none text-[15px] text-black dark:text-white placeholder-gray-400 dark:placeholder-gray-500"
              />
            </div>

            {/* Language List */}
            <div className="flex flex-col py-2 max-h-[400px] overflow-y-auto">
              {filteredLanguages.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-gray-500">No languages found.</div>
              ) : (
                filteredLanguages.map((l) => (
                  <button
                    key={l.code}
                    onClick={() => { setLang(l.code); setIsLanguageModalOpen(false); setSearchQuery(""); }}
                    className="flex justify-between items-center px-4 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                  >
                    <span className="font-medium text-[15px] text-black dark:text-white">{l.name}</span>
                    {lang === l.code ? (
                      <Check className="w-4 h-4 text-black dark:text-white" />
                    ) : (
                      <span className="text-[14px] text-gray-500">{l.translation}</span>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
