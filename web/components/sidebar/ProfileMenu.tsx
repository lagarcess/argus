"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  Archive,
  ChevronRight,
  Database,
  HelpCircle,
  LogOut,
  MessageSquareText,
  Palette,
  Globe,
  PanelLeft,
  Shield,
  Trash2,
  User,
  FileText,
  BookOpen,
  Bug,
  Lightbulb,
  MessageCircle,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { getMe, type ApiUser } from "@/lib/argus-api";

import AppearanceModal from "@/components/settings/AppearanceModal";
import LanguageModal from "@/components/settings/LanguageModal";
import ArchivedChatsView from "@/components/settings/ArchivedChatsView";
import DeletedItemsView from "@/components/settings/DeletedItemsView";

// ─── Types ────────────────────────────────────────────────────────────────────

type ProfileMenuProps = {
  isOpen: boolean;
  onClose: () => void;
  onLogout: () => void;
  onFeedback?: (type: "bug" | "feature" | "general") => void;
  onOpenSidebarPreference?: () => void;
  /** Anchor position */
  anchorRef: React.RefObject<HTMLElement | null>;
};

type ActiveModal =
  | null
  | "appearance"
  | "language"
  | "archived"
  | "deleted"
  | "profile";

type SubMenu = null | "data" | "settings" | "help" | "feedback";

// ─── Component ────────────────────────────────────────────────────────────────

export default function ProfileMenu({
  isOpen,
  onClose,
  onLogout,
  onFeedback,
  onOpenSidebarPreference,
  anchorRef,
}: ProfileMenuProps) {
  const { t } = useTranslation();
  const menuRef = useRef<HTMLDivElement>(null);
  const [activeSubmenu, setActiveSubmenu] = useState<SubMenu>(null);
  const [activeModal, setActiveModal] = useState<ActiveModal>(null);
  const [profile, setProfile] = useState<ApiUser | null>(null);
  const submenuTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch profile on mount
  useEffect(() => {
    if (isOpen) {
      getMe()
        .then(({ user }) => setProfile(user))
        .catch(() => null);
    }
  }, [isOpen]);

  // Close on click-outside
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: MouseEvent) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(e.target as Node) &&
        anchorRef.current &&
        !anchorRef.current.contains(e.target as Node)
      ) {
        onClose();
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [isOpen, onClose, anchorRef]);

  // Close on Escape
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [isOpen, onClose]);

  // Submenu hover with delay
  const handleSubmenuEnter = useCallback((menu: SubMenu) => {
    if (submenuTimeoutRef.current) clearTimeout(submenuTimeoutRef.current);
    submenuTimeoutRef.current = setTimeout(() => setActiveSubmenu(menu), 150);
  }, []);

  const handleSubmenuLeave = useCallback(() => {
    if (submenuTimeoutRef.current) clearTimeout(submenuTimeoutRef.current);
    submenuTimeoutRef.current = setTimeout(() => setActiveSubmenu(null), 200);
  }, []);

  const openModal = useCallback(
    (modal: ActiveModal) => {
      setActiveModal(modal);
      onClose();
    },
    [onClose],
  );

  if (!isOpen && !activeModal) return null;

  // ── Active modal rendering ──────────────────────────────────────────────
  if (activeModal === "appearance") {
    return <AppearanceModal onClose={() => setActiveModal(null)} />;
  }
  if (activeModal === "language") {
    return <LanguageModal onClose={() => setActiveModal(null)} />;
  }
  if (activeModal === "archived") {
    return <ArchivedChatsView onClose={() => setActiveModal(null)} />;
  }
  if (activeModal === "deleted") {
    return <DeletedItemsView onClose={() => setActiveModal(null)} />;
  }
  if (activeModal === "profile") {
    return (
      <div className="fixed inset-0 z-[70] bg-black/25 dark:bg-black/60 backdrop-blur-sm p-4 flex items-center justify-center">
        <button className="absolute inset-0" onClick={() => setActiveModal(null)} aria-label="Close profile" />
        <div className="relative w-full max-w-sm bg-white dark:bg-[#1b1d20] rounded-[18px] border border-black/5 dark:border-white/10 overflow-hidden p-5">
          <h2 className="text-[16px] font-medium text-black dark:text-white mb-4">
            {t("settings.profile.title", "Profile")}
          </h2>
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-full bg-[#191c1f] dark:bg-white/10 flex items-center justify-center text-white font-bold text-[16px]">
                {(profile?.display_name ?? profile?.email ?? "A").charAt(0).toUpperCase()}
              </div>
              <div className="flex flex-col">
                <span className="text-[15px] font-medium text-black dark:text-white">
                  {profile?.display_name ?? profile?.username ?? "User"}
                </span>
                <span className="text-[13px] text-black/40 dark:text-white/40">
                  {profile?.email ?? ""}
                </span>
              </div>
            </div>
            <div className="mt-2 flex flex-col gap-2 text-[13px]">
              <div className="flex justify-between">
                <span className="text-black/50 dark:text-white/50">Language</span>
                <span className="text-black dark:text-white">{profile?.language ?? "en"}</span>
              </div>
            </div>
            <div className="mt-4 pt-3 border-t border-black/5 dark:border-white/5">
              <button
                disabled
                className="text-[13px] text-[#d66d75]/40 cursor-not-allowed"
              >
                Delete account
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (!isOpen) return null;

  // ── Menu rendering ──────────────────────────────────────────────────────
  return (
    <div
      ref={menuRef}
      className="absolute bottom-full left-0 z-50 mb-2 min-w-[220px] rounded-[14px] border border-black/10 bg-white py-1.5 dark:border-white/10 dark:bg-[#1f2225]"
      onMouseLeave={handleSubmenuLeave}
    >
      {/* Profile */}
      <button
        onClick={() => openModal("profile")}
        className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] font-medium hover:bg-black/5 dark:hover:bg-white/5"
      >
        <User className="h-4 w-4 text-black/50 dark:text-white/50" />
        {t("settings.profile.title", "Profile")}
      </button>

      {/* Data */}
      <div
        className="relative"
        onMouseEnter={() => handleSubmenuEnter("data")}
      >
        <button className="flex w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium hover:bg-black/5 dark:hover:bg-white/5">
          <div className="flex items-center gap-2.5">
            <Database className="h-4 w-4 text-black/50 dark:text-white/50" />
            {t("settings.data.title", "Data")}
          </div>
          <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
        </button>
        {activeSubmenu === "data" && (
          <div
            className="absolute bottom-0 left-full ml-1 min-w-[200px] rounded-[12px] border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#1f2225]"
            onMouseEnter={() => handleSubmenuEnter("data")}
            onMouseLeave={handleSubmenuLeave}
          >
            <button
              onClick={() => openModal("archived")}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] hover:bg-black/5 dark:hover:bg-white/5"
            >
              <Archive className="h-3.5 w-3.5" />
              {t("settings.data.archived_chats", "Archived chats")}
            </button>
            <button
              onClick={() => openModal("deleted")}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] hover:bg-black/5 dark:hover:bg-white/5"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {t("settings.data.recently_deleted", "Recently Deleted")}
            </button>
            <button
              disabled
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-[#d66d75]/40 cursor-not-allowed"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete all conversations
            </button>
          </div>
        )}
      </div>

      {/* Settings */}
      <div
        className="relative"
        onMouseEnter={() => handleSubmenuEnter("settings")}
      >
        <button className="flex w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium hover:bg-black/5 dark:hover:bg-white/5">
          <div className="flex items-center gap-2.5">
            <Palette className="h-4 w-4 text-black/50 dark:text-white/50" />
            {t("common.settings", "Settings")}
          </div>
          <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
        </button>
        {activeSubmenu === "settings" && (
          <div
            className="absolute bottom-0 left-full ml-1 min-w-[200px] rounded-[12px] border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#1f2225]"
            onMouseEnter={() => handleSubmenuEnter("settings")}
            onMouseLeave={handleSubmenuLeave}
          >
            <button
              onClick={() => openModal("appearance")}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] hover:bg-black/5 dark:hover:bg-white/5"
            >
              <Palette className="h-3.5 w-3.5" />
              {t("settings.app.appearance", "Appearance")}
            </button>
            <button
              onClick={() => openModal("language")}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] hover:bg-black/5 dark:hover:bg-white/5"
            >
              <Globe className="h-3.5 w-3.5" />
              {t("settings.app.language", "Language")}
            </button>
            {onOpenSidebarPreference && (
              <button
                onClick={() => {
                  onOpenSidebarPreference();
                  onClose();
                }}
                className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] hover:bg-black/5 dark:hover:bg-white/5"
              >
                <PanelLeft className="h-3.5 w-3.5" />
                Sidebar
              </button>
            )}
            <button
              disabled
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black/25 dark:text-white/25 cursor-not-allowed"
            >
              <Shield className="h-3.5 w-3.5" />
              Security
            </button>
          </div>
        )}
      </div>

      {/* Help */}
      <div
        className="relative"
        onMouseEnter={() => handleSubmenuEnter("help")}
      >
        <button className="flex w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium hover:bg-black/5 dark:hover:bg-white/5">
          <div className="flex items-center gap-2.5">
            <HelpCircle className="h-4 w-4 text-black/50 dark:text-white/50" />
            Help
          </div>
          <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
        </button>
        {activeSubmenu === "help" && (
          <div
            className="absolute bottom-0 left-full ml-1 min-w-[200px] rounded-[12px] border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#1f2225]"
            onMouseEnter={() => handleSubmenuEnter("help")}
            onMouseLeave={handleSubmenuLeave}
          >
            <button disabled className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black/25 dark:text-white/25 cursor-not-allowed">
              <FileText className="h-3.5 w-3.5" />
              Terms of Service
            </button>
            <button disabled className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black/25 dark:text-white/25 cursor-not-allowed">
              <Shield className="h-3.5 w-3.5" />
              Privacy Policy
            </button>
            <button disabled className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black/25 dark:text-white/25 cursor-not-allowed">
              <BookOpen className="h-3.5 w-3.5" />
              Release Notes
            </button>
          </div>
        )}
      </div>

      {/* Feedback */}
      <div
        className="relative"
        onMouseEnter={() => handleSubmenuEnter("feedback")}
      >
        <button className="flex w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium hover:bg-black/5 dark:hover:bg-white/5">
          <div className="flex items-center gap-2.5">
            <MessageSquareText className="h-4 w-4 text-black/50 dark:text-white/50" />
            Feedback
          </div>
          <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
        </button>
        {activeSubmenu === "feedback" && (
          <div
            className="absolute bottom-0 left-full ml-1 min-w-[200px] rounded-[12px] border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#1f2225]"
            onMouseEnter={() => handleSubmenuEnter("feedback")}
            onMouseLeave={handleSubmenuLeave}
          >
            <button
              onClick={() => {
                onFeedback?.("bug");
                onClose();
              }}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] hover:bg-black/5 dark:hover:bg-white/5"
            >
              <Bug className="h-3.5 w-3.5" />
              Report a Bug
            </button>
            <button
              onClick={() => {
                onFeedback?.("feature");
                onClose();
              }}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] hover:bg-black/5 dark:hover:bg-white/5"
            >
              <Lightbulb className="h-3.5 w-3.5" />
              Request a Feature
            </button>
            <button
              onClick={() => {
                onFeedback?.("general");
                onClose();
              }}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] hover:bg-black/5 dark:hover:bg-white/5"
            >
              <MessageCircle className="h-3.5 w-3.5" />
              General Feedback
            </button>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className="my-1 border-t border-black/5 dark:border-white/5" />

      {/* Log out */}
      <button
        onClick={() => {
          onLogout();
          onClose();
        }}
        className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] font-medium text-[#d66d75] hover:bg-black/5 dark:hover:bg-white/5"
      >
        <LogOut className="h-4 w-4" />
        {t("settings.logout", "Log out")}
      </button>

      {/* Footer links */}
      <div className="my-1 border-t border-black/5 dark:border-white/5" />
      <div className="px-3.5 py-1.5 text-[10px] text-black/25 dark:text-white/25">
        Terms of Service · Privacy Policy
      </div>
    </div>
  );
}
