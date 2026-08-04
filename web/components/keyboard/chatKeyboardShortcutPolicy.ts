type KeyboardShortcutSurfaceState = {
  searchOverlayOpen: boolean;
  recentsQuickPeekOpen: boolean;
  deleteConfirmationOpen: boolean;
  modalOpen: boolean;
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
}: KeyboardShortcutSurfaceState): boolean {
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
