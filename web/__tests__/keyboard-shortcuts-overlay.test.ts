import { describe, expect, test } from "bun:test";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

function source(relativePath: string): string {
  return readFileSync(join(root, relativePath), "utf-8");
}

describe("keyboard shortcuts overlay", () => {
  test("uses the central registry for the overlay, handler, and Help entry", () => {
    const overlayPath = join(
      root,
      "components/sidebar/KeyboardShortcutsOverlay.tsx",
    );

    expect(existsSync(overlayPath)).toBe(true);
    if (!existsSync(overlayPath)) return;

    const overlay = readFileSync(overlayPath, "utf-8");
    const chat = source("components/chat/ChatInterface.tsx");
    const guestShellActions = source("components/guest/useGuestShellActions.ts");
    const menu = source("components/sidebar/ProfileMenu.tsx");

    expect(overlay).toContain("KEYBOARD_SHORTCUTS.map");
    expect(chat).toContain('matchesKeyboardShortcut("keyboard_shortcuts", event)');
    expect(guestShellActions).toContain(
      'matchesKeyboardShortcut("omnisearch", event)',
    );
    expect(menu).toContain("onOpenKeyboardShortcuts");
  });

  test("localizes every overlay label in English and Spanish", () => {
    const en = JSON.parse(source("public/locales/en/common.json"));
    const es = JSON.parse(source("public/locales/es-419/common.json"));

    expect(en.keyboard_shortcuts.title).toBe("Keyboard shortcuts");
    expect(en.keyboard_shortcuts.shortcuts.omnisearch).toBe("Open search");
    expect(en.keyboard_shortcuts.shortcuts.keyboard_shortcuts).toBe(
      "Show keyboard shortcuts",
    );
    expect(es.keyboard_shortcuts.title).toBe("Atajos de teclado");
    expect(es.keyboard_shortcuts.shortcuts.omnisearch).toBe(
      "Abrir búsqueda",
    );
    expect(es.keyboard_shortcuts.shortcuts.keyboard_shortcuts).toBe(
      "Mostrar atajos de teclado",
    );
  });

  test("shares numbered quick-jump behavior between Recents and Settings", () => {
    const sidebar = source("components/sidebar/ChatSidebar.tsx");
    const profileMenu = source("components/sidebar/ProfileMenu.tsx");
    const quickPeekPath = join(
      root,
      "components/sidebar/RecentsQuickPeek.tsx",
    );

    expect(sidebar).toContain("useQuickJump");
    expect(sidebar).toContain("QuickJumpBadge");
    expect(profileMenu).toContain("useQuickJump");
    expect(profileMenu).toContain("QuickJumpBadge");
    expect(existsSync(quickPeekPath)).toBe(true);
  });
});
