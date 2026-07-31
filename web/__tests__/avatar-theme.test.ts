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

  test("derives stronger picker and quieter ambient gradients from one hue system", () => {
    const hueStep = 360 / AVATAR_THEMES.length;

    for (const [index, theme] of AVATAR_THEMES.entries()) {
      expect(theme.hue).toBeCloseTo(28.5 + index * hueStep);
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

  test("renders an avatar-triggered picker submodal without changing initials derivation", () => {
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
    expect(menu).toContain("openAvatarPicker");
    expect(menu).toContain("isAvatarPickerOpen &&");
    expect(menu).toContain("avatarPickerDialogRef");
    expect(menu).toContain("avatarPickerShouldRestoreFocusRef");
    expect(menu).toContain("inert={isAvatarPickerOpen}");
    expect(menu).toContain('document.addEventListener("keydown", handleKeyDown)');
    expect(menu).toContain("avatarTriggerRef.current?.focus()");
    expect(menu).toContain("h-11 w-11 items-center justify-center");
    expect(menu).toContain("grid-cols-8 gap-3");
    expect(menu).toContain('index === 4 ? "col-start-2" : ""');
    expect(menu).toContain('"scale-[0.98] opacity-45 blur-[1px]"');
    expect(menu).not.toContain("<fieldset");
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
    expect(en.settings.profile.avatar_theme.themes.ember).toBe("Sienna");
    expect(en.settings.profile.avatar_theme.themes.ocean).toBe("Cobalt");
    expect(es.settings.profile.avatar_theme.themes.ember).toBe("Siena");
    expect(es.settings.profile.avatar_theme.themes.ocean).toBe("Cobalto");
  });
});
