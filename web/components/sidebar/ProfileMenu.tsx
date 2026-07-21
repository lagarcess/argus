"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  Activity,
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
import { getMe, patchMe, postFeedback, type ApiUser } from "@/lib/argus-api";
import {
  ENABLED_LANGUAGES,
  languageDisplayAbbreviation,
  localeForLanguage,
  normalizeEnabledLanguage,
} from "@/lib/language-features";

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
  onDeleteAllConversations?: () => void;
  onHistoryMutated?: () => void;
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

type DeleteRequestState = "idle" | "submitting" | "success" | "error";

const SUPPORT_EMAIL =
  process.env.NEXT_PUBLIC_ARGUS_SUPPORT_EMAIL ?? "support@argus.local";

function profileHandle(profile: ApiUser | null) {
  const explicitUsername = profile?.username?.trim().replace(/^@+/, "");
  if (explicitUsername) return `@${explicitUsername}`;

  const emailLocalPart = profile?.email?.split("@")[0]?.trim();
  return emailLocalPart ? `@${emailLocalPart}` : null;
}

function profileInitial(profile: ApiUser | null) {
  const source =
    profile?.display_name?.trim() ||
    profile?.username?.trim() ||
    profile?.email?.trim() ||
    "A";
  return source.charAt(0).toUpperCase();
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function ProfileMenu({
  isOpen,
  onClose,
  onLogout,
  onFeedback,
  onDeleteAllConversations,
  onHistoryMutated,
  onOpenSidebarPreference,
  anchorRef,
  sidebarCollapsed = false,
}: ProfileMenuProps) {
  const { t, i18n } = useTranslation();
  const menuRef = useRef<HTMLDivElement>(null);
  const languagePickerRef = useRef<HTMLDivElement>(null);
  const [activeSubmenu, setActiveSubmenu] = useState<SubMenu>(null);
  const [activeModal, setActiveModal] = useState<ActiveModal>(null);
  const [profile, setProfile] = useState<ApiUser | null>(null);
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [isSavingName, setIsSavingName] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [isLanguagePickerOpen, setIsLanguagePickerOpen] = useState(false);
  const [isSavingLanguage, setIsSavingLanguage] = useState(false);
  const [languageError, setLanguageError] = useState<string | null>(null);
  const [isDeleteRequestOpen, setIsDeleteRequestOpen] = useState(false);
  const [deleteRequestState, setDeleteRequestState] =
    useState<DeleteRequestState>("idle");
  const submenuTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch profile on open
  useEffect(() => {
    if (isOpen) {
      setNameError(null);
      setLanguageError(null);
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

  useEffect(() => {
    if (!activeModal) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (isLanguagePickerOpen) {
        setIsLanguagePickerOpen(false);
        return;
      }
      if (isDeleteRequestOpen) {
        if (deleteRequestState !== "submitting") setIsDeleteRequestOpen(false);
        return;
      }
      setActiveModal(null);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [
    activeModal,
    deleteRequestState,
    isDeleteRequestOpen,
    isLanguagePickerOpen,
  ]);

  useEffect(() => {
    if (!isLanguagePickerOpen) return;
    const handler = (e: MouseEvent) => {
      if (languagePickerRef.current?.contains(e.target as Node)) return;
      setIsLanguagePickerOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [isLanguagePickerOpen]);

  // Submenu hover with delay and guard
  const [canOpenSubmenu, setCanOpenSubmenu] = useState(false);

  useEffect(() => {
    if (isOpen) {
      // Guard: wait 100ms before allowing submenus to open to prevent 'exploded' effect on open
      const t = setTimeout(() => setCanOpenSubmenu(true), 100);
      return () => clearTimeout(t);
    } else {
      setCanOpenSubmenu(false);
      setActiveSubmenu(null);
    }
  }, [isOpen]);

  const handleSubmenuEnter = useCallback((menu: SubMenu) => {
    if (!canOpenSubmenu) return;
    if (submenuTimeoutRef.current) clearTimeout(submenuTimeoutRef.current);
    setActiveSubmenu(menu);
  }, [canOpenSubmenu]);

  const handleSubmenuToggle = useCallback((menu: SubMenu) => {
    if (submenuTimeoutRef.current) clearTimeout(submenuTimeoutRef.current);
    setActiveSubmenu((current) => (current === menu ? null : menu));
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

  const handleDeleteAllConversations = useCallback(() => {
    setActiveSubmenu(null);
    onClose();
    onDeleteAllConversations?.();
  }, [onClose, onDeleteAllConversations]);

  // Profile name editing
  const handleStartEditName = useCallback(() => {
    setNameValue(profile?.display_name ?? "");
    setNameError(null);
    setEditingName(true);
  }, [profile]);

  const handleSaveName = useCallback(async () => {
    const trimmed = nameValue.trim();
    if (!trimmed || trimmed === profile?.display_name) {
      setEditingName(false);
      return;
    }
    setIsSavingName(true);
    setNameError(null);
    try {
      const { user } = await patchMe({ display_name: trimmed });
      setProfile(user);
      setEditingName(false);
    } catch (err) {
      console.error("Failed to update display name", err);
      setNameError(
        t(
          "settings.profile.display_name_save_error",
          "Could not save that name yet.",
        ),
      );
    } finally {
      setIsSavingName(false);
    }
  }, [nameValue, profile, t]);

  const currentLanguage = normalizeEnabledLanguage(
    profile?.language ?? i18n.language,
  );
  const currentLanguageAbbreviation =
    languageDisplayAbbreviation(currentLanguage);
  const handleLanguageSelect = useCallback(
    async (code: string) => {
      const nextLanguage = normalizeEnabledLanguage(code);
      const previousLanguage = normalizeEnabledLanguage(
        profile?.language ?? i18n.language,
      );
      if (isSavingLanguage) return;

      setIsSavingLanguage(true);
      setLanguageError(null);
      setProfile((current) =>
        current
          ? {
              ...current,
              language: nextLanguage,
              locale: localeForLanguage(nextLanguage),
            }
          : current,
      );
      await i18n.changeLanguage(nextLanguage);

      try {
        const { user } = await patchMe({
          language: nextLanguage,
          locale: localeForLanguage(nextLanguage),
        });
        setProfile(user);
        setIsLanguagePickerOpen(false);
      } catch (err) {
        console.error("Failed to update language", err);
        await i18n.changeLanguage(previousLanguage);
        setProfile((current) =>
          current
            ? {
                ...current,
                language: previousLanguage,
                locale: localeForLanguage(previousLanguage),
              }
            : current,
        );
        setLanguageError(
          t(
            "settings.profile.language_save_error",
            "Could not update language yet.",
          ),
        );
      } finally {
        setIsSavingLanguage(false);
      }
    },
    [i18n, isSavingLanguage, profile, t],
  );

  const handleOpenDeleteRequest = useCallback(() => {
    setDeleteRequestState("idle");
    setIsDeleteRequestOpen(true);
  }, []);

  const handleSubmitDeleteRequest = useCallback(async () => {
    if (deleteRequestState === "submitting" || deleteRequestState === "success") {
      return;
    }
    setDeleteRequestState("submitting");
    try {
      await postFeedback({
        type: "account_deletion_request",
        message: "Private alpha account deletion requested.",
        context: {
          source: "profile_modal",
          profile_language: currentLanguage,
        },
      });
      setDeleteRequestState("success");
    } catch (err) {
      console.error("Failed to submit account deletion request", err);
      setDeleteRequestState("error");
    }
  }, [currentLanguage, deleteRequestState]);

  const accountHint = profile?.email ? ` (${profile.email})` : "";
  const supportMailto = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(
    t(
      "settings.profile.request_deletion.email_subject",
      "Argus account deletion request",
    ),
  )}&body=${encodeURIComponent(
    t(
      "settings.profile.request_deletion.email_body",
      "Please help me request deletion for my Argus account{{account_hint}}.",
      { account_hint: accountHint },
    ),
  )}`;

  const deleteRequestDialog = isDeleteRequestOpen ? (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/25 p-4 backdrop-blur-sm dark:bg-black/60">
      <button
        className="absolute inset-0"
        onClick={() => {
          if (deleteRequestState !== "submitting") {
            setIsDeleteRequestOpen(false);
          }
        }}
        aria-label={t(
          "settings.profile.request_deletion.close",
          "Close deletion request",
        )}
      />
      <div
        className="relative w-full max-w-sm rounded-[18px] border border-black/5 bg-white p-5 dark:border-white/10 dark:bg-[#1b1d20]"
        role="dialog"
        aria-modal="true"
        aria-labelledby="argus-delete-request-title"
      >
        <div className="mb-3 flex items-center justify-between">
          <h3
            id="argus-delete-request-title"
            className="font-display text-[16px] font-medium text-black dark:text-white"
          >
            {t(
              "settings.profile.request_deletion.title",
              "Request account deletion",
            )}
          </h3>
          <button
            type="button"
            onClick={() => setIsDeleteRequestOpen(false)}
            disabled={deleteRequestState === "submitting"}
            className="rounded-full p-1.5 hover:bg-black/5 disabled:cursor-wait disabled:opacity-50 dark:hover:bg-white/10"
            aria-label={t(
              "settings.profile.request_deletion.close",
              "Close deletion request",
            )}
          >
            <X className="h-4 w-4 text-black/50 dark:text-white/50" />
          </button>
        </div>

        {deleteRequestState === "success" ? (
          <>
            <p className="text-[13px] leading-relaxed text-black/55 dark:text-white/55">
              {t(
                "settings.profile.request_deletion.success",
                "Request sent. We'll follow up by email.",
              )}
            </p>
            <div className="mt-5 flex justify-end">
              <button
                type="button"
                onClick={() => setIsDeleteRequestOpen(false)}
                className="rounded-md bg-black px-3 py-2 text-[13px] font-medium text-white hover:bg-black/85 dark:bg-white dark:text-black dark:hover:bg-white/85"
              >
                {t("common.done", "Done")}
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="text-[13px] leading-relaxed text-black/55 dark:text-white/55">
              {t(
                "settings.profile.request_deletion.body",
                "Support handles account deletion during private alpha. We'll verify ownership, process your account data, and follow up by email. Completed deletions cannot be undone.",
              )}
            </p>
            {deleteRequestState === "error" && (
              <p className="mt-3 text-[12px] leading-relaxed text-[#d66d75]">
                {t(
                  "settings.profile.request_deletion.error",
                  "We could not submit that request yet.",
                )}{" "}
                <a className="underline" href={supportMailto}>
                  {t(
                    "settings.profile.request_deletion.email_fallback",
                    "Email support",
                  )}
                </a>
              </p>
            )}
            <div className="mt-5 flex justify-end gap-2">
              <button
                type="button"
                onClick={() => setIsDeleteRequestOpen(false)}
                disabled={deleteRequestState === "submitting"}
                className="rounded-md px-3 py-2 text-[13px] font-medium text-black/55 hover:bg-black/5 disabled:cursor-wait disabled:opacity-50 dark:text-white/55 dark:hover:bg-white/10"
              >
                {t("common.cancel", "Cancel")}
              </button>
              <button
                type="button"
                onClick={() => void handleSubmitDeleteRequest()}
                disabled={deleteRequestState === "submitting"}
                className="rounded-md bg-[#d66d75]/12 px-3 py-2 text-[13px] font-medium text-[#b94c55] hover:bg-[#d66d75]/18 disabled:cursor-wait disabled:opacity-60 dark:text-[#e7a2a8]"
              >
                {deleteRequestState === "submitting"
                  ? t(
                      "settings.profile.request_deletion.submitting",
                      "Sending...",
                    )
                  : t(
                      "settings.profile.request_deletion.contact_support",
                      "Contact support",
                    )}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  ) : null;

  if (!isOpen && !activeModal && !isDeleteRequestOpen) return null;

  // ── Active modal rendering ──────────────────────────────────────────────
  if (activeModal === "appearance") {
    return <AppearanceModal onClose={() => setActiveModal(null)} />;
  }
  if (activeModal === "language") {
    return <LanguageModal onClose={() => setActiveModal(null)} />;
  }
  if (activeModal === "archived") {
    return (
      <ArchivedChatsView
        onClose={() => setActiveModal(null)}
        onRestored={onHistoryMutated}
      />
    );
  }
  if (activeModal === "deleted") {
    return (
      <DeletedItemsView
        onClose={() => setActiveModal(null)}
        onRestored={onHistoryMutated}
      />
    );
  }
  if (activeModal === "profile") {
    return (
      <>
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/25 p-4 backdrop-blur-sm dark:bg-black/60">
          <button
            className="absolute inset-0"
            onClick={() => setActiveModal(null)}
            aria-label={t("settings.profile.close", "Close profile")}
          />
          <div
            className="relative w-full max-w-sm overflow-visible rounded-[18px] border border-black/5 bg-white p-5 dark:border-white/10 dark:bg-[#1b1d20]"
            role="dialog"
            aria-modal="true"
            aria-labelledby="argus-profile-modal-title"
          >
            {/* Header */}
            <div className="mb-4 flex items-center justify-between">
              <h2
                id="argus-profile-modal-title"
                className="font-display text-[16px] font-medium text-black dark:text-white"
              >
                {t("settings.profile.title", "Profile")}
              </h2>
              <button
                onClick={() => setActiveModal(null)}
                className="rounded-full p-1.5 hover:bg-black/5 dark:hover:bg-white/10"
                aria-label={t("settings.profile.close", "Close profile")}
              >
                <X className="h-4 w-4 text-black/50 dark:text-white/50" />
              </button>
            </div>

            <div className="flex flex-col gap-3">
              {/* Avatar + Name */}
              <div className="flex items-center gap-3">
                <div className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full bg-[#191c1f] text-[16px] font-bold text-white dark:bg-white/10">
                  {profileInitial(profile)}
                </div>
                <div className="flex min-w-0 flex-1 flex-col">
                  {/* Display Name - editable */}
                  {editingName ? (
                    <div className="flex items-center gap-1.5">
                      <input
                        autoFocus
                        type="text"
                        value={nameValue}
                        onChange={(e) =>
                          setNameValue(e.target.value.slice(0, 60))
                        }
                        onKeyDown={(e) => {
                          if (e.key === "Enter") void handleSaveName();
                          if (e.key === "Escape") setEditingName(false);
                        }}
                        disabled={isSavingName}
                        className="min-w-0 flex-1 rounded-md border border-black/15 bg-transparent px-2 py-1 text-[14px] font-medium outline-none focus:border-black/30 dark:border-white/15 dark:focus:border-white/30"
                        maxLength={60}
                        placeholder={t(
                          "settings.profile.display_name",
                          "Display name",
                        )}
                      />
                      <button
                        onClick={() => void handleSaveName()}
                        disabled={isSavingName}
                        className="rounded-md p-1 hover:bg-black/5 dark:hover:bg-white/10"
                        title={t("common.save", "Save")}
                        aria-label={t("common.save", "Save")}
                      >
                        <Check
                          className={`h-3.5 w-3.5 text-[#5ba897] ${
                            isSavingName ? "opacity-40" : ""
                          }`}
                        />
                      </button>
                      <button
                        onClick={() => setEditingName(false)}
                        disabled={isSavingName}
                        className="rounded-md p-1 hover:bg-black/5 dark:hover:bg-white/10"
                        title={t("common.cancel", "Cancel")}
                        aria-label={t("common.cancel", "Cancel")}
                      >
                        <X className="h-3.5 w-3.5 text-black/40 dark:text-white/40" />
                      </button>
                    </div>
                  ) : (
                    <div className="group flex items-center gap-1.5">
                      <span className="font-display truncate text-[15px] font-medium text-black dark:text-white">
                        {profile?.display_name ??
                          t("settings.profile.default_user", "User")}
                      </span>
                      <button
                        onClick={handleStartEditName}
                        className="rounded-md p-0.5 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-black/5 dark:hover:bg-white/10"
                        title={t(
                          "settings.profile.edit_display_name",
                          "Edit display name",
                        )}
                        aria-label={t(
                          "settings.profile.edit_display_name",
                          "Edit display name",
                        )}
                      >
                        <Edit2 className="h-3 w-3 text-black/40 dark:text-white/40" />
                      </button>
                    </div>
                  )}
                  {nameError && (
                    <span className="mt-1 text-[12px] text-[#d66d75]">
                      {nameError}
                    </span>
                  )}
                  {/* Username */}
                  {profileHandle(profile) && (
                    <span className="text-[13px] text-black/40 dark:text-white/40">
                      {profileHandle(profile)}
                    </span>
                  )}
                  <span className="text-[13px] text-black/40 dark:text-white/40">
                    {profile?.email ?? ""}
                  </span>
                </div>
              </div>

            {/* Info */}
            <div className="mt-2 flex flex-col gap-2 text-[13px]">
              <div
                ref={languagePickerRef}
                className="relative flex items-center justify-between py-1"
              >
                <span className="text-black/50 dark:text-white/50">
                  {t("settings.app.language", "Language")}
                </span>
                <button
                  id="argus-profile-language-trigger"
                  type="button"
                  onClick={() => setIsLanguagePickerOpen((open) => !open)}
                  className="-mr-1 rounded-md px-1.5 py-0.5 text-black outline-none transition-colors hover:bg-black/[0.04] focus-visible:ring-2 focus-visible:ring-black/20 dark:text-white dark:hover:bg-white/[0.06] dark:focus-visible:ring-white/20"
                  aria-haspopup="listbox"
                  aria-expanded={isLanguagePickerOpen}
                  aria-controls="argus-profile-language-picker"
                  aria-label={t("settings.app.language", "App language")}
                >
                  {currentLanguageAbbreviation}
                </button>
                {isLanguagePickerOpen && (
                  <div
                    id="argus-profile-language-picker"
                    role="listbox"
                    aria-labelledby="argus-profile-language-trigger"
                    className="absolute right-0 top-full z-30 mt-1 min-w-[136px] rounded-[10px] border border-black/10 bg-white py-1 shadow-[0_12px_28px_rgba(0,0,0,0.12)] dark:border-white/10 dark:bg-[#23262a]"
                  >
                    {ENABLED_LANGUAGES.map((entry) => {
                      const entryLanguage = normalizeEnabledLanguage(entry.code);
                      const selected = entryLanguage === currentLanguage;
                      return (
                        <button
                          key={entry.code}
                          type="button"
                          role="option"
                          aria-selected={selected}
                          onClick={() => void handleLanguageSelect(entry.code)}
                          disabled={isSavingLanguage}
                          className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-[13px] text-black transition-colors hover:bg-black/5 disabled:cursor-wait disabled:opacity-60 dark:text-white dark:hover:bg-white/5"
                        >
                          <span>{entry.name}</span>
                          {selected ? (
                            <Check className="h-3.5 w-3.5 text-black dark:text-white" />
                          ) : (
                            <span className="text-black/35 dark:text-white/35">
                              {languageDisplayAbbreviation(entryLanguage)}
                            </span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
              {languageError && (
                <span className="text-[12px] text-[#d66d75]">
                  {languageError}
                </span>
              )}
            </div>

          </div>
        </div>
      </div>
      {deleteRequestDialog}
      </>
    );
  }

  if (!isOpen) {
    return typeof document !== "undefined" && deleteRequestDialog
      ? createPortal(deleteRequestDialog, document.body)
      : deleteRequestDialog;
  }

  // ── Menu rendering ──────────────────────────────────────────────────────

  // Position: detached from sidebar, consistently to the right
  const menuLeft = sidebarCollapsed ? "68px" : "16px";

  const menu = (
    <div
      ref={menuRef}
      data-profile-menu-surface
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
        <button
          onClick={() => handleSubmenuToggle("data")}
          className="font-display flex w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
        >
          <div className="flex items-center gap-2.5">
            <Database className="h-4 w-4 text-black/50 dark:text-white/50" />
            {t("settings.data.title", "Data Controls")}
          </div>
          <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
        </button>
        {activeSubmenu === "data" && (
          <div
            className="absolute bottom-0 left-full ml-1.5 min-w-[220px] rounded-[12px] border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#1f2225]"
            style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.1)" }}
            onMouseEnter={handleSubmenuKeepAlive}
            onMouseLeave={handleSubmenuLeave}
          >
            <button
              onClick={() => openModal("archived")}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Archive className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
              {t("settings.data.archived_chats", "Archived chats")}
            </button>
            <button
              onClick={() => openModal("deleted")}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Trash2 className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
              {t("settings.data.recently_deleted", "Recently Deleted")}
            </button>
            <button
              onClick={() => {
                onClose();
                window.location.href = "/account/security";
              }}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Shield className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
              {t("settings.data.security", "Security")}
            </button>
            <button
              disabled
              className="flex w-full cursor-not-allowed items-center gap-2.5 px-3.5 py-2 text-[13px] text-black/25 dark:text-white/25"
            >
              <Activity className="h-3.5 w-3.5 text-black/25 dark:text-white/25" />
              {t("settings.data.usage", "Usage")}
            </button>
            <button
              onClick={handleDeleteAllConversations}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] font-medium text-[#d66d75] transition-colors hover:bg-[#d66d75]/10 dark:hover:bg-[#d66d75]/10"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span className="whitespace-nowrap">
                {t("settings.data.delete_all_conversations", "Delete all conversations")}
              </span>
            </button>
            <button
              type="button"
              onClick={handleOpenDeleteRequest}
              className="flex w-full flex-col items-start gap-1 px-3.5 py-2 text-left text-[#d66d75] transition-colors hover:bg-[#d66d75]/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#d66d75]/25 dark:hover:bg-[#d66d75]/10"
            >
              <span className="flex items-center gap-2.5 text-[13px] font-medium">
                <Trash2 className="h-3.5 w-3.5" />
                {t("settings.profile.delete_account", "Delete account")}
              </span>
              <span className="pl-6 text-[11px] leading-snug text-black/35 dark:text-white/35">
                {t(
                  "settings.profile.delete_account_note",
                  "Request permanent deletion of your Argus account. Support will follow up by email.",
                )}
              </span>
            </button>
          </div>
        )}
      </div>

      {/* Preferences */}
      <div
        className="relative"
        onMouseEnter={() => handleSubmenuEnter("settings")}
        onMouseLeave={handleSubmenuLeave}
      >
        <button
          onClick={() => handleSubmenuToggle("settings")}
          className="font-display flex w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
        >
          <div className="flex items-center gap-2.5">
            <Palette className="h-4 w-4 text-black/50 dark:text-white/50" />
            {t("settings.preferences.title", "Preferences")}
          </div>
          <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
        </button>
        {activeSubmenu === "settings" && (
          <div
            aria-label={t("settings.preferences.title", "Preferences")}
            className="absolute bottom-0 left-full ml-1.5 min-w-[220px] rounded-[12px] border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#1f2225]"
            style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.1)" }}
            onMouseEnter={handleSubmenuKeepAlive}
            onMouseLeave={handleSubmenuLeave}
          >
            <button
              onClick={() => openModal("appearance")}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Palette className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
              {t("settings.app.appearance", "Appearance")}
            </button>
            <button
              onClick={() => openModal("language")}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Globe className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
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
                <PanelLeft className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
                {t("settings.app.sidebar", "Sidebar")}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Help */}
      <div
        className="relative"
        onMouseEnter={() => handleSubmenuEnter("help")}
        onMouseLeave={handleSubmenuLeave}
      >
        <button
          onClick={() => handleSubmenuToggle("help")}
          className="font-display flex w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
        >
          <div className="flex items-center gap-2.5">
            <HelpCircle className="h-4 w-4 text-black/50 dark:text-white/50" />
            {t("settings.help.title", "Help & Legal")}
          </div>
          <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
        </button>
        {activeSubmenu === "help" && (
          <div
            className="absolute bottom-0 left-full ml-1.5 min-w-[220px] rounded-[12px] border border-black/10 bg-white py-1 dark:border-white/10 dark:bg-[#1f2225]"
            style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.1)" }}
            onMouseEnter={handleSubmenuKeepAlive}
            onMouseLeave={handleSubmenuLeave}
          >
            <a href="/terms" className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black transition-colors hover:bg-black/5 dark:text-white dark:hover:bg-white/5">
              <FileText className="h-3.5 w-3.5" />
              {t("settings.help.terms", "Terms of Use")}
            </a>
            <a href="/privacy" className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black transition-colors hover:bg-black/5 dark:text-white dark:hover:bg-white/5">
              <Shield className="h-3.5 w-3.5" />
              {t("settings.help.privacy", "Privacy Policy")}
            </a>
            <button disabled className="flex w-full cursor-not-allowed items-center gap-2.5 px-3.5 py-2 text-[13px] text-black/25 dark:text-white/25">
              <BookOpen className="h-3.5 w-3.5" />
              {t("settings.help.release_notes", "Release Notes")}
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
        <button
          onClick={() => handleSubmenuToggle("feedback")}
          className="font-display flex w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
        >
          <div className="flex items-center gap-2.5">
            <MessageSquareText className="h-4 w-4 text-black/50 dark:text-white/50" />
            {t("feedback.eyebrow", "Feedback")}
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
              {t("feedback.type.bug", "Report a bug")}
            </button>
            <button
              onClick={() => {
                onFeedback?.("feature");
                onClose();
              }}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Lightbulb className="h-3.5 w-3.5" />
              {t("feedback.type.feature", "Request a feature")}
            </button>
            <button
              onClick={() => {
                onFeedback?.("general");
                onClose();
              }}
              className="flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <MessageCircle className="h-3.5 w-3.5" />
              {t("feedback.type.general", "General feedback")}
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
      <div className="flex items-center gap-1 px-3.5 py-1.5 text-[10px] text-black/25 dark:text-white/25">
        <a href="/terms" className="transition-colors hover:text-black dark:hover:text-white">
          {t("settings.help.terms", "Terms of Use")}
        </a>
        <span aria-hidden="true">·</span>
        <a href="/privacy" className="transition-colors hover:text-black dark:hover:text-white">
          {t("settings.help.privacy", "Privacy Policy")}
        </a>
      </div>
    </div>
  );

  return typeof document !== "undefined" ? (
    <>
      {createPortal(menu, document.body)}
      {deleteRequestDialog ? createPortal(deleteRequestDialog, document.body) : null}
    </>
  ) : null;
}
