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
const AVATAR_THEME_SURFACES = {
  picker: { saturation: 42, tintLightness: 39, baseLightness: 29 },
  ambient: { saturation: 24, tintLightness: 35, baseLightness: 30 },
} as const;

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

export function avatarThemeStyle(
  theme: AvatarTheme | undefined,
  surface: keyof typeof AVATAR_THEME_SURFACES = "ambient",
) {
  const { hue } = avatarTheme(theme);
  const { saturation, tintLightness, baseLightness } =
    AVATAR_THEME_SURFACES[surface];

  return {
    backgroundImage:
      `linear-gradient(145deg, hsl(${hue} ${saturation}% ${tintLightness}%), hsl(${hue} ${saturation}% ${baseLightness}%))`,
  };
}
