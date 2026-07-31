const AVATAR_THEME_TOKENS = [
  "ember",
  "gold",
  "slate",
  "teal",
  "ocean",
  "indigo",
  "plum",
] as const;

export type AvatarTheme = (typeof AVATAR_THEME_TOKENS)[number];

const HUE_STEP = 360 / AVATAR_THEME_TOKENS.length;
const SATURATION = 42;
const TINT_LIGHTNESS = 39;
const BASE_LIGHTNESS = 29;

type AvatarThemeDefinition = {
  token: AvatarTheme;
  hue: number;
  className: "text-white";
};

export const AVATAR_THEMES: AvatarThemeDefinition[] = AVATAR_THEME_TOKENS.map(
  (token, index) => ({
    token,
    hue: index * HUE_STEP,
    className: "text-white",
  }),
);

const AVATAR_THEME_BY_TOKEN = new Map(
  AVATAR_THEMES.map((theme) => [theme.token, theme]),
);

function avatarTheme(theme: AvatarTheme | undefined): AvatarThemeDefinition {
  return AVATAR_THEME_BY_TOKEN.get(theme ?? "ocean") ??
    AVATAR_THEME_BY_TOKEN.get("ocean")!;
}

export function avatarThemeClassName(theme: AvatarTheme | undefined): string {
  return avatarTheme(theme).className;
}

export function avatarThemeStyle(theme: AvatarTheme | undefined) {
  const { hue } = avatarTheme(theme);

  return {
    backgroundImage:
      `linear-gradient(145deg, hsl(${hue} ${SATURATION}% ${TINT_LIGHTNESS}%), hsl(${hue} ${SATURATION}% ${BASE_LIGHTNESS}%))`,
  };
}
