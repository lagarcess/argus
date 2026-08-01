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
});
