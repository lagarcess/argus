"use client";

import { useEffect, useRef, useState } from "react";
import {
  canManageFocusedConversation,
  canOpenKeyboardShortcuts,
} from "./chatKeyboardShortcutPolicy";
import { matchesKeyboardShortcut } from "@/lib/keyboard-shortcuts";
import { nextSidebarRecentsState } from "@/lib/sidebar-shortcuts";

type UseChatKeyboardShortcutsOptions = {
  isChatView: boolean;
  canManageConversation: boolean;
  conversationId: string | null;
  isGuest: boolean;
  searchOverlayOpen: boolean;
  deleteConfirmationOpen: boolean;
  modalOpen: boolean;
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  recentsExpanded: boolean;
  setRecentsExpanded: (expanded: boolean) => void;
  requestNewChat: () => void;
  closeTransientSidebar: () => void;
  requestDelete: () => void;
  startRename: () => void;
  archiveConversation: () => void | Promise<void>;
  toggleRead: () => void | Promise<void>;
  togglePin: () => void | Promise<void>;
  showChatOptions: () => void;
};

export function useChatKeyboardShortcuts(
  options: UseChatKeyboardShortcutsOptions,
) {
  const optionsRef = useRef(options);
  const [keyboardShortcutsOpen, setKeyboardShortcutsOpen] = useState(false);
  const [isRecentsQuickPeekOpen, setIsRecentsQuickPeekOpen] = useState(false);
  const [settingsOpenRequest, setSettingsOpenRequest] = useState(0);

  useEffect(() => {
    optionsRef.current = options;
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const current = optionsRef.current;
      if (
        !matchesKeyboardShortcut("keyboard_shortcuts", event) ||
        !canOpenKeyboardShortcuts({
          searchOverlayOpen: current.searchOverlayOpen,
          recentsQuickPeekOpen: isRecentsQuickPeekOpen,
          deleteConfirmationOpen: current.deleteConfirmationOpen,
          modalOpen: current.modalOpen,
          shortcutsOverlayOpen: keyboardShortcutsOpen,
        })
      ) {
        return;
      }
      event.preventDefault();
      setKeyboardShortcutsOpen((open) => !open);
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [isRecentsQuickPeekOpen, keyboardShortcutsOpen]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      const current = optionsRef.current;
      if (
        keyboardShortcutsOpen ||
        current.searchOverlayOpen ||
        isRecentsQuickPeekOpen ||
        current.deleteConfirmationOpen ||
        current.modalOpen
      ) {
        return;
      }

      if (matchesKeyboardShortcut("new_chat", event)) {
        event.preventDefault();
        setIsRecentsQuickPeekOpen(false);
        current.requestNewChat();
        current.closeTransientSidebar();
        return;
      }
      if (matchesKeyboardShortcut("open_recents", event)) {
        event.preventDefault();
        current.setRecentsExpanded(false);
        setIsRecentsQuickPeekOpen(true);
        return;
      }
      if (matchesKeyboardShortcut("expand_sidebar_recents", event)) {
        event.preventDefault();
        setIsRecentsQuickPeekOpen(false);
        const nextState = nextSidebarRecentsState(
          current.sidebarOpen,
          current.recentsExpanded,
        );
        current.setSidebarOpen(nextState.sidebarOpen);
        current.setRecentsExpanded(nextState.recentsExpanded);
        return;
      }
      if (matchesKeyboardShortcut("open_settings", event) && !current.isGuest) {
        event.preventDefault();
        setIsRecentsQuickPeekOpen(false);
        setSettingsOpenRequest((request) => request + 1);
        return;
      }
      if (
        !canManageFocusedConversation({
          isChatView: current.isChatView,
          canManageConversation: current.canManageConversation,
          conversationId: current.conversationId,
        })
      ) {
        return;
      }

      if (matchesKeyboardShortcut("delete_focused_chat", event)) {
        event.preventDefault();
        current.requestDelete();
        return;
      }
      if (matchesKeyboardShortcut("rename_focused_chat", event)) {
        event.preventDefault();
        current.showChatOptions();
        current.startRename();
        return;
      }
      if (matchesKeyboardShortcut("archive_focused_chat", event)) {
        event.preventDefault();
        void current.archiveConversation();
        return;
      }
      if (matchesKeyboardShortcut("toggle_read_focused_chat", event)) {
        event.preventDefault();
        void current.toggleRead();
        return;
      }
      if (matchesKeyboardShortcut("toggle_pin_focused_chat", event)) {
        event.preventDefault();
        void current.togglePin();
      }
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [isRecentsQuickPeekOpen, keyboardShortcutsOpen]);

  return {
    keyboardShortcutsOpen,
    setKeyboardShortcutsOpen,
    isRecentsQuickPeekOpen,
    setIsRecentsQuickPeekOpen,
    settingsOpenRequest,
  };
}
