import { describe, expect, test } from "bun:test";
import * as keyboardShortcuts from "../lib/keyboard-shortcuts";

const {
  KEYBOARD_SHORTCUTS,
  isKeyboardShortcutHintModifierActive,
  keyboardShortcutHintDisplay,
  keyboardShortcutDisplay,
  matchesKeyboardShortcut,
  commandPaletteRowActionForEvent,
  quickJumpHintDisplay,
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
      "command_palette_rename",
      "command_palette_archive",
      "command_palette_delete",
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
    expect(quickJumpHintDisplay(1, true)).toBe("⌘⌥1");
    expect(quickJumpHintDisplay(9, false)).toBe("Ctrl+Shift+9");
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

  test("owns Omnisearch row actions in the shared registry without using browser commands", () => {
    expect(KEYBOARD_SHORTCUTS).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "command_palette_rename",
          group: "omnisearch",
          code: "F2",
        }),
        expect.objectContaining({
          id: "command_palette_archive",
          group: "omnisearch",
          code: "F2",
        }),
        expect.objectContaining({
          id: "command_palette_delete",
          group: "omnisearch",
          code: "Delete",
        }),
      ]),
    );
    expect(
      commandPaletteRowActionForEvent({
        key: "F2",
        code: "F2",
        metaKey: false,
        ctrlKey: false,
        shiftKey: false,
        altKey: false,
      }),
    ).toBe("rename");
    expect(
      commandPaletteRowActionForEvent({
        key: "F2",
        code: "F2",
        metaKey: false,
        ctrlKey: false,
        shiftKey: true,
        altKey: false,
      }),
    ).toBe("archive");
    expect(
      commandPaletteRowActionForEvent({
        key: "Delete",
        code: "Delete",
        metaKey: false,
        ctrlKey: false,
        shiftKey: false,
        altKey: false,
      }),
    ).toBe("delete");
    expect(
      commandPaletteRowActionForEvent({
        key: "x",
        code: "KeyX",
        metaKey: true,
        ctrlKey: false,
        shiftKey: true,
        altKey: false,
      }),
    ).toBeNull();
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

  test("ignores auto-repeat for actions and quick-jump digits", () => {
    expect(
      matchesKeyboardShortcut("keyboard_shortcuts", {
        key: "/",
        code: "Slash",
        metaKey: true,
        ctrlKey: false,
        shiftKey: false,
        altKey: false,
        repeat: true,
      }),
    ).toBe(false);
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
          repeat: true,
        },
        true,
      ),
    ).toBeNull();
  });
});
