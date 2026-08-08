"use client";

import { useCallback, type Dispatch, type RefObject, type SetStateAction } from "react";
import {
  dossierPaneKeyboardAction,
  dossierPaneTransition,
  type DossierPaneState,
} from "@/lib/command-palette-dossier-integration";
import {
  commandPaletteKeyboardAction,
  isEditableKeyboardTarget,
} from "@/lib/command-palette-items";

/**
 * Every key Omnisearch answers for, in one place.
 *
 * The palette owns arrows, rename, archive, delete, the dossier pane, and
 * Escape, which is a lot of policy to keep inline in a component that is also
 * the largest surface in the app. It is handed to the layer registry as a
 * single keydown, so it only ever runs while the palette is the topmost layer.
 *
 * Generic over the row type: this decides *when* an action fires, never what a
 * row is.
 */
export function useCommandPaletteKeys<Item extends { canManageConversation?: boolean }>({
  cancelRename,
  canManageConversation,
  dossierPaneState,
  editingId,
  handleArchive,
  handleDelete,
  inputRef,
  keyboardItems,
  onClose,
  openRow,
  pendingDeleteItem,
  selectedNavigationDisabled,
  selectedPreview,
  setDossierPaneState,
  setPreviewItem,
  startRename,
  usesCommandKey,
}: {
  cancelRename: () => void;
  canManageConversation: boolean;
  dossierPaneState: DossierPaneState;
  editingId: string | null;
  handleArchive: (item: Item) => void | Promise<void>;
  handleDelete: (item: Item, viaKeyboard: boolean) => void;
  inputRef: RefObject<HTMLInputElement | null>;
  keyboardItems: readonly Item[];
  onClose: () => void;
  openRow: (
    item: Item,
    options: { navigationDisabled: boolean; openAtLeftOff?: boolean },
  ) => void;
  pendingDeleteItem: Item | null;
  selectedNavigationDisabled: boolean;
  selectedPreview: Item | null;
  setDossierPaneState: Dispatch<SetStateAction<DossierPaneState>>;
  setPreviewItem: (item: Item) => void;
  startRename: (item: Item) => void;
  usesCommandKey: boolean;
}): (event: KeyboardEvent) => void {
  return useCallback(
    (event: KeyboardEvent) => {
    if (pendingDeleteItem) return;
    const eventTarget =
      event.target instanceof HTMLElement ? event.target : null;
    // The three-dot is a control, not the row: activating the row from it
    // opened the dossier instead of the menu. Only activation is skipped,
    // since standing the whole handler down swallows Escape while the
    // trigger holds focus.
    if (
      (event.key === "Enter" || event.key === " ") &&
      eventTarget?.closest("[data-row-action]")
    ) {
      return;
    }
    const targetIsEditableDossierControl = Boolean(
      eventTarget?.closest("[data-dossier-pane]") &&
        isEditableKeyboardTarget(eventTarget),
    );
    const targetIsDossierControl = Boolean(
      eventTarget?.closest("[data-dossier-pane]") &&
        (isEditableKeyboardTarget(eventTarget) ||
          eventTarget.closest("button")),
    );
    const dossierKeyboardAction = dossierPaneKeyboardAction({
      key: event.key,
      metaKey: event.metaKey,
      ctrlKey: event.ctrlKey,
      targetIsDossierControl,
      targetIsEditable: targetIsEditableDossierControl,
      state: dossierPaneState,
    });
    if (dossierKeyboardAction === "restore_latest") {
      event.preventDefault();
      setDossierPaneState((current) =>
        dossierPaneTransition(current, { type: "restore_latest" }),
      );
      return;
    }
    if (dossierKeyboardAction === "suppress_navigation") {
      event.preventDefault();
      return;
    }
    if (dossierKeyboardAction === "allow_control") return;
    if (event.key === "Escape") {
      event.preventDefault();
      if (editingId) {
        cancelRename();
        return;
      }
      onClose();
      return;
    }
    const action = commandPaletteKeyboardAction({
      key: event.key,
      code: event.code,
      itemCount: keyboardItems.length,
      hasSelection: Boolean(selectedPreview),
      selectedCanManageConversation: Boolean(
        canManageConversation && selectedPreview?.canManageConversation,
      ),
      targetIsEditable: isEditableKeyboardTarget(event.target),
      targetIsSearchInput: event.target === inputRef.current,
      isEditing: Boolean(editingId),
      metaKey: event.metaKey,
      ctrlKey: event.ctrlKey,
      shiftKey: event.shiftKey,
      altKey: event.altKey,
      repeat: event.repeat,
      focusedRowIndex: Number(
        eventTarget?.closest<HTMLElement>("[data-palette-row-index]")
          ?.dataset.paletteRowIndex ?? -1,
      ),
      usesCommandKey,
    });
    if (action.type === "focus_search") {
      event.preventDefault();
      inputRef.current?.focus();
      return;
    }
    if (action.type === "select") {
      event.preventDefault();
      const item = keyboardItems[action.index];
      setPreviewItem(item);
      document
        .querySelector<HTMLElement>(
          `[data-palette-row-index="${action.index}"]`,
        )
        ?.focus();
      return;
    }
    if (action.type === "open" && selectedPreview) {
      event.preventDefault();
      openRow(selectedPreview, {
        navigationDisabled: selectedNavigationDisabled,
        openAtLeftOff: action.openAtLeftOff,
      });
      return;
    }
    if (action.type === "rename" && selectedPreview) {
      event.preventDefault();
      startRename(selectedPreview);
      return;
    }
    if (action.type === "archive" && selectedPreview) {
      event.preventDefault();
      void handleArchive(selectedPreview);
      return;
    }
    if (action.type === "delete" && selectedPreview) {
      event.preventDefault();
      handleDelete(selectedPreview, true);
    }
        },
    [
      cancelRename,
      canManageConversation,
      dossierPaneState,
      editingId,
      handleArchive,
      handleDelete,
      inputRef,
      keyboardItems,
      onClose,
      openRow,
      pendingDeleteItem,
      selectedNavigationDisabled,
      selectedPreview,
      setDossierPaneState,
      setPreviewItem,
      startRename,
      usesCommandKey,
    ],
  );
}
