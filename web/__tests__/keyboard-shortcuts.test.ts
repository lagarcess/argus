import { describe, expect, test } from "bun:test";
import * as keyboardShortcuts from "../lib/keyboard-shortcuts";

const {
  KEYBOARD_SHORTCUTS,
  isKeyboardShortcutHintModifierActive,
  keyboardShortcutHintDisplay,
  keyboardShortcutDisplay,
  matchesKeyboardShortcut,
} = keyboardShortcuts;
const quickJumpIndexForEvent = (
  keyboardShortcuts as typeof keyboardShortcuts & {
    quickJumpIndexForEvent?: (
      event: Parameters<typeof matchesKeyboardShortcut>[1],
      usesCommandKey: boolean,
    ) => number | null;
  }
).quickJumpIndexForEvent;

describe("keyboard shortcut registry", () => {
  test("defines the searchable actions once for handlers and the overlay", () => {
    expect(KEYBOARD_SHORTCUTS.map((shortcut) => shortcut.id)).toEqual([
      "omnisearch",
      "keyboard_shortcuts",
      "open_recents",
      "expand_sidebar_recents",
      "open_settings",
      "new_chat",
      "delete_focused_chat",
      "rename_focused_chat",
      "toggle_pin_focused_chat",
      "quick_jump",
    ]);
    expect(KEYBOARD_SHORTCUTS.every((shortcut) => shortcut.labelKey)).toBe(true);
  });

  test("matches Command or Control without matching a bare modifier", () => {
    expect(
      matchesKeyboardShortcut("omnisearch", {
        key: "k",
        code: "KeyK",
        metaKey: true,
        ctrlKey: false,
        shiftKey: false,
        altKey: false,
      }),
    ).toBe(true);
    expect(
      matchesKeyboardShortcut("omnisearch", {
        key: "K",
        code: "KeyK",
        metaKey: false,
        ctrlKey: true,
        shiftKey: false,
        altKey: false,
      }),
    ).toBe(true);
    expect(
      matchesKeyboardShortcut("keyboard_shortcuts", {
        key: "/",
        code: "Slash",
        metaKey: false,
        ctrlKey: true,
        shiftKey: false,
        altKey: false,
      }),
    ).toBe(true);
    expect(
      matchesKeyboardShortcut("keyboard_shortcuts", {
        key: "Control",
        code: "ControlLeft",
        metaKey: false,
        ctrlKey: true,
        shiftKey: false,
        altKey: false,
      }),
    ).toBe(false);
  });

  test("formats the shared bindings for Mac and Windows/Linux", () => {
    expect(keyboardShortcutDisplay("keyboard_shortcuts", true)).toEqual([
      "⌘",
      "/",
    ]);
    expect(keyboardShortcutDisplay("omnisearch", false)).toEqual([
      "Ctrl",
      "K",
    ]);
    expect(keyboardShortcutDisplay("open_recents", true)).toEqual([
      "⌘",
      "Shift",
      ",",
    ]);
    expect(keyboardShortcutDisplay("quick_jump", false)).toEqual([
      "Ctrl",
      "Shift",
      "1–9",
    ]);
    expect(keyboardShortcutHintDisplay("new_chat", true)).toBe("⌘⇧.");
    expect(keyboardShortcutHintDisplay("omnisearch", false)).toBe("Ctrl+K");
  });

  test("reveals shortcut hints while the platform primary modifier is held", () => {
    expect(
      isKeyboardShortcutHintModifierActive(
        {
          key: "Meta",
          code: "MetaLeft",
          metaKey: true,
          ctrlKey: false,
          shiftKey: false,
          altKey: false,
        },
        true,
      ),
    ).toBe(true);
    expect(
      isKeyboardShortcutHintModifierActive(
        {
          key: "Control",
          code: "ControlLeft",
          metaKey: false,
          ctrlKey: true,
          shiftKey: false,
          altKey: false,
        },
        false,
      ),
    ).toBe(true);
    expect(
      isKeyboardShortcutHintModifierActive(
        {
          key: "AltGraph",
          code: "AltRight",
          metaKey: false,
          ctrlKey: true,
          shiftKey: false,
          altKey: true,
        },
        false,
      ),
    ).toBe(false);
  });

  test("matches finalized action bindings by physical key code", () => {
    expect(
      matchesKeyboardShortcut("open_recents", {
        key: "<",
        code: "Comma",
        metaKey: true,
        ctrlKey: false,
        shiftKey: true,
        altKey: false,
      }),
    ).toBe(true);
    expect(
      matchesKeyboardShortcut("open_recents", {
        key: ",",
        code: "Comma",
        metaKey: false,
        ctrlKey: true,
        shiftKey: false,
        altKey: false,
      }),
    ).toBe(false);
    expect(
      matchesKeyboardShortcut("rename_focused_chat", {
        key: "F2",
        code: "F2",
        metaKey: false,
        ctrlKey: false,
        shiftKey: false,
        altKey: false,
      }),
    ).toBe(true);
  });

  test("matches quick-jump digits by code across shifted layouts", () => {
    expect(quickJumpIndexForEvent).toBeTypeOf("function");
    if (!quickJumpIndexForEvent) return;
    expect(
      quickJumpIndexForEvent(
        {
          key: "1",
          code: "Digit1",
          metaKey: true,
          ctrlKey: false,
          shiftKey: false,
          altKey: true,
        },
        true,
      ),
    ).toBe(0);
    expect(
      quickJumpIndexForEvent(
        {
          key: "@",
          code: "Digit2",
          metaKey: false,
          ctrlKey: true,
          shiftKey: true,
          altKey: false,
        },
        false,
      ),
    ).toBe(1);
    expect(
      quickJumpIndexForEvent(
        {
          key: "@",
          code: "Digit2",
          metaKey: false,
          ctrlKey: true,
          shiftKey: true,
          altKey: true,
        },
        false,
      ),
    ).toBeNull();
  });
});
