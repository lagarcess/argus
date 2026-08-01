"use client";

import type { HistoryItem } from "@/lib/argus-api";
import KeyboardShortcutsOverlay from "@/components/sidebar/KeyboardShortcutsOverlay";
import RecentsQuickPeek from "@/components/sidebar/RecentsQuickPeek";

type KeyboardShortcutSurfacesProps = {
  keyboardShortcutsOpen: boolean;
  onCloseKeyboardShortcuts: () => void;
  recentsQuickPeekOpen: boolean;
  historyItems: HistoryItem[];
  activeConversationId: string | null;
  onOpenHistoryItem: (item: HistoryItem) => void;
  onCloseRecentsQuickPeek: () => void;
};

export function KeyboardShortcutSurfaces({
  keyboardShortcutsOpen,
  onCloseKeyboardShortcuts,
  recentsQuickPeekOpen,
  historyItems,
  activeConversationId,
  onOpenHistoryItem,
  onCloseRecentsQuickPeek,
}: KeyboardShortcutSurfacesProps) {
  return (
    <>
      {recentsQuickPeekOpen && (
        <RecentsQuickPeek
          historyItems={historyItems}
          activeConversationId={activeConversationId}
          onOpenItem={(item) => {
            onCloseRecentsQuickPeek();
            onOpenHistoryItem(item);
          }}
          onClose={onCloseRecentsQuickPeek}
        />
      )}
      {keyboardShortcutsOpen && (
        <KeyboardShortcutsOverlay onClose={onCloseKeyboardShortcuts} />
      )}
    </>
  );
}
