export type KeyboardShortcutId = "omnisearch" | "keyboard_shortcuts";

export type KeyboardShortcutEvent = Pick<
  KeyboardEvent,
  "ctrlKey" | "key" | "metaKey"
>;

export type KeyboardShortcutDefinition = {
  id: KeyboardShortcutId;
  labelKey: string;
  key: string;
};

export const KEYBOARD_SHORTCUTS: readonly KeyboardShortcutDefinition[] = [
  {
    id: "omnisearch",
    labelKey: "keyboard_shortcuts.shortcuts.omnisearch",
    key: "k",
  },
  {
    id: "keyboard_shortcuts",
    labelKey: "keyboard_shortcuts.shortcuts.keyboard_shortcuts",
    key: "/",
  },
];

function keyboardShortcut(id: KeyboardShortcutId): KeyboardShortcutDefinition {
  const shortcut = KEYBOARD_SHORTCUTS.find((item) => item.id === id);
  if (!shortcut) {
    throw new Error(`Unknown keyboard shortcut: ${id}`);
  }
  return shortcut;
}

export function matchesKeyboardShortcut(
  id: KeyboardShortcutId,
  event: KeyboardShortcutEvent,
): boolean {
  const shortcut = keyboardShortcut(id);
  return (
    (event.metaKey || event.ctrlKey) &&
    event.key.toLowerCase() === shortcut.key
  );
}

export function keyboardShortcutDisplay(
  id: KeyboardShortcutId,
  usesCommandKey: boolean,
): readonly [string, string] {
  const shortcut = keyboardShortcut(id);
  return [usesCommandKey ? "⌘" : "Ctrl", shortcut.key.toUpperCase()];
}
