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
  Check,
  X,
  Edit2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { getMe, patchMe, type ApiUser } from "@/lib/argus-api";

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
  /** Whether the sidebar is collapsed (affects menu position) */
  sidebarCollapsed?: boolean;
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
  sidebarCollapsed = false,
}: ProfileMenuProps) {
  const { t } = useTranslation();
  const menuRef = useRef<HTMLDivElement>(null);
  const [activeSubmenu, setActiveSubmenu] = useState<SubMenu>(null);
  const [activeModal, setActiveModal] = useState<ActiveModal>(null);
  const [profile, setProfile] = useState<ApiUser | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const submenuTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch profile on open
  useEffect(() => {
    if (isOpen) {
      getMe()
        .then(({ user }) => setProfile(user))
        .catch(() => null);
    }
  }, [isOpen]);

  // Reset submenu state when menu closes
  useEffect(() => {
    if (!isOpen) {
      // Don't clear submenu here — preserve for re-open persistence
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
    setActiveSubmenu(menu);
  }, []);

  const handleSubmenuLeave = useCallback(() => {
    if (submenuTimeoutRef.current) clearTimeout(submenuTimeoutRef.current);
    submenuTimeoutRef.current = setTimeout(() => setActiveSubmenu(null), 250);
  }, []);

  const handleSubmenuKeepAlive = useCallback(() => {
    if (submenuTimeoutRef.current) clearTimeout(submenuTimeoutRef.current);
  }, []);

  const openModal = useCallback(
    (modal: ActiveModal) => {
      setActiveModal(modal);
      setActiveSubmenu(null);
      onClose();
    },
    [onClose],
  );

  // Profile name editing
  const handleStartEditName = useCallback(() => {
    setNameValue(profile?.display_name ?? "");
    setEditingName(true);
  }, [profile]);

  const handleSaveName = useCallback(async () => {
    const trimmed = nameValue.trim();
    if (!trimmed || trimmed === profile?.display_name) {
      setEditingName(false);
      return;
    }
    try {
      const { user } = await patchMe({ display_name: trimmed });
      setProfile(user);
    } catch (err) {
      console.error("Failed to update display name", err);
    }
    setEditingName(false);
  }, [nameValue, profile]);

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
      <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/25 p-4 backdrop-blur-sm dark:bg-black/60">
        <button className="absolute inset-0" onClick={() => setActiveModal(null)} aria-label="Close profile" />
        <div className="relative w-full max-w-sm overflow-hidden rounded-[18px] border border-black/5 bg-white p-5 dark:border-white/10 dark:bg-[#1b1d20]">
          {/* Header */}
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-[16px] font-medium text-black dark:text-white">
              {t("settings.profile.title", "Profile")}
            </h2>
            <button
              onClick={() => setActiveModal(null)}
              className="rounded-full p-1.5 hover:bg-black/5 dark:hover:bg-white/10"
            >
              <X className="h-4 w-4 text-black/50 dark:text-white/50" />
            </button>
          </div>

          <div className="flex flex-col gap-3">
            {/* Avatar + Name */}
            <div className="flex items-center gap-3">
              <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-[#191c1f] text-[16px] font-bold text-white dark:bg-white/10">
                {(profile?.display_name ?? profile?.email ?? "A").charAt(0).toUpperCase()}
              </div>
              <div className="flex min-w-0 flex-1 flex-col">
                {/* Display Name — editable */}
                {editingName ? (
                  <div className="flex items-center gap-1.5">
                    <input
                      autoFocus
                      type="text"
                      value={nameValue}
                      onChange={(e) => setNameValue(e.target.value.slice(0, 60))}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void handleSaveName();
                        if (e.key === "Escape") setEditingName(false);
                      }}
                      className="min-w-0 flex-1 rounded-md border border-black/15 bg-transparent px-2 py-1 text-[14px] font-medium outline-none focus:border-black/30 dark:border-white/15 dark:focus:border-white/30"
                      maxLength={60}
                      placeholder="Display name"
                    />
                    <button
                      onClick={() => void handleSaveName()}
                      className="rounded-md p-1 hover:bg-black/5 dark:hover:bg-white/10"
                      title="Save"
                    >
                      <Check className="h-3.5 w-3.5 text-[#5ba897]" />
                    </button>
                    <button
                      onClick={() => setEditingName(false)}
                      className="rounded-md p-1 hover:bg-black/5 dark:hover:bg-white/10"
                      title="Cancel"
                    >
                      <X className="h-3.5 w-3.5 text-black/40 dark:text-white/40" />
                    </button>
                  </div>
                ) : (
                  <div className="group flex items-center gap-1.5">
                    <span className="font-display truncate text-[15px] font-medium text-black dark:text-white">
                      {profile?.display_name ?? "User"}
                    </span>
                    <button
                      onClick={handleStartEditName}
                      className="rounded-md p-0.5 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-black/5 dark:hover:bg-white/10"
                      title="Edit display name"
                    >
                      <Edit2 className="h-3 w-3 text-black/40 dark:text-white/40" />
                    </button>
                  </div>
                )}
                {/* Username */}
                {profile?.username && (
                  <span className="text-[13px] text-black/40 dark:text-white/40">
                    @{profile.username}
                  </span>
                )}
                <span className="text-[13px] text-black/40 dark:text-white/40">
                  {profile?.email ?? ""}
                </span>
              </div>
            </div>

            {/* Info */}
            <div className="mt-2 flex flex-col gap-2 text-[13px]">
              <div className="flex justify-between">
                <span className="text-black/50 dark:text-white/50">Language</span>
                <span className="text-black dark:text-white">{profile?.language ?? "en"}</span>
              </div>
            </div>

            {/* Danger zone */}
            <div className="mt-4 border-t border-black/5 pt-3 dark:border-white/5">
              <button
                disabled
                className="cursor-not-allowed text-[13px] text-[#d66d75]/40"
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

  // Position: detached from sidebar, consistently to the right
  const menuLeft = sidebarCollapsed ? "68px" : "16px";

  return (
    <div
      ref={menuRef}
      className="fixed bottom-16 z-[60] min-w-[220px] rounded-[14px] border border-black/10 bg-white py-1.5 dark:border-white/10 dark:bg-[#1f2225]"
      style={{
        left: menuLeft,
        boxShadow: "0 8px 32px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)",
      }}
    >
      {/* Profile */}
      <button
        onClick={() => openModal("profile")}
        className="font-display flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
      >
        <User className="h-4 w-4 text-black/50 dark:text-white/50" />
        {t("settings.profile.title", "Profile")}
      </button>

      {/* Data */}
      <div
        className="relative"
        onMouseEnter={() => handleSubmenuEnter("data")}
        onMouseLeave={handleSubmenuLeave}
      >
        <button className="font-display flex w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5">
          <div className="flex items-center gap-2.5">
            <Database className="h-4 w-4 text-black/50 dark:text-white/50" />
            {t("settings.data.title", "Data")}
          </div>
          <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
        </button>
        {activeSubmenu === "data" && (
          <div
            className="absolute bottom-0 left-full ml-1.5 min-w-[200px] rounded-[12px] border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#1f2225]"
            style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.1)" }}
            onMouseEnter={handleSubmenuKeepAlive}
            onMouseLeave={handleSubmenuLeave}
          >
            <button
              onClick={() => openModal("archived")}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Archive className="h-3.5 w-3.5" />
              {t("settings.data.archived_chats", "Archived chats")}
            </button>
            <button
              onClick={() => openModal("deleted")}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Trash2 className="h-3.5 w-3.5" />
              {t("settings.data.recently_deleted", "Recently Deleted")}
            </button>
            <button
              disabled
              className="flex w-full cursor-not-allowed items-center gap-2.5 px-3.5 py-2 text-[13px] text-[#d66d75]/40"
            >
              <Trash2 className="h-3.5 w-3.5" />
              Delete all conversations
            </button>
          </div>
        )}
      </div>

      {/* Settings (includes Language) */}
      <div
        className="relative"
        onMouseEnter={() => handleSubmenuEnter("settings")}
        onMouseLeave={handleSubmenuLeave}
      >
        <button className="font-display flex w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5">
          <div className="flex items-center gap-2.5">
            <Palette className="h-4 w-4 text-black/50 dark:text-white/50" />
            {t("common.settings", "Settings")}
          </div>
          <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
        </button>
        {activeSubmenu === "settings" && (
          <div
            className="absolute bottom-0 left-full ml-1.5 min-w-[200px] rounded-[12px] border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#1f2225]"
            style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.1)" }}
            onMouseEnter={handleSubmenuKeepAlive}
            onMouseLeave={handleSubmenuLeave}
          >
            <button
              onClick={() => openModal("appearance")}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Palette className="h-3.5 w-3.5" />
              {t("settings.app.appearance", "Appearance")}
            </button>
            <button
              onClick={() => openModal("language")}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
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
                className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
              >
                <PanelLeft className="h-3.5 w-3.5" />
                Sidebar
              </button>
            )}
            <button
              disabled
              className="flex w-full cursor-not-allowed items-center gap-2.5 px-3.5 py-2 text-[13px] text-black/25 dark:text-white/25"
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
        onMouseLeave={handleSubmenuLeave}
      >
        <button className="font-display flex w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5">
          <div className="flex items-center gap-2.5">
            <HelpCircle className="h-4 w-4 text-black/50 dark:text-white/50" />
            Help
          </div>
          <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
        </button>
        {activeSubmenu === "help" && (
          <div
            className="absolute bottom-0 left-full ml-1.5 min-w-[200px] rounded-[12px] border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#1f2225]"
            style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.1)" }}
            onMouseEnter={handleSubmenuKeepAlive}
            onMouseLeave={handleSubmenuLeave}
          >
            <button disabled className="flex w-full cursor-not-allowed items-center gap-2.5 px-3.5 py-2 text-[13px] text-black/25 dark:text-white/25">
              <FileText className="h-3.5 w-3.5" />
              Terms of Service
            </button>
            <button disabled className="flex w-full cursor-not-allowed items-center gap-2.5 px-3.5 py-2 text-[13px] text-black/25 dark:text-white/25">
              <Shield className="h-3.5 w-3.5" />
              Privacy Policy
            </button>
            <button disabled className="flex w-full cursor-not-allowed items-center gap-2.5 px-3.5 py-2 text-[13px] text-black/25 dark:text-white/25">
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
        onMouseLeave={handleSubmenuLeave}
      >
        <button className="font-display flex w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5">
          <div className="flex items-center gap-2.5">
            <MessageSquareText className="h-4 w-4 text-black/50 dark:text-white/50" />
            Feedback
          </div>
          <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
        </button>
        {activeSubmenu === "feedback" && (
          <div
            className="absolute bottom-0 left-full ml-1.5 min-w-[200px] rounded-[12px] border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#1f2225]"
            style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.1)" }}
            onMouseEnter={handleSubmenuKeepAlive}
            onMouseLeave={handleSubmenuLeave}
          >
            <button
              onClick={() => {
                onFeedback?.("bug");
                onClose();
              }}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Bug className="h-3.5 w-3.5" />
              Report a Bug
            </button>
            <button
              onClick={() => {
                onFeedback?.("feature");
                onClose();
              }}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Lightbulb className="h-3.5 w-3.5" />
              Request a Feature
            </button>
            <button
              onClick={() => {
                onFeedback?.("general");
                onClose();
              }}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
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
        className="font-display flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] font-medium text-[#d66d75] hover:bg-black/5 dark:hover:bg-white/5"
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
