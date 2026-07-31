import { describe, expect, test } from "bun:test";
import {
  KEYBOARD_SHORTCUTS,
  keyboardShortcutDisplay,
  matchesKeyboardShortcut,
} from "../lib/keyboard-shortcuts";

describe("keyboard shortcut registry", () => {
  test("defines the searchable actions once for handlers and the overlay", () => {
    expect(KEYBOARD_SHORTCUTS.map((shortcut) => shortcut.id)).toEqual([
      "omnisearch",
      "keyboard_shortcuts",
    ]);
    expect(KEYBOARD_SHORTCUTS.every((shortcut) => shortcut.labelKey)).toBe(true);
  });

  test("matches Command or Control without matching a bare modifier", () => {
    expect(
      matchesKeyboardShortcut("omnisearch", {
        key: "k",
        metaKey: true,
        ctrlKey: false,
      }),
    ).toBe(true);
    expect(
      matchesKeyboardShortcut("omnisearch", {
        key: "K",
        metaKey: false,
        ctrlKey: true,
      }),
    ).toBe(true);
    expect(
      matchesKeyboardShortcut("keyboard_shortcuts", {
        key: "/",
        metaKey: false,
        ctrlKey: true,
      }),
    ).toBe(true);
    expect(
      matchesKeyboardShortcut("keyboard_shortcuts", {
        key: "Control",
        metaKey: false,
        ctrlKey: true,
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
  });
});
