type KeyboardShortcutSurfaceState = {
  searchOverlayOpen: boolean;
  recentsQuickPeekOpen: boolean;
  deleteConfirmationOpen: boolean;
  modalOpen: boolean;
  /**
   * Whether the layer registry has anything open, asked at press time.
   *
   * The named flags beside it are a list somebody has to remember to extend,
   * and the surface added most recently was not on it: between 720 and 1024 the
   * settings panel is a sheet, so Open Recents mounted Quick Peek underneath it
   * and moved focus into a dialog nobody could see. The registry is the only
   * thing that knows what is open now, which is why the Omnisearch key already
   * asks it rather than naming surfaces.
   */
  anyOverlayOpen?: boolean;
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
  anyOverlayOpen = false,
  shortcutsOverlayOpen = false,
}: KeyboardShortcutSurfaceState): boolean {
  // This shortcut toggles, so its own overlay is never a reason to refuse it.
  // Opened from the drawer's Help submenu the drawer stays open underneath,
  // which kept `modalOpen` true and left the advertised key unable to close
  // the dialog it had just opened. It is also why the registry cannot be
  // consulted before this line: the overlay it would report is this one.
  if (shortcutsOverlayOpen) return true;
  return !(
    searchOverlayOpen ||
    recentsQuickPeekOpen ||
    deleteConfirmationOpen ||
    modalOpen ||
    anyOverlayOpen
  );
}

export function canManageFocusedConversation({
  isChatView,
  canManageConversation,
  conversationId,
}: FocusedConversationState): boolean {
  return isChatView && canManageConversation && conversationId !== null;
}
