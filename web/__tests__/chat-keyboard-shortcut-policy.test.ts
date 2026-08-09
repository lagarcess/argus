import { describe, expect, test } from "bun:test";
import {
  canManageFocusedConversation,
  canOpenKeyboardShortcuts,
} from "../components/keyboard/chatKeyboardShortcutPolicy";

describe("chat keyboard shortcut policy", () => {
  test("keeps conversation mutations on the visible chat view", () => {
    expect(
      canManageFocusedConversation({
        isChatView: false,
        canManageConversation: true,
        conversationId: "hidden-chat",
      }),
    ).toBe(false);
    expect(
      canManageFocusedConversation({
        isChatView: true,
        canManageConversation: true,
        conversationId: "visible-chat",
      }),
    ).toBe(true);
  });

  test("does not stack shortcut help above another keyboard surface", () => {
    expect(
      canOpenKeyboardShortcuts({
        searchOverlayOpen: true,
        recentsQuickPeekOpen: false,
        deleteConfirmationOpen: false,
      }),
    ).toBe(false);
    expect(
      canOpenKeyboardShortcuts({
        searchOverlayOpen: false,
        recentsQuickPeekOpen: false,
        deleteConfirmationOpen: false,
      }),
    ).toBe(true);
  });

  test("the shortcut can always close the overlay it opened", () => {
    // Opened from the drawer's Help submenu the drawer stays open underneath,
    // so `modalOpen` is true and the advertised key could not close the dialog
    // it had just opened. A toggle must never be blocked by its own target.
    expect(
      canOpenKeyboardShortcuts({
        searchOverlayOpen: false,
        recentsQuickPeekOpen: false,
        deleteConfirmationOpen: false,
        modalOpen: true,
        shortcutsOverlayOpen: true,
      }),
    ).toBe(true);

    // Unrelated modals still block opening it in the first place.
    expect(
      canOpenKeyboardShortcuts({
        searchOverlayOpen: false,
        recentsQuickPeekOpen: false,
        deleteConfirmationOpen: false,
        modalOpen: true,
        shortcutsOverlayOpen: false,
      }),
    ).toBe(false);
  });
});
