"use client";

import { useMemo, useState } from "react";
import { useTheme } from "next-themes";
import { X, ChevronRight, User, LogOut, Sun, Moon, Monitor, Search, Check } from "lucide-react";

const LANGUAGES = [
  { code: "en", name: "English", translation: "English" },
  { code: "es-LA", name: "Español", translation: "Spanish" },
];

type SettingsViewProps = {
  onClose: () => void;
  onLogout: () => void;
};

export default function SettingsView({ onClose, onLogout }: SettingsViewProps) {
  const { theme, setTheme } = useTheme();
  const [isLanguageModalOpen, setIsLanguageModalOpen] = useState(false);
  const [isAppearanceModalOpen, setIsAppearanceModalOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [lang, setLang] = useState<string>(() => {
    if (typeof window === "undefined") return "en";
    return localStorage.getItem("argus-language") ?? "en";
  });

  const currentLangLabel = useMemo(
    () => LANGUAGES.find((entry) => entry.code === lang)?.name ?? "English",
    [lang],
  );

  const filteredLanguages = useMemo(
    () =>
      LANGUAGES.filter(
        (entry) =>
          entry.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          entry.translation.toLowerCase().includes(searchQuery.toLowerCase()),
      ),
    [searchQuery],
  );

  const setLanguage = (nextLanguage: string) => {
    setLang(nextLanguage);
    if (typeof window !== "undefined") {
      localStorage.setItem("argus-language", nextLanguage);
    }
    setIsLanguageModalOpen(false);
    setSearchQuery("");
  };

  const appearanceLabel = theme === "light" ? "Light" : theme === "dark" ? "Dark" : "System";

  return (
    <div className="flex flex-col w-full h-[100dvh] max-w-3xl mx-auto overflow-hidden bg-[#f9f9f9] dark:bg-[#141517] relative font-space">
      {/* Header */}
      <div className="absolute top-0 inset-x-0 h-28 z-30 pointer-events-none backdrop-blur-[8px] bg-[#f5f5f5]/10 dark:bg-[#191c1f]/20 [mask-image:linear-gradient(to_bottom,black_30%,transparent_100%)] [-webkit-mask-image:linear-gradient(to_bottom,black_30%,transparent_100%)]" />

      <div className="absolute top-6 inset-x-0 w-full flex justify-center z-[35] pointer-events-none">
        <h1 className="text-[18px] font-medium tracking-tight pointer-events-auto">Settings</h1>
      </div>

      <div className="absolute top-4 right-4 z-[35]">
        <button 
          onClick={onClose} 
          className="flex items-center justify-center p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 transition-colors text-black dark:text-white border border-black/10 dark:border-white/10"
        >
          <X className="w-5 h-5" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 pt-24 pb-32 relative z-10 w-full max-w-md mx-auto">
        <div className="flex flex-col gap-6 w-full">
          
          {/* Profile Section */}
          <button className="flex items-center justify-between p-4 bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 rounded-[20px] shadow-sm hover:opacity-80 transition-opacity text-left w-full">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-full bg-[#f4e8ff] dark:bg-[#342442] flex items-center justify-center border border-black/5 dark:border-white/5 shrink-0">
                <User className="w-6 h-6 text-[#9a66d9] dark:text-[#d3a8fc]" />
              </div>
              <div className="flex flex-col">
                <span className="text-[16px] font-medium text-black dark:text-white">Display Name</span>
                <span className="text-[14px] text-black/50 dark:text-white/50">user-name</span>
                <span className="text-[14px] text-black/50 dark:text-white/50">email@example.com</span>
              </div>
            </div>
            <ChevronRight className="w-5 h-5 text-black/40 dark:text-white/40" />
          </button>

          {/* Subscription */}
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-medium text-black/40 dark:text-white/40 px-2">Subscription</span>
            <button className="w-full py-4 px-4 bg-[#f4e8ff]/80 dark:bg-[#342442]/80 border border-[#9a66d9]/20 dark:border-[#d3a8fc]/20 rounded-[16px] shadow-sm hover:opacity-80 transition-opacity text-center flex items-center justify-center">
              <span className="text-[15px] font-medium text-[#7e47be] dark:text-[#e4c4fd]">Try upgrading to Pro for Free</span>
            </button>
          </div>

          {/* App */}
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-medium text-black/40 dark:text-white/40 px-2">App</span>
            <div className="flex flex-col bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 rounded-[16px] shadow-sm overflow-hidden">
              <button
                onClick={() => setIsLanguageModalOpen(true)}
                className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5"
              >
                <span className="text-[15px] text-black dark:text-white font-medium">App language</span>
                <div className="flex items-center gap-2">
                  <span className="text-[14px] text-black/40 dark:text-white/40">{currentLangLabel}</span>
                  <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
                </div>
              </button>
              <button
                onClick={() => setIsAppearanceModalOpen(true)}
                className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                <span className="text-[15px] text-black dark:text-white font-medium">Appearance</span>
                <div className="flex items-center gap-2">
                  <span className="text-[14px] text-black/40 dark:text-white/40">{appearanceLabel}</span>
                  <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
                </div>
              </button>
            </div>
          </div>

          {/* Data & Information */}
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-medium text-black/40 dark:text-white/40 px-2">Data & Information</span>
            <div className="flex flex-col bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 rounded-[16px] shadow-sm overflow-hidden">
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5">
                <span className="text-[15px] text-black dark:text-white font-medium">Archived chats</span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5">
                <span className="text-[15px] text-black dark:text-white font-medium">Recently deleted</span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                <span className="text-[15px] text-black dark:text-white font-medium">Security</span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
            </div>
          </div>

          {/* About */}
          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-medium text-black/40 dark:text-white/40 px-2">About</span>
            <div className="flex flex-col bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 rounded-[16px] shadow-sm overflow-hidden">
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5">
                <span className="text-[15px] text-black dark:text-white font-medium">Report a bug</span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5">
                <span className="text-[15px] text-black dark:text-white font-medium">Request a feature</span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                <span className="text-[15px] text-black dark:text-white font-medium">General feedback</span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
            </div>
          </div>

          {/* Log out */}
          <button 
            onClick={onLogout}
            className="w-[140px] mt-2 py-3 px-4 bg-red-400/20 dark:bg-red-500/10 border border-red-500/20 rounded-[12px] shadow-sm hover:opacity-80 transition-opacity text-center flex items-center justify-center gap-2"
          >
            <LogOut className="w-4 h-4 text-red-600 dark:text-red-400" />
            <span className="text-[14px] font-medium text-red-600 dark:text-red-400">Log out</span>
          </button>
          
        </div>
      </div>

      {isLanguageModalOpen && (
        <div className="absolute inset-0 z-[70] bg-black/25 dark:bg-black/60 backdrop-blur-sm p-4 flex items-center justify-center">
          <button
            className="absolute inset-0"
            aria-label="Close language modal"
            onClick={() => {
              setIsLanguageModalOpen(false);
              setSearchQuery("");
            }}
          />
          <div className="relative w-full max-w-sm bg-white dark:bg-[#111111] rounded-[18px] border border-black/5 dark:border-white/10 overflow-hidden shadow-2xl">
            <div className="flex items-center px-4 py-3 border-b border-black/5 dark:border-white/5">
              <Search className="w-4 h-4 text-black/40 dark:text-white/40 mr-3" />
              <input
                type="text"
                autoFocus
                placeholder="Search language"
                value={searchQuery}
                onChange={(event) => setSearchQuery(event.target.value)}
                className="w-full bg-transparent border-none outline-none text-[15px] text-black dark:text-white placeholder:text-black/35 dark:placeholder:text-white/35"
              />
            </div>
            <div className="max-h-[340px] overflow-y-auto py-1">
              {filteredLanguages.length === 0 ? (
                <div className="px-4 py-8 text-center text-[14px] text-black/45 dark:text-white/45">
                  No languages found.
                </div>
              ) : (
                filteredLanguages.map((entry) => (
                  <button
                    key={entry.code}
                    onClick={() => setLanguage(entry.code)}
                    className="w-full flex items-center justify-between px-4 py-3 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
                  >
                    <span className="text-[15px] font-medium text-black dark:text-white">{entry.name}</span>
                    {entry.code === lang ? (
                      <Check className="w-4 h-4 text-black dark:text-white" />
                    ) : (
                      <span className="text-[14px] text-black/45 dark:text-white/45">{entry.translation}</span>
                    )}
                  </button>
                ))
              )}
            </div>
          </div>
        </div>
      )}

      {isAppearanceModalOpen && (
        <div className="absolute inset-0 z-[70] bg-black/25 dark:bg-black/60 backdrop-blur-sm p-4 flex items-end sm:items-center justify-center">
          <button
            className="absolute inset-0"
            aria-label="Close appearance modal"
            onClick={() => setIsAppearanceModalOpen(false)}
          />
          <div className="relative w-full max-w-sm bg-white dark:bg-[#1b1d20] rounded-[18px] border border-black/5 dark:border-white/10 overflow-hidden shadow-2xl p-3">
            <div className="flex items-center justify-between p-1 bg-black/5 dark:bg-black/35 rounded-2xl">
              <button
                onClick={() => { setTheme("light"); setIsAppearanceModalOpen(false); }}
                className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl transition-colors ${theme === "light" ? "bg-white text-black shadow-sm" : "text-black/45 dark:text-white/45 hover:text-black dark:hover:text-white"}`}
              >
                <Sun className="w-[16px] h-[16px]" />
                <span className="text-[14px] font-medium">Light</span>
              </button>
              <button
                onClick={() => { setTheme("dark"); setIsAppearanceModalOpen(false); }}
                className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl transition-colors ${theme === "dark" ? "bg-white dark:bg-[#32363d] text-black dark:text-white shadow-sm" : "text-black/45 dark:text-white/45 hover:text-black dark:hover:text-white"}`}
              >
                <Moon className="w-[16px] h-[16px]" />
                <span className="text-[14px] font-medium">Dark</span>
              </button>
              <button
                onClick={() => { setTheme("system"); setIsAppearanceModalOpen(false); }}
                className={`flex-1 flex items-center justify-center gap-2 py-3 rounded-xl transition-colors ${theme === "system" ? "bg-white dark:bg-[#32363d] text-black dark:text-white shadow-sm" : "text-black/45 dark:text-white/45 hover:text-black dark:hover:text-white"}`}
              >
                <Monitor className="w-[16px] h-[16px]" />
                <span className="text-[14px] font-medium">System</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
