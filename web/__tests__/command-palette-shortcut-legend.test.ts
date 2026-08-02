import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

function source(relativePath: string): string {
  return readFileSync(join(root, relativePath), "utf-8");
}

describe("Omnisearch shortcut legend", () => {
  test("uses the shared keycap and only reveals a footer legend for modifier plus hover", () => {
    const palette = source("components/sidebar/ChatCommandPalette.tsx");

    expect(palette).toContain("KeyboardShortcutKeycap");
    expect(palette).toContain("isKeyboardShortcutHintModifierActive");
    expect(palette).toContain("data-command-palette-shortcut-legend");
    expect(palette).toContain("data-command-palette-action-region");
    expect(palette).toContain("isShortcutLegendHovered && isShortcutHintModifierActive");
    expect(palette).not.toContain('"command_palette.open_at_match"');
    expect(palette).not.toContain('"command_palette.open_at_left_off"');
  });

  test("keeps legend copy localized without adding it to the global shortcut overlay", () => {
    const en = JSON.parse(source("public/locales/en/common.json"));
    const es = JSON.parse(source("public/locales/es-419/common.json"));
    const overlay = source("components/sidebar/KeyboardShortcutsOverlay.tsx");

    expect(en.command_palette.shortcut_legend.go).toBe("Go");
    expect(en.command_palette.shortcut_legend.rename).toBe("Rename");
    expect(en.command_palette.shortcut_legend.archive).toBe("Archive");
    expect(en.command_palette.shortcut_legend.delete).toBe("Delete");
    expect(es.command_palette.shortcut_legend.go).toBe("Abrir");
    expect(es.command_palette.shortcut_legend.rename).toBe("Renombrar");
    expect(es.command_palette.shortcut_legend.archive).toBe("Archivar");
    expect(es.command_palette.shortcut_legend.delete).toBe("Eliminar");
    expect(overlay).not.toContain("command_palette.shortcut_legend");
  });
});
