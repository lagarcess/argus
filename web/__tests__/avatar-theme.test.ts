import { describe, expect, test } from "vitest";
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

  test("labels every selectable avatar theme in English and Latin American Spanish", async () => {
    const [en, es] = await Promise.all([
      import("@/public/locales/en/common.json"),
      import("@/public/locales/es-419/common.json"),
    ]);
    const expectedThemes = new Set(AVATAR_THEMES.map((theme) => theme.token));

    for (const locale of [en.default, es.default]) {
      const avatarTheme = locale.settings.profile.avatar_theme;
      expect(new Set(Object.keys(avatarTheme.themes))).toEqual(expectedThemes);
      expect(avatarTheme.label.trim()).not.toBe("");
      expect(avatarTheme.change.trim()).not.toBe("");
      expect(avatarTheme.close.trim()).not.toBe("");
      expect(avatarTheme.hide.trim()).not.toBe("");
      for (const theme of AVATAR_THEMES) {
        expect(avatarTheme.themes[theme.token].trim()).not.toBe("");
      }
    }

    expect(en.default.settings.profile.avatar_theme.label).toBe("Avatar color");
    expect(es.default.settings.profile.avatar_theme.label).toBe(
      "Color del avatar",
    );
  });
});
