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
  test("keeps Argus's original neutral avatar as the deterministic default", () => {
    expect(AVATAR_THEMES).toHaveLength(7);
    expect(AVATAR_THEMES.map((theme) => theme.token)).toEqual([
      "ocean",
      "ember",
      "gold",
      "slate",
      "teal",
      "indigo",
      "plum",
    ] satisfies AvatarTheme[]);
    expect(avatarThemeClassName(undefined)).toBe(
      "bg-[#191c1f] text-white dark:bg-white/10",
    );
    expect(avatarThemeClassName("ocean")).toBe(
      "bg-[#191c1f] text-white dark:bg-white/10",
    );
    expect(avatarThemeStyle(undefined)).toBeUndefined();
    expect(avatarThemeStyle("ocean", "picker")).toBeUndefined();
  });

  test("derives stronger picker and quieter ambient gradients from one hue system", () => {
    const expectedHues: Record<AvatarTheme, number> = {
      ember: 28.5,
      gold: 28.5 + 360 / 7,
      slate: 28.5 + (360 / 7) * 2,
      teal: 28.5 + (360 / 7) * 3,
      ocean: 28.5 + (360 / 7) * 4,
      indigo: 28.5 + (360 / 7) * 5,
      plum: 28.5 + (360 / 7) * 6,
    };

    for (const theme of AVATAR_THEMES) {
      if (theme.token === "ocean") continue;

      expect(theme.hue).toBeCloseTo(expectedHues[theme.token]);
      expect(theme.className).toBe("text-white");
      expect(avatarThemeStyle(theme.token, "picker")).toEqual({
        backgroundImage:
          `linear-gradient(145deg, hsl(${theme.hue} 36% 35%), hsl(${theme.hue} 36% 27%))`,
      });
      expect(avatarThemeStyle(theme.token, "ambient")).toEqual({
        backgroundImage:
          `linear-gradient(145deg, hsl(${theme.hue} 22% 32%), hsl(${theme.hue} 22% 29%))`,
      });
    }
  });

  test("renders an avatar-triggered inline drawer without changing initials derivation", () => {
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
    expect(menu).toContain('avatarThemeStyle(profile?.avatar_theme, "ambient")');
    expect(menu).toContain('avatarThemeStyle(theme.token, "picker")');
    expect(menu).toContain("toggleAvatarPicker");
    expect(menu).toContain("argus-avatar-theme-drawer");
    expect(menu).toContain("aria-expanded={isAvatarPickerOpen}");
    expect(menu).toContain("inert={!isAvatarPickerOpen}");
    expect(menu).not.toContain("avatarPickerDialogRef");
    expect(menu).not.toContain("argus-avatar-theme-picker-title");
    expect(menu).toContain("h-11 w-11 items-center justify-center");
    expect(menu).toContain("flex h-9 w-9 items-center justify-center");
    expect(menu).toContain("ring-2 ring-black/70 dark:ring-white/80");
    expect(menu).toContain('theme.token === "ocean"');
    expect(menu).toContain('"border-black/20 dark:border-white/20"');
    expect(menu).not.toContain("ring-offset-2");
    expect(menu).not.toContain("border-t border-black/10 pt-1.5");
    expect(menu).toContain("grid-cols-8 place-items-center");
    expect(menu).toContain("sm:grid-cols-7");
    expect(menu).toContain("Avatar color");
    expect(menu).toContain("Hide avatar colors");
    expect(menu).not.toContain("<fieldset");
    expect(menu).toContain("bg-[#191c1f] text-white dark:bg-white/10");
    expect(menu).toContain("profile?.display_name?.trim() ||");
    expect(menu).toContain("profile?.username?.trim() ||");
    expect(menu).toContain("profile?.email?.trim() ||");
    expect(en.settings.profile.avatar_theme.label).toBe("Avatar color");
    expect(es.settings.profile.avatar_theme.label).toBe("Color del avatar");
    expect(en.settings.profile.avatar_theme.change).toBe("Edit avatar");
    expect(es.settings.profile.avatar_theme.change).toBe("Editar avatar");
    expect(en.settings.profile.avatar_theme.close).toBe("Hide avatar colors");
    expect(es.settings.profile.avatar_theme.close).toBe(
      "Ocultar colores del avatar",
    );
    expect(new Set(Object.keys(en.settings.profile.avatar_theme.themes))).toEqual(
      new Set(AVATAR_THEMES.map((theme) => theme.token)),
    );
    expect(new Set(Object.keys(es.settings.profile.avatar_theme.themes))).toEqual(
      new Set(AVATAR_THEMES.map((theme) => theme.token)),
    );
    expect(en.settings.profile.avatar_theme.themes.ember).toBe("Sienna");
    expect(en.settings.profile.avatar_theme.themes.ocean).toBe("Default");
    expect(es.settings.profile.avatar_theme.themes.ember).toBe("Siena");
    expect(es.settings.profile.avatar_theme.themes.ocean).toBe("Predeterminado");
  });
});
