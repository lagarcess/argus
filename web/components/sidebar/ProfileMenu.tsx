"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { useModalSurface } from "../layout/useModalSurface";
import { useOverlayLayer } from "../layout/overlayStack";
import ProfileDeleteRequestDialog from "./ProfileDeleteRequestDialog";
import {
  SHEET_SUBMENU_CLASS,
  profileMenuClass,
  profileSubmenuAnchorClass,
  profileSubmenuClass,
} from "./profileMenuPlacement";
import {
  Activity,
  Archive,
  Brain,
  ChevronRight,
  ChevronUp,
  Database,
  HelpCircle,
  Keyboard,
  Link2,
  LogOut,
  MessageSquareText,
  Palette,
  Globe,
  PanelLeft,
  Shield,
  Trash2,
  User,
  FileText,
  Bug,
  Lightbulb,
  MessageCircle,
  Check,
  X,
  Edit2,
} from "lucide-react";
import { useTranslation } from "react-i18next";
import { useResponsiveLayout } from "@/components/layout/useResponsiveLayout";
import AdaptivePanel from "@/components/ui/AdaptivePanel";
import { getMe, patchMe, postFeedback, type ApiUser } from "@/lib/argus-api";
import {
  AVATAR_THEMES,
  avatarThemeClassName,
  avatarThemeStyle,
  type AvatarTheme,
} from "@/lib/avatar-theme";
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
import MemoryControlsModal from "@/components/settings/MemoryControlsModal";
import SharedReceiptsView from "@/components/settings/SharedReceiptsView";
import UsageModal from "@/components/settings/UsageModal";
import { memoryAvailable as fetchMemoryAvailable } from "@/lib/memory-privacy";
import { evidenceReceiptSharingEnabled } from "@/lib/private-alpha-flags";
import { QuickJumpBadge } from "@/components/keyboard/QuickJumpBadge";
import { useQuickJump } from "@/components/keyboard/useQuickJump";

// ─── Types ────────────────────────────────────────────────────────────────────

type ProfileMenuProps = {
  isOpen: boolean;
  onClose: () => void;
  onLogout: () => void;
  onFeedback?: (type: "bug" | "feature" | "general") => void;
  onDeleteAllConversations?: () => void;
  onHistoryMutated?: () => void;
  onOpenSidebarPreference?: () => void;
  onOpenKeyboardShortcuts?: () => void;
  /** Anchor position */
  anchorRef: React.RefObject<HTMLElement | null>;
  /** Whether the sidebar is collapsed (affects menu position) */
  sidebarCollapsed?: boolean;
  /**
   * Where the menu is opening from. The rail can afford a detached popover that
   * flies its submenus out to the right; a drawer cannot.
   */
  placement?: "rail" | "drawer";
};

type ActiveModal =
  | null
  | "appearance"
  | "language"
  | "archived"
  | "deleted"
  | "usage"
  | "memory"
  | "receipts"
  | "profile";

type SubMenu = null | "data" | "settings" | "help" | "feedback";

type DeleteRequestState = "idle" | "submitting" | "success" | "error";

type ProfileQuickJumpItem = {
  id: string;
  onSelect: () => void;
};

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
  onOpenKeyboardShortcuts,
  anchorRef,
  sidebarCollapsed = false,
  placement = "rail",
}: ProfileMenuProps) {
  const { t, i18n } = useTranslation();
  const { isBelowDesktop } = useResponsiveLayout();
  /*
   * Below the panel line this menu is a sheet, whatever the sidebar is doing.
   * Tying it to the sidebar's own 720 line left the tablet band showing a
   * shrunken mouse menu whose submenus only opened on a hover that a tablet
   * cannot produce.
   */
  const asSheet = isBelowDesktop;
  const isDrawerPlacement = placement === "drawer";
  const menuOverlayId = useId();
  const profileModalOverlayId = useId();
  const menuRef = useRef<HTMLDivElement>(null);
  const profileModalRef = useRef<HTMLDivElement>(null);
  const languagePickerRef = useRef<HTMLDivElement>(null);
  const avatarTriggerRef = useRef<HTMLButtonElement>(null);
  const avatarThemeDrawerRef = useRef<HTMLDivElement>(null);
  const [activeSubmenu, setActiveSubmenu] = useState<SubMenu>(null);
  const [activeModal, setActiveModal] = useState<ActiveModal>(null);
  const [profile, setProfile] = useState<ApiUser | null>(null);
  const [accountKind, setAccountKind] = useState<"guest" | "registered" | null>(
    null,
  );
  const [memoryControlsAvailable, setMemoryControlsAvailable] = useState(false);
  const dataControlsLabel = t("settings.data.title", "Data Controls");
  // Every Data Controls panel offers the same return, so the sheet's back row is
  // defined once rather than rebuilt at each mount.
  const backToDataControls = asSheet
    ? () => {
        setActiveModal(null);
        setActiveSubmenu("data");
      }
    : undefined;
  // Every receipt endpoint requires the registered-only can_save_decision
  // capability, so showing this to a guest offers a modal whose only action is a
  // retry that can never succeed.
  const receiptsAvailable =
    evidenceReceiptSharingEnabled && accountKind === "registered";
  const [editingName, setEditingName] = useState(false);
  const [nameValue, setNameValue] = useState("");
  const [isSavingName, setIsSavingName] = useState(false);
  const [nameError, setNameError] = useState<string | null>(null);
  const [isLanguagePickerOpen, setIsLanguagePickerOpen] = useState(false);
  const [isSavingLanguage, setIsSavingLanguage] = useState(false);
  const [languageError, setLanguageError] = useState<string | null>(null);
  const [isSavingAvatarTheme, setIsSavingAvatarTheme] = useState(false);
  const [avatarThemeError, setAvatarThemeError] = useState<string | null>(null);
  const [isAvatarPickerOpen, setIsAvatarPickerOpen] = useState(false);
  const [isDeleteRequestOpen, setIsDeleteRequestOpen] = useState(false);
  const [deleteRequestState, setDeleteRequestState] =
    useState<DeleteRequestState>("idle");
  const [usesCommandKey, setUsesCommandKey] = useState(false);
  const submenuTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hoverOpenedRef = useRef(false);

  const closeAvatarPicker = useCallback(() => {
    if (!isAvatarPickerOpen) return;

    setIsAvatarPickerOpen(false);
    avatarTriggerRef.current?.focus();
  }, [isAvatarPickerOpen]);

  const toggleAvatarPicker = useCallback(() => {
    if (accountKind !== "registered") return;

    if (isAvatarPickerOpen) {
      closeAvatarPicker();
      return;
    }

    setAvatarThemeError(null);
    setIsAvatarPickerOpen(true);
  }, [accountKind, closeAvatarPicker, isAvatarPickerOpen]);

  const closeProfileModal = useCallback(() => {
    setIsAvatarPickerOpen(false);
    setActiveModal(null);
  }, []);

  useEffect(() => {
    if (!isAvatarPickerOpen) return;

    const selectedTheme = avatarThemeDrawerRef.current?.querySelector<HTMLButtonElement>(
      '[role="radio"][aria-checked="true"]',
    );
    selectedTheme?.focus();
  }, [isAvatarPickerOpen]);

  // Fetch profile on open
  useEffect(() => {
    if (isOpen) {
      setNameError(null);
      setLanguageError(null);
      getMe()
        .then(({ user, account_kind }) => {
          setProfile(user);
          setAccountKind(account_kind);
        })
        .catch(() => null);
    }
  }, [isOpen]);

  // Reset submenu state when menu closes
  useEffect(() => {
    if (!isOpen) {
      // Don't clear submenu here — preserve for re-open persistence
    }
  }, [isOpen]);

  useEffect(() => {
    setUsesCommandKey(
      /Mac|iPhone|iPad|iPod/.test(navigator.userAgent),
    );
  }, []);

  // Memory stays invisible unless the backend exposes it to this account.
  useEffect(() => {
    if (!isOpen || accountKind !== "registered") return;
    let isCurrent = true;
    void fetchMemoryAvailable().then((available) => {
      if (isCurrent) setMemoryControlsAvailable(available);
    });
    return () => {
      isCurrent = false;
    };
  }, [isOpen, accountKind]);


  /*
   * One registration per visible surface.
   *
   * As a sheet the shell already owns the layer, the history entry and the
   * focus trap, so registering here as well gave the same panel two owners:
   * closing it scheduled two `history.back()` calls, and traversal being
   * asynchronous, that leaves a phantom entry the next press spends.
   */
  useModalSurface({
    isOpen: isOpen && isDrawerPlacement && !asSheet,
    overlayId: menuOverlayId,
    containerRef: menuRef,
    onDismiss: onClose,
    // A submenu is the shallower thing on screen, so it answers first instead
    // of one press closing both levels.
    onEscape: () => {
      if (activeSubmenu) {
        setActiveSubmenu(null);
        return;
      }
      onClose();
    },
    // A menu is not modal, so it does not hold Tab itself. The registry hands
    // containment down to the nearest trapping layer instead, which inside the
    // drawer is the drawer, so Tab still cannot reach the page behind it.
    trapFocus: false,
  });

  // On the rail this is a detached popover rather than a layer, so it keeps the
  // plain dismissal rules a popover has.
  useOverlayLayer({
    isOpen: isOpen && !isDrawerPlacement && !asSheet,
    overlayId: menuOverlayId,
    containerRef: menuRef,
    onEscape: onClose,
    onOutsidePointerDown: (event) => {
      if (anchorRef.current?.contains(event.target as Node)) return;
      onClose();
    },
  });

  // Opening this closes the menu, so the registration above has already stood
  // down by the time the dialog paints. It needs its own or nothing owns back,
  // Escape, or focus for it. Scoped to the panel rather than the backdrop, so
  // focus does not open on an invisible dismiss control.
  useModalSurface({
    isOpen: activeModal === "profile",
    overlayId: profileModalOverlayId,
    containerRef: profileModalRef,
    onDismiss: closeProfileModal,
    // The pickers inside this dialog are nested state rather than layers of
    // their own, so the registry cannot see them. Defaulting Escape to
    // onDismiss threw the whole dialog away while a picker was open.
    onEscape: () => {
      if (isLanguagePickerOpen) {
        setIsLanguagePickerOpen(false);
        return;
      }
      if (isAvatarPickerOpen) {
        closeAvatarPicker();
        return;
      }
      if (isDeleteRequestOpen) {
        if (deleteRequestState !== "submitting") setIsDeleteRequestOpen(false);
        return;
      }
      closeProfileModal();
    },
    returnFocusRef: anchorRef,
  });



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

  // A tap emits mouseenter as well as click, so hover-to-open and tap-to-toggle
  // cancelled each other out and no submenu ever appeared in the drawer. Touch
  // has no hover to express intent with, so the tap is the only opener there.
  const handleSubmenuEnter = useCallback((menu: SubMenu) => {
    if (asSheet) return;
    if (!canOpenSubmenu) return;
    if (submenuTimeoutRef.current) clearTimeout(submenuTimeoutRef.current);
    hoverOpenedRef.current = true;
    setActiveSubmenu(menu);
  }, [asSheet, canOpenSubmenu]);

  /*
   * Click opens a submenu at every width; hover only ever accelerates it.
   *
   * A press on a hover-capable machine fires enter and then click, so a plain
   * toggle closed what the hover had just opened and the submenu never
   * appeared. Anything a mouse can reach only by hovering is unreachable on a
   * tablet, which stays above the panel line in landscape.
   */
  const handleSubmenuToggle = useCallback((menu: SubMenu) => {
    if (submenuTimeoutRef.current) clearTimeout(submenuTimeoutRef.current);
    if (activeSubmenu === menu) {
      if (hoverOpenedRef.current) {
        // The hover opened it a moment ago; this click confirms rather than undoes.
        hoverOpenedRef.current = false;
        return;
      }
      setActiveSubmenu(null);
      return;
    }
    hoverOpenedRef.current = false;
    setActiveSubmenu(menu);
  }, [activeSubmenu]);

  const handleSubmenuLeave = useCallback(() => {
    if (asSheet) return;
    if (submenuTimeoutRef.current) clearTimeout(submenuTimeoutRef.current);
    submenuTimeoutRef.current = setTimeout(() => setActiveSubmenu(null), 250);
  }, [asSheet]);

  const handleSubmenuKeepAlive = useCallback(() => {
    if (submenuTimeoutRef.current) clearTimeout(submenuTimeoutRef.current);
  }, []);

  const openModal = useCallback(
    (modal: ActiveModal) => {
      setActiveModal(modal);
      if (asSheet) return;
      // The popover has nowhere to sit behind a dialog, so it closes. A sheet
      // stays open underneath, which is what the child's back row returns to.
      setActiveSubmenu(null);
      onClose();
    },
    [asSheet, onClose],
  );

  const handleDeleteAllConversations = useCallback(() => {
    setActiveSubmenu(null);
    onClose();
    onDeleteAllConversations?.();
  }, [onClose, onDeleteAllConversations]);

  const handleOpenKeyboardShortcuts = useCallback(() => {
    setActiveSubmenu(null);
    onClose();
    onOpenKeyboardShortcuts?.();
  }, [onClose, onOpenKeyboardShortcuts]);

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
  const avatarClassName =
    accountKind === "registered"
      ? avatarThemeClassName(profile?.avatar_theme)
      : "bg-[#191c1f] text-white dark:bg-white/10";
  const avatarStyle =
    accountKind === "registered"
      ? avatarThemeStyle(profile?.avatar_theme, "ambient")
      : undefined;
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

  const handleAvatarThemeSelect = useCallback(
    async (avatarTheme: AvatarTheme) => {
      if (!profile || accountKind !== "registered" || isSavingAvatarTheme) return;

      const previousTheme = profile.avatar_theme;
      setAvatarThemeError(null);
      setIsSavingAvatarTheme(true);
      setProfile((current) =>
        current ? { ...current, avatar_theme: avatarTheme } : current,
      );

      try {
        const { user } = await patchMe({ avatar_theme: avatarTheme });
        setProfile(user);
      } catch (err) {
        console.error("Failed to update avatar theme", err);
        setProfile((current) =>
          current ? { ...current, avatar_theme: previousTheme } : current,
        );
        setAvatarThemeError(
          t(
            "settings.profile.avatar_theme.save_error",
            "Could not update your avatar color yet.",
          ),
        );
      } finally {
        setIsSavingAvatarTheme(false);
      }
    },
    [accountKind, isSavingAvatarTheme, profile, t],
  );

  const handleAvatarThemeKeyDown = useCallback(
    (event: React.KeyboardEvent<HTMLButtonElement>, currentIndex: number) => {
      if (isSavingAvatarTheme) return;

      const lastIndex = AVATAR_THEMES.length - 1;
      let nextIndex: number | null = null;

      switch (event.key) {
        case "ArrowRight":
        case "ArrowDown":
          nextIndex = currentIndex === lastIndex ? 0 : currentIndex + 1;
          break;
        case "ArrowLeft":
        case "ArrowUp":
          nextIndex = currentIndex === 0 ? lastIndex : currentIndex - 1;
          break;
        case "Home":
          nextIndex = 0;
          break;
        case "End":
          nextIndex = lastIndex;
          break;
        default:
          return;
      }

      event.preventDefault();
      avatarThemeDrawerRef.current
        ?.querySelectorAll<HTMLButtonElement>('[role="radio"]')
        [nextIndex]?.focus();
      void handleAvatarThemeSelect(AVATAR_THEMES[nextIndex].token);
    },
    [handleAvatarThemeSelect, isSavingAvatarTheme],
  );

  const handleOpenDeleteRequest = useCallback(() => {
    setDeleteRequestState("idle");
    setIsDeleteRequestOpen(true);
  }, []);

  const quickJumpItems = useMemo<ProfileQuickJumpItem[]>(() => {
    if (activeSubmenu === "data") {
      return [
        ...(memoryControlsAvailable
          ? [{ id: "memory", onSelect: () => openModal("memory") }]
          : []),
        ...(receiptsAvailable
          ? [{ id: "receipts", onSelect: () => openModal("receipts") }]
          : []),
        { id: "archived", onSelect: () => openModal("archived") },
        { id: "deleted", onSelect: () => openModal("deleted") },
        {
          id: "security",
          onSelect: () => {
            onClose();
            window.location.href = "/account/security";
          },
        },
        { id: "usage", onSelect: () => openModal("usage") },
        { id: "delete-all", onSelect: handleDeleteAllConversations },
        { id: "delete-account", onSelect: handleOpenDeleteRequest },
      ];
    }
    if (activeSubmenu === "settings") {
      return [
        { id: "appearance", onSelect: () => openModal("appearance") },
        { id: "language", onSelect: () => openModal("language") },
        ...(onOpenSidebarPreference
          ? [
              {
                id: "sidebar",
                onSelect: () => {
                  onOpenSidebarPreference();
                  onClose();
                },
              },
            ]
          : []),
      ];
    }
    if (activeSubmenu === "help") {
      return [
        {
          id: "keyboard-shortcuts",
          onSelect: handleOpenKeyboardShortcuts,
        },
        {
          id: "terms",
          onSelect: () => {
            window.location.href = "/terms";
          },
        },
        {
          id: "privacy",
          onSelect: () => {
            window.location.href = "/privacy";
          },
        },
      ];
    }
    if (activeSubmenu === "feedback") {
      return [
        {
          id: "feedback-bug",
          onSelect: () => {
            onFeedback?.("bug");
            onClose();
          },
        },
        {
          id: "feedback-feature",
          onSelect: () => {
            onFeedback?.("feature");
            onClose();
          },
        },
        {
          id: "feedback-general",
          onSelect: () => {
            onFeedback?.("general");
            onClose();
          },
        },
      ];
    }
    return [
      { id: "profile", onSelect: () => openModal("profile") },
      { id: "data", onSelect: () => handleSubmenuToggle("data") },
      { id: "settings", onSelect: () => handleSubmenuToggle("settings") },
      { id: "help", onSelect: () => handleSubmenuToggle("help") },
      { id: "feedback", onSelect: () => handleSubmenuToggle("feedback") },
    ];
  }, [
    activeSubmenu,
    handleDeleteAllConversations,
    handleOpenDeleteRequest,
    handleOpenKeyboardShortcuts,
    handleSubmenuToggle,
    memoryControlsAvailable,
    receiptsAvailable,
    onClose,
    onFeedback,
    onOpenSidebarPreference,
    openModal,
  ]);
  const handleQuickJump = useCallback(
    (id: string) => {
      quickJumpItems.find((item) => item.id === id)?.onSelect();
    },
    [quickJumpItems],
  );
  const { isQuickJumpActive, numberFor } = useQuickJump({
    enabled: isOpen && !activeModal && !isDeleteRequestOpen,
    items: quickJumpItems,
    onSelect: handleQuickJump,
    usesCommandKey,
  });
  const quickJumpBadge = (id: string) => {
    const number = numberFor(id);
    return isQuickJumpActive && number !== null ? (
      <QuickJumpBadge
        number={number}
        presentation="shortcut_hint"
        usesCommandKey={usesCommandKey}
      />
    ) : null;
  };

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
    <ProfileDeleteRequestDialog
      state={deleteRequestState}
      supportMailto={supportMailto}
      onClose={() => setIsDeleteRequestOpen(false)}
      onSubmit={handleSubmitDeleteRequest}
    />
  ) : null;

  if (!isOpen && !activeModal && !isDeleteRequestOpen) return null;

  // ── Active modal rendering ──────────────────────────────────────────────
  if (activeModal === "appearance") {
    return (
      <AppearanceModal
        onClose={() => setActiveModal(null)}
        onBack={asSheet ? () => {
          setActiveModal(null);
          setActiveSubmenu("settings");
        } : undefined}
        backLabel={t("settings.app.title", "Preferences")}
      />
    );
  }
  if (activeModal === "language") {
    return (
      <LanguageModal
        onClose={() => setActiveModal(null)}
        onBack={asSheet ? () => {
          setActiveModal(null);
          setActiveSubmenu("settings");
        } : undefined}
        backLabel={t("settings.app.title", "Preferences")}
      />
    );
  }
  if (activeModal === "archived") {
    return (
      <ArchivedChatsView
        onClose={() => setActiveModal(null)}
        onBack={backToDataControls}
        backLabel={dataControlsLabel}
        onRestored={onHistoryMutated}
      />
    );
  }
  if (activeModal === "deleted") {
    return (
      <DeletedItemsView
        onClose={() => setActiveModal(null)}
        onBack={backToDataControls}
        backLabel={dataControlsLabel}
        onRestored={onHistoryMutated}
      />
    );
  }
  if (activeModal === "usage") {
    return (
      <UsageModal
        locale={localeForLanguage(
          normalizeEnabledLanguage(i18n.resolvedLanguage),
        )}
        onClose={() => setActiveModal(null)}
        onBack={backToDataControls}
        backLabel={dataControlsLabel}
        returnFocusRef={anchorRef}
      />
    );
  }
  if (activeModal === "memory") {
    return (
      <MemoryControlsModal
        locale={localeForLanguage(
          normalizeEnabledLanguage(i18n.resolvedLanguage),
        )}
        onClose={() => setActiveModal(null)}
        onBack={backToDataControls}
        backLabel={dataControlsLabel}
        returnFocusRef={anchorRef}
      />
    );
  }
  if (activeModal === "receipts") {
    return (
      <SharedReceiptsView
        onClose={() => setActiveModal(null)}
        onBack={backToDataControls}
        backLabel={dataControlsLabel}
        returnFocusRef={anchorRef}
      />
    );
  }
  if (activeModal === "profile") {
    return (
      <>
        <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/25 p-4 backdrop-blur-sm dark:bg-black/60">
          <button
        tabIndex={-1}
            className="absolute inset-0"
            onClick={closeProfileModal}
            aria-label={t("settings.profile.close", "Close profile")}
          />
          <div
            ref={profileModalRef}
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
                onClick={closeProfileModal}
                className="rounded-full p-1.5 hover:bg-black/5 dark:hover:bg-white/10"
                aria-label={t("settings.profile.close", "Close profile")}
              >
                <X className="h-4 w-4 text-black/50 dark:text-white/50" />
              </button>
            </div>

            <div className="flex flex-col gap-3">
              {/* Avatar + Name */}
              <div className="flex items-center gap-3">
                {accountKind === "registered" ? (
                  <button
                    ref={avatarTriggerRef}
                    type="button"
                    onClick={toggleAvatarPicker}
                    className="group relative flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full outline-none transition-transform hover:scale-[1.03] focus-visible:ring-2 focus-visible:ring-black/30 dark:focus-visible:ring-white/50"
                    aria-label={t(
                      "settings.profile.avatar_theme.change",
                      "Edit avatar",
                    )}
                    aria-expanded={isAvatarPickerOpen}
                    aria-controls="argus-avatar-theme-drawer"
                    data-avatar-theme-trigger
                  >
                    <span
                      className={`flex h-full w-full items-center justify-center rounded-full text-[16px] font-bold ${avatarClassName}`}
                      style={avatarStyle}
                    >
                      {profileInitial(profile)}
                    </span>
                    <span
                      className="pointer-events-none absolute -bottom-0.5 -right-0.5 flex h-5 w-5 items-center justify-center rounded-full bg-white text-black ring-1 ring-black/10 dark:bg-[#2b2e33] dark:text-white dark:ring-white/15"
                      aria-hidden="true"
                    >
                      <Edit2 className="h-2.5 w-2.5" />
                    </span>
                  </button>
                ) : (
                  <div
                    className={`flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-full text-[16px] font-bold ${avatarClassName}`}
                    style={avatarStyle}
                  >
                    {profileInitial(profile)}
                  </div>
                )}
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

              {accountKind === "registered" && (
                <div
                  id="argus-avatar-theme-drawer"
                  ref={avatarThemeDrawerRef}
                  className={`grid transition-[grid-template-rows,margin,opacity] duration-200 ease-out motion-reduce:transition-none ${
                    isAvatarPickerOpen
                      ? "mt-0 grid-rows-[1fr] opacity-100"
                      : "mt-0 grid-rows-[0fr] opacity-0"
                  }`}
                  aria-hidden={!isAvatarPickerOpen}
                  inert={!isAvatarPickerOpen}
                >
                  <div className="min-h-0 overflow-hidden">
                    <div className="pt-1">
                      <button
                        type="button"
                        onClick={closeAvatarPicker}
                        className="flex h-11 w-full items-center gap-2 text-left outline-none focus-visible:ring-2 focus-visible:ring-black/20 dark:focus-visible:ring-white/30"
                        aria-label={t(
                          "settings.profile.avatar_theme.close",
                          "Hide avatar colors",
                        )}
                      >
                        <span className="whitespace-nowrap text-[13px] text-black/50 dark:text-white/50">
                          {t(
                            "settings.profile.avatar_theme.label",
                            "Avatar color",
                          )}
                        </span>
                        <span
                          className="h-px flex-1 bg-black/10 dark:bg-white/10"
                          aria-hidden="true"
                        />
                        <span className="text-[11px] text-black/35 dark:text-white/35">
                          {t(
                            "settings.profile.avatar_theme.hide",
                            "Hide",
                          )}
                        </span>
                        <ChevronUp
                          className="h-3.5 w-3.5 text-black/35 dark:text-white/35"
                          aria-hidden="true"
                        />
                      </button>
                      <div
                        className="grid grid-cols-8 place-items-center gap-y-2 sm:grid-cols-7"
                        role="radiogroup"
                        aria-busy={isSavingAvatarTheme || undefined}
                        aria-label={t(
                          "settings.profile.avatar_theme.label",
                          "Avatar color",
                        )}
                      >
                        {AVATAR_THEMES.map((theme, index) => {
                          const selected =
                            (profile?.avatar_theme ?? "ocean") === theme.token;
                          const themeLabel = t(
                            `settings.profile.avatar_theme.themes.${theme.token}`,
                            theme.token,
                          );
                          return (
                            <button
                              key={theme.token}
                              type="button"
                              role="radio"
                              aria-checked={selected}
                              aria-label={themeLabel}
                              title={themeLabel}
                              aria-disabled={isSavingAvatarTheme || undefined}
                              onClick={() => void handleAvatarThemeSelect(theme.token)}
                              onKeyDown={(event) =>
                                handleAvatarThemeKeyDown(event, index)
                              }
                              tabIndex={selected ? 0 : -1}
                              className={`col-span-2 flex h-11 w-11 items-center justify-center rounded-full outline-none transition-transform hover:scale-105 focus-visible:ring-2 focus-visible:ring-black/30 dark:focus-visible:ring-white/50 sm:col-span-1 ${
                                isSavingAvatarTheme
                                  ? "cursor-wait opacity-60"
                                  : ""
                              } ${
                                index === 4 ? "col-start-2 sm:col-auto" : ""
                              }`}
                            >
                              <span
                                className={`flex h-9 w-9 items-center justify-center rounded-full border text-[12px] font-bold ${theme.className} ${
                                  theme.token === "ocean"
                                    ? "border-black/20 dark:border-white/20"
                                    : "border-transparent"
                                } ${
                                  selected
                                    ? "ring-2 ring-black/70 dark:ring-white/80"
                                    : ""
                                }`}
                                style={avatarThemeStyle(theme.token, "picker")}
                                aria-hidden="true"
                              >
                                {profileInitial(profile)}
                              </span>
                            </button>
                          );
                        })}
                      </div>
                      {avatarThemeError && (
                        <span className="mt-3 block text-[12px] text-[#d66d75]">
                          {avatarThemeError}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              )}

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

  const { className: rawMenuClass, left: rawMenuLeft } = profileMenuClass(
    placement,
    sidebarCollapsed,
  );
  // Inside a sheet the shell is the panel, so the menu is just its rows.
  const menuClassName = asSheet
    ? "[&_button]:min-h-[44px] [&_a]:min-h-[44px]"
    : rawMenuClass;
  const menuLeft = asSheet ? undefined : rawMenuLeft;
  const submenuSurfaceClass = (railSizeClass: string) =>
    asSheet ? SHEET_SUBMENU_CLASS : profileSubmenuClass(placement, railSizeClass);
  const submenuAnchorClass = asSheet ? "" : profileSubmenuAnchorClass(placement);
  // In the sheet a submenu replaces the list rather than floating over it.
  // Drilled into a submenu, the sheet shows that submenu alone. The bodies
  // already render conditionally, so only the root-level rows need standing
  // down; moving them would mean relocating 200 lines of markup for a class.
  const showRootRows = !asSheet || !activeSubmenu;
  const rootRow = showRootRows ? "" : " hidden";
  const sheetTitles: Record<string, string> = {
    data: t("settings.data.title", "Data Controls"),
    settings: t("settings.app.title", "Preferences"),
    help: t("settings.help.title", "Help & Legal"),
    feedback: t("feedback.title", "Feedback"),
  };

  const menu = (
    <div
      ref={menuRef}
      data-profile-menu-surface
      className={menuClassName}
      style={{
        left: menuLeft,
        boxShadow: "0 8px 32px rgba(0,0,0,0.12), 0 2px 8px rgba(0,0,0,0.06)",
      }}
    >
      {/* Profile */}
      <button
        onClick={() => openModal("profile")}
        className={`font-display flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5${rootRow}`}
      >
        <User className="h-4 w-4 text-black/50 dark:text-white/50" />
        {t("settings.profile.title", "Profile")}
        <span className="ml-auto flex shrink-0">{quickJumpBadge("profile")}</span>
      </button>

      {/* Data */}
      <div
        className={submenuAnchorClass}
        onMouseEnter={() => handleSubmenuEnter("data")}
        onMouseLeave={handleSubmenuLeave}
      >
        <button
          onClick={() => handleSubmenuToggle("data")}
          className={`font-display flex min-h-[38px] w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5${rootRow}`}
        >
          <div className="flex items-center gap-2.5">
            <Database className="h-4 w-4 text-black/50 dark:text-white/50" />
            {t("settings.data.title", "Data Controls")}
          </div>
          <span className="ml-auto flex shrink-0">{quickJumpBadge("data")}</span>
          {!isQuickJumpActive && (
            <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
          )}
        </button>
        {activeSubmenu === "data" && (
          <div
            className={submenuSurfaceClass("min-h-[294px] min-w-[304px]")}
            style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.1)" }}
            onMouseEnter={handleSubmenuKeepAlive}
            onMouseLeave={handleSubmenuLeave}
          >
            {memoryControlsAvailable ? (
              <button
                onClick={() => openModal("memory")}
                className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
              >
                <Brain className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
                <span className="whitespace-nowrap">
                  {t("settings.data.personalization.menu", "Personalization")}
                </span>
                <span className="ml-auto flex shrink-0">{quickJumpBadge("memory")}</span>
              </button>
            ) : null}
            {receiptsAvailable ? (
              <button
                onClick={() => openModal("receipts")}
                className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
              >
                <Link2 className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
                <span className="whitespace-nowrap">
                  {t("settings.data.shared_links", "Shared links")}
                </span>
                <span className="ml-auto flex shrink-0">
                  {quickJumpBadge("receipts")}
                </span>
              </button>
            ) : null}
            <button
              onClick={() => openModal("archived")}
              className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Archive className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
              <span className="whitespace-nowrap">
                {t("settings.data.archived_chats", "Archived chats")}
              </span>
              <span className="ml-auto flex shrink-0">{quickJumpBadge("archived")}</span>
            </button>
            <button
              onClick={() => openModal("deleted")}
              className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Trash2 className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
              <span className="whitespace-nowrap">
                {t("settings.data.recently_deleted", "Recently Deleted")}
              </span>
              <span className="ml-auto flex shrink-0">{quickJumpBadge("deleted")}</span>
            </button>
            <button
              onClick={() => {
                onClose();
                window.location.href = "/account/security";
              }}
              className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Shield className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
              <span className="whitespace-nowrap">
                {t("settings.data.security", "Security")}
              </span>
              <span className="ml-auto flex shrink-0">{quickJumpBadge("security")}</span>
            </button>
            <button
              onClick={() => openModal("usage")}
              className="flex min-h-11 w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Activity className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
              <span className="whitespace-nowrap">
                {t("settings.data.usage", "Usage")}
              </span>
              <span className="ml-auto flex shrink-0">{quickJumpBadge("usage")}</span>
            </button>
            <button
              onClick={handleDeleteAllConversations}
              className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] font-medium text-[#d66d75] transition-colors hover:bg-[#d66d75]/10 dark:hover:bg-[#d66d75]/10"
            >
              <Trash2 className="h-3.5 w-3.5" />
              <span className="whitespace-nowrap">
                {t("settings.data.delete_all_conversations", "Delete all conversations")}
              </span>
              <span className="ml-auto flex shrink-0">{quickJumpBadge("delete-all")}</span>
            </button>
            <button
              type="button"
              onClick={handleOpenDeleteRequest}
              className="flex min-h-[88px] w-full flex-col items-start gap-1 px-3.5 py-2 text-left text-[#d66d75] transition-colors hover:bg-[#d66d75]/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#d66d75]/25 dark:hover:bg-[#d66d75]/10"
            >
              <span className="flex h-[22px] w-full items-center gap-2.5 text-[13px] font-medium">
                <Trash2 className="h-3.5 w-3.5" />
                <span className="whitespace-nowrap">
                  {t("settings.profile.delete_account", "Delete account")}
                </span>
                <span className="ml-auto flex shrink-0">{quickJumpBadge("delete-account")}</span>
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
        className={submenuAnchorClass}
        onMouseEnter={() => handleSubmenuEnter("settings")}
        onMouseLeave={handleSubmenuLeave}
      >
        <button
          onClick={() => handleSubmenuToggle("settings")}
          className={`font-display flex min-h-[38px] w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5${rootRow}`}
        >
          <div className="flex items-center gap-2.5">
            <Palette className="h-4 w-4 text-black/50 dark:text-white/50" />
            {t("settings.preferences.title", "Preferences")}
          </div>
          <span className="ml-auto flex shrink-0">{quickJumpBadge("settings")}</span>
          {!isQuickJumpActive && (
            <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
          )}
        </button>
        {activeSubmenu === "settings" && (
          <div
            aria-label={t("settings.preferences.title", "Preferences")}
            className={submenuSurfaceClass("min-w-[248px]")}
            style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.1)" }}
            onMouseEnter={handleSubmenuKeepAlive}
            onMouseLeave={handleSubmenuLeave}
          >
            <button
              onClick={() => openModal("appearance")}
              className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Palette className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
              <span className="whitespace-nowrap">
                {t("settings.app.appearance", "Appearance")}
              </span>
              <span className="ml-auto flex shrink-0">{quickJumpBadge("appearance")}</span>
            </button>
            <button
              onClick={() => openModal("language")}
              className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Globe className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
              <span className="whitespace-nowrap">
                {t("settings.app.language", "Language")}
              </span>
              <span className="ml-auto flex shrink-0">{quickJumpBadge("language")}</span>
            </button>
            {onOpenSidebarPreference && (
              <button
                onClick={() => {
                  onOpenSidebarPreference();
                  onClose();
                }}
                className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
              >
                <PanelLeft className="h-3.5 w-3.5 text-black/60 dark:text-white/60" />
                <span className="whitespace-nowrap">
                  {t("settings.app.sidebar", "Sidebar")}
                </span>
                <span className="ml-auto flex shrink-0">{quickJumpBadge("sidebar")}</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Help */}
      <div
        className={submenuAnchorClass}
        onMouseEnter={() => handleSubmenuEnter("help")}
        onMouseLeave={handleSubmenuLeave}
      >
        <button
          onClick={() => handleSubmenuToggle("help")}
          className={`font-display flex min-h-[38px] w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5${rootRow}`}
        >
          <div className="flex items-center gap-2.5">
            <HelpCircle className="h-4 w-4 text-black/50 dark:text-white/50" />
            {t("settings.help.title", "Help & Legal")}
          </div>
          <span className="ml-auto flex shrink-0">{quickJumpBadge("help")}</span>
          {!isQuickJumpActive && (
            <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
          )}
        </button>
        {activeSubmenu === "help" && (
          <div
            className={`${submenuSurfaceClass("min-w-[248px]")} [&>a]:mx-1 [&>a]:my-0.5 [&>a]:w-[calc(100%-0.5rem)] [&>a]:rounded-[10px]`}
            style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.1)" }}
            onMouseEnter={handleSubmenuKeepAlive}
            onMouseLeave={handleSubmenuLeave}
          >
            {/* A phone has no keyboard to shortcut, so it is not offered there. */}
            {isDrawerPlacement ? null : (
            <button
              type="button"
              onClick={handleOpenKeyboardShortcuts}
              className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black transition-colors hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Keyboard className="h-3.5 w-3.5" />
              <span className="whitespace-nowrap">
                {t("keyboard_shortcuts.menu_item", "Keyboard shortcuts")}
              </span>
              <span className="ml-auto flex shrink-0">{quickJumpBadge("keyboard-shortcuts")}</span>
            </button>
            )}
            <a href="/terms" className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black transition-colors hover:bg-black/5 dark:text-white dark:hover:bg-white/5">
              <FileText className="h-3.5 w-3.5" />
              <span className="whitespace-nowrap">
                {t("settings.help.terms", "Terms of Use")}
              </span>
              <span className="ml-auto flex shrink-0">{quickJumpBadge("terms")}</span>
            </a>
            <a href="/privacy" className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black transition-colors hover:bg-black/5 dark:text-white dark:hover:bg-white/5">
              <Shield className="h-3.5 w-3.5" />
              <span className="whitespace-nowrap">
                {t("settings.help.privacy", "Privacy Policy")}
              </span>
              <span className="ml-auto flex shrink-0">{quickJumpBadge("privacy")}</span>
            </a>
          </div>
        )}
      </div>

      {/* Feedback */}
      <div
        className={submenuAnchorClass}
        onMouseEnter={() => handleSubmenuEnter("feedback")}
        onMouseLeave={handleSubmenuLeave}
      >
        <button
          onClick={() => handleSubmenuToggle("feedback")}
          className={`font-display flex min-h-[38px] w-full items-center justify-between gap-2.5 px-3.5 py-2 text-[13px] font-medium text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5${rootRow}`}
        >
          <div className="flex items-center gap-2.5">
            <MessageSquareText className="h-4 w-4 text-black/50 dark:text-white/50" />
            {t("feedback.eyebrow", "Feedback")}
          </div>
          <span className="ml-auto flex shrink-0">{quickJumpBadge("feedback")}</span>
          {!isQuickJumpActive && (
            <ChevronRight className="h-3.5 w-3.5 text-black/30 dark:text-white/30" />
          )}
        </button>
        {activeSubmenu === "feedback" && (
          <div
            className={submenuSurfaceClass("min-w-[248px]")}
            style={{ boxShadow: "0 4px 20px rgba(0,0,0,0.1)" }}
            onMouseEnter={handleSubmenuKeepAlive}
            onMouseLeave={handleSubmenuLeave}
          >
            <button
              onClick={() => {
                onFeedback?.("bug");
                onClose();
              }}
              className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Bug className="h-3.5 w-3.5" />
              <span className="whitespace-nowrap">
                {t("feedback.type.bug", "Report a bug")}
              </span>
              <span className="ml-auto flex shrink-0">{quickJumpBadge("feedback-bug")}</span>
            </button>
            <button
              onClick={() => {
                onFeedback?.("feature");
                onClose();
              }}
              className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <Lightbulb className="h-3.5 w-3.5" />
              <span className="whitespace-nowrap">
                {t("feedback.type.feature", "Request a feature")}
              </span>
              <span className="ml-auto flex shrink-0">{quickJumpBadge("feedback-feature")}</span>
            </button>
            <button
              onClick={() => {
                onFeedback?.("general");
                onClose();
              }}
              className="flex min-h-[38px] w-full items-center gap-2.5 px-3.5 py-2 text-[13px] text-black hover:bg-black/5 dark:text-white dark:hover:bg-white/5"
            >
              <MessageCircle className="h-3.5 w-3.5" />
              <span className="whitespace-nowrap">
                {t("feedback.type.general", "General feedback")}
              </span>
              <span className="ml-auto flex shrink-0">{quickJumpBadge("feedback-general")}</span>
            </button>
          </div>
        )}
      </div>

      {/* Divider */}
      <div className={`my-1 border-t border-black/5 dark:border-white/5${rootRow}`} />

      {/* Log out */}
      <button
        onClick={() => {
          onLogout();
          onClose();
        }}
        className={`font-display flex w-full items-center gap-2.5 px-3.5 py-2 text-[13px] font-medium text-[#d66d75] hover:bg-black/5 dark:hover:bg-white/5${rootRow}`}
      >
        <LogOut className="h-4 w-4" />
        {t("settings.logout", "Log out")}
      </button>

      {/* Footer links */}
      <div className={`my-1 border-t border-black/5 dark:border-white/5${rootRow}`} />
      <div className={`flex items-center gap-1 px-3.5 py-1.5 text-[10px] text-black/25 dark:text-white/25${rootRow}`}>
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

  if (typeof document === "undefined") return null;

  if (asSheet) {
    // The sheet supplies the panel, the title and the way back, so the menu
    // contributes only its rows.
    const sheet = (
      <AdaptivePanel
        title={
          activeSubmenu
            ? sheetTitles[activeSubmenu]
            : t("common.settings", "Settings")
        }
        closeLabel={t("common.close", "Close")}
        onClose={onClose}
        onBack={activeSubmenu ? () => setActiveSubmenu(null) : undefined}
        backLabel={t("common.settings", "Settings")}
      >
        {menu}
      </AdaptivePanel>
    );
    return (
      <>
        {createPortal(sheet, document.body)}
        {deleteRequestDialog
          ? createPortal(deleteRequestDialog, document.body)
          : null}
      </>
    );
  }

  return (
    <>
      {isDrawerPlacement ? menu : createPortal(menu, document.body)}
      {deleteRequestDialog
        ? createPortal(deleteRequestDialog, document.body)
        : null}
    </>
  );
}
