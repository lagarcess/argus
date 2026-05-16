"use client";

import { useEffect, useMemo, useState } from "react";
import { useTheme } from "next-themes";
import {
  X,
  ChevronRight,
  User,
  LogOut,
  ChevronLeft,
  Sparkles,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  patchMe,
  getMe,
  type ApiUser,
} from "@/lib/argus-api";
import AppearanceModal from "@/components/settings/AppearanceModal";
import LanguageModal from "@/components/settings/LanguageModal";
import ArchivedChatsView from "@/components/settings/ArchivedChatsView";
import DeletedItemsView from "@/components/settings/DeletedItemsView";
import { ENABLED_LANGUAGES, normalizeEnabledLanguage } from "@/lib/language-features";

type SettingsViewProps = {
  onClose: () => void;
  onLogout: () => void;
  onFeedback?: (type: "bug" | "feature" | "general", context: Record<string, unknown>) => void;
};

type SubView = "main" | "archived" | "deleted";

export default function SettingsView({ onClose, onLogout, onFeedback }: SettingsViewProps) {
  const { t, i18n } = useTranslation();
  const { theme } = useTheme();
  const showSubscriptionSection =
    process.env.NEXT_PUBLIC_ARGUS_SHOW_SUBSCRIPTION === "true";
  const showDevOnboardingReset =
    process.env.NEXT_PUBLIC_ENABLE_DEV_ONBOARDING_RESET === "true";
  const [activeSubView, setActiveSubView] = useState<SubView>("main");
  const [isLanguageModalOpen, setIsLanguageModalOpen] = useState(false);
  const [isAppearanceModalOpen, setIsAppearanceModalOpen] = useState(false);
  const [profile, setProfile] = useState<ApiUser | null>(null);

  useEffect(() => {
    getMe()
      .then(({ user }) => setProfile(user))
      .catch(() => null);
  }, []);
  const lang = i18n.language || "en";

  const currentLangLabel = useMemo(
    () => ENABLED_LANGUAGES.find((entry) => entry.code === normalizeEnabledLanguage(lang))?.name ?? "English",
    [lang],
  );

  const resetOnboardingForDev = async () => {
    await patchMe({
      onboarding: {
        completed: false,
        stage: "language_selection",
        language_confirmed: true,
        primary_goal: null,
      },
    });
  };


  const appearanceLabel =
    theme === "light"
      ? t("settings.app.appearance_options.light")
      : theme === "dark"
        ? t("settings.app.appearance_options.dark")
        : t("settings.app.appearance_options.system");

  const renderHeader = (title: string, onBack?: () => void) => (
    <>
      <div className="absolute top-0 inset-x-0 h-28 z-30 pointer-events-none backdrop-blur-[8px] bg-[#f5f5f5]/10 dark:bg-[#191c1f]/20 [mask-image:linear-gradient(to_bottom,black_30%,transparent_100%)] [-webkit-mask-image:linear-gradient(to_bottom,black_30%,transparent_100%)]" />
      <div className="absolute top-6 inset-x-0 w-full flex justify-center z-[35] pointer-events-none">
        <h1 className="text-[18px] font-medium tracking-tight pointer-events-auto">{title}</h1>
      </div>
      <div className="absolute top-4 left-4 z-[35]">
        {onBack && (
          <button
            onClick={onBack}
            className="flex items-center justify-center p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 transition-colors text-black dark:text-white border border-black/10 dark:border-white/10"
          >
            <ChevronLeft className="w-5 h-5" />
          </button>
        )}
      </div>
      <div className="absolute top-4 right-4 z-[35]">
        <button
          onClick={onClose}
          className="flex items-center justify-center p-2 rounded-full hover:bg-black/5 dark:hover:bg-white/10 transition-colors text-black dark:text-white border border-black/10 dark:border-white/10"
        >
          <X className="w-5 h-5" />
        </button>
      </div>
    </>
  );

  if (activeSubView === "archived") {
    return <ArchivedChatsView onClose={() => setActiveSubView("main")} />;
  }

  if (activeSubView === "deleted") {
    return <DeletedItemsView onClose={() => setActiveSubView("main")} />;
  }

  return (
    <div className="flex flex-col w-full h-[100dvh] max-w-5xl mx-auto overflow-hidden bg-[#f9f9f9] dark:bg-[#141517] relative font-space">
      {renderHeader(t("settings.title"))}

      <div className="flex-1 overflow-y-auto px-6 pt-24 pb-32 relative z-10 w-full max-w-md mx-auto">
        <div className="flex flex-col gap-6 w-full">
          {/* Profile Section */}
          <button className="flex items-center justify-between p-4 bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 rounded-[20px] hover:opacity-80 transition-opacity text-left w-full">
            <div className="flex items-center gap-4">
              <div className="w-14 h-14 rounded-full bg-[#f4e8ff] dark:bg-[#342442] flex items-center justify-center border border-black/5 dark:border-white/5 shrink-0">
                <User className="w-6 h-6 text-[#9a66d9] dark:text-[#d3a8fc]" />
              </div>
              <div className="flex flex-col">
                <span className="text-[16px] font-medium text-black dark:text-white">
                  {profile?.display_name || profile?.username || t("settings.profile.display_name")}
                </span>
                <span className="text-[14px] text-black/50 dark:text-white/50">{profile?.email || "email@example.com"}</span>
              </div>
            </div>
            <ChevronRight className="w-5 h-5 text-black/40 dark:text-white/40" />
          </button>

          {showSubscriptionSection && (
            <div className="flex flex-col gap-2">
              <span className="text-[13px] font-medium text-black/40 dark:text-white/40 px-2">
                {t("settings.subscription.title")}
              </span>
              <button className="w-full py-4 px-4 bg-[#f4e8ff]/80 dark:bg-[#342442]/80 border border-[#9a66d9]/20 dark:border-[#d3a8fc]/20 rounded-[16px] hover:opacity-80 transition-opacity text-center flex items-center justify-center">
                <span className="text-[15px] font-medium text-[#7e47be] dark:text-[#e4c4fd]">
                  {t("settings.subscription.upgrade_pro")}
                </span>
              </button>
            </div>
          )}

          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-medium text-black/40 dark:text-white/40 px-2">
              {t("settings.app.title")}
            </span>
            <div className="flex flex-col bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 rounded-[16px] overflow-hidden">
              <button
                onClick={() => setIsLanguageModalOpen(true)}
                className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5"
              >
                <span className="text-[15px] text-black dark:text-white font-medium">
                  {t("settings.app.language")}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-[14px] text-black/40 dark:text-white/40">{currentLangLabel}</span>
                  <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
                </div>
              </button>
              <button
                onClick={() => setIsAppearanceModalOpen(true)}
                className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                <span className="text-[15px] text-black dark:text-white font-medium">
                  {t("settings.app.appearance")}
                </span>
                <div className="flex items-center gap-2">
                  <span className="text-[14px] text-black/40 dark:text-white/40">{appearanceLabel}</span>
                  <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
                </div>
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-medium text-black/40 dark:text-white/40 px-2">
              {t("settings.data.title")}
            </span>
            <div className="flex flex-col bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 rounded-[16px] overflow-hidden">
              <button
                onClick={() => setActiveSubView("archived")}
                className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5"
              >
                <span className="text-[15px] text-black dark:text-white font-medium">
                  {t("settings.data.archived_chats")}
                </span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button
                onClick={() => setActiveSubView("deleted")}
                className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5"
              >
                <span className="text-[15px] text-black dark:text-white font-medium">
                  {t("settings.data.recently_deleted")}
                </span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                <span className="text-[15px] text-black dark:text-white font-medium">
                  {t("settings.data.security")}
                </span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-2">
            <span className="text-[13px] font-medium text-black/40 dark:text-white/40 px-2">
              {t("settings.about.title")}
            </span>
            <div className="flex flex-col bg-white dark:bg-[#1f2225] border border-black/10 dark:border-white/10 rounded-[16px] overflow-hidden">
              <button
                className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5"
              >
                <span className="text-[15px] text-black dark:text-white font-medium">
                  {t("settings.about.terms")}
                </span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button
                className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5"
              >
                <span className="text-[15px] text-black dark:text-white font-medium">
                  {t("settings.about.privacy")}
                </span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button
                onClick={() => onFeedback?.("bug", { surface: "settings" })}
                className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5"
              >
                <span className="text-[15px] text-black dark:text-white font-medium">
                  {t("settings.about.report_bug")}
                </span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button
                onClick={() => onFeedback?.("feature", { surface: "settings" })}
                className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors border-b border-black/5 dark:border-white/5"
              >
                <span className="text-[15px] text-black dark:text-white font-medium">
                  {t("settings.about.request_feature")}
                </span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
              <button
                onClick={() => onFeedback?.("general", { surface: "settings" })}
                className="flex items-center justify-between w-full p-4 hover:bg-black/5 dark:hover:bg-white/5 transition-colors"
              >
                <span className="text-[15px] text-black dark:text-white font-medium">
                  {t("settings.about.feedback")}
                </span>
                <ChevronRight className="w-4 h-4 text-black/40 dark:text-white/40" />
              </button>
            </div>
          </div>

          <button
            onClick={onLogout}
            className="w-fit mt-2 py-3 px-6 bg-red-400/20 dark:bg-red-500/10 border border-red-500/20 rounded-[12px] hover:opacity-80 transition-opacity text-center flex items-center justify-center gap-2 whitespace-nowrap"
          >
            <LogOut className="w-4 h-4 text-red-600 dark:text-red-400" />
            <span className="text-[14px] font-medium text-red-600 dark:text-red-400">{t("settings.logout")}</span>
          </button>

          {showDevOnboardingReset && (
            <button
              onClick={() => {
                void resetOnboardingForDev();
              }}
              className="w-fit mt-2 py-3 px-6 bg-black/5 dark:bg-white/10 border border-black/10 dark:border-white/20 rounded-[12px] hover:opacity-80 transition-opacity text-center flex items-center justify-center gap-2 whitespace-nowrap"
            >
              <Sparkles className="w-4 h-4 text-black/70 dark:text-white/80" />
              <span className="text-[14px] font-medium text-black/70 dark:text-white/80">
                {t("settings.dev.reset_onboarding", "Reset onboarding (dev)")}
              </span>
            </button>
          )}
        </div>
      </div>

      {isLanguageModalOpen && (
        <LanguageModal onClose={() => setIsLanguageModalOpen(false)} />
      )}

      {isAppearanceModalOpen && (
        <AppearanceModal onClose={() => setIsAppearanceModalOpen(false)} />
      )}
    </div>
  );
}
