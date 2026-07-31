import { describe, expect, test } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  AVATAR_THEMES,
  avatarThemeClassName,
  avatarThemeStyle,
  type AvatarTheme,
} from "@/lib/avatar-theme";

describe("avatar monogram themes", () => {
  test("uses a curated token set with a deterministic ocean fallback", () => {
    expect(AVATAR_THEMES).toHaveLength(7);
    expect(AVATAR_THEMES.map((theme) => theme.token)).toEqual([
      "ember",
      "gold",
      "slate",
      "teal",
      "ocean",
      "indigo",
      "plum",
    ] satisfies AvatarTheme[]);
    expect(avatarThemeClassName(undefined)).toBe(avatarThemeClassName("ocean"));
  });

  test("derives evenly spaced rich gradients from the shared hue formula", () => {
    const hueStep = 360 / AVATAR_THEMES.length;

    for (const [index, theme] of AVATAR_THEMES.entries()) {
      expect(theme.hue).toBeCloseTo(index * hueStep);
      expect(theme.className).toBe("text-white");
      expect(avatarThemeStyle(theme.token)).toEqual({
        backgroundImage:
          `linear-gradient(145deg, hsl(${theme.hue} 42% 39%), hsl(${theme.hue} 42% 29%))`,
      });
    }
  });

  test("renders a registered-only picker without changing initials derivation", () => {
    const root = join(import.meta.dir, "..");
    const menu = readFileSync(
      join(root, "components/sidebar/ProfileMenu.tsx"),
      "utf-8",
    );
    const en = JSON.parse(
      readFileSync(join(root, "public/locales/en/common.json"), "utf-8"),
    );
    const es = JSON.parse(
      readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
    );

    expect(menu).toContain("accountKind === \"registered\"");
    expect(menu).toContain("patchMe({ avatar_theme: avatarTheme })");
    expect(menu).toContain("avatarThemeClassName(profile?.avatar_theme)");
    expect(menu).toContain("bg-[#191c1f] text-white dark:bg-white/10");
    expect(menu).toContain("profile?.display_name?.trim() ||");
    expect(menu).toContain("profile?.username?.trim() ||");
    expect(menu).toContain("profile?.email?.trim() ||");
    expect(en.settings.profile.avatar_theme.label).toBe("Monogram color");
    expect(es.settings.profile.avatar_theme.label).toBe("Color del monograma");
    expect(Object.keys(en.settings.profile.avatar_theme.themes)).toEqual(
      AVATAR_THEMES.map((theme) => theme.token),
    );
    expect(Object.keys(es.settings.profile.avatar_theme.themes)).toEqual(
      AVATAR_THEMES.map((theme) => theme.token),
    );
    expect(en.settings.profile.avatar_theme.themes.slate).toBe("Moss");
    expect(es.settings.profile.avatar_theme.themes.slate).toBe("Musgo");
  });
});
