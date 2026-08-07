type KeyboardShortcutSurfaceState = {
  searchOverlayOpen: boolean;
  recentsQuickPeekOpen: boolean;
  deleteConfirmationOpen: boolean;
  modalOpen: boolean;
  /** The overlay this shortcut toggles, when it is already open. */
  shortcutsOverlayOpen?: boolean;
};

type FocusedConversationState = {
  isChatView: boolean;
  canManageConversation: boolean;
  conversationId: string | null;
};

export function canOpenKeyboardShortcuts({
  searchOverlayOpen,
  recentsQuickPeekOpen,
  deleteConfirmationOpen,
  modalOpen,
  shortcutsOverlayOpen = false,
}: KeyboardShortcutSurfaceState): boolean {
  // This shortcut toggles, so its own overlay is never a reason to refuse it.
  // Opened from the drawer's Help submenu the drawer stays open underneath,
  // which kept `modalOpen` true and left the advertised key unable to close
  // the dialog it had just opened.
  if (shortcutsOverlayOpen) return true;
  return !(
    searchOverlayOpen ||
    recentsQuickPeekOpen ||
    deleteConfirmationOpen ||
    modalOpen
  );
}

export function canManageFocusedConversation({
  isChatView,
  canManageConversation,
  conversationId,
}: FocusedConversationState): boolean {
  return isChatView && canManageConversation && conversationId !== null;
}
