const AVATAR_THEME_TOKENS = [
  "ocean",
  "ember",
  "gold",
  "slate",
  "teal",
  "indigo",
  "plum",
] as const;

export type AvatarTheme = (typeof AVATAR_THEME_TOKENS)[number];

const HUE_PHASE = 28.5;
const HUE_STEP = 360 / AVATAR_THEME_TOKENS.length;
const HUE_INDEX_BY_TOKEN: Record<AvatarTheme, number> = {
  ember: 0,
  gold: 1,
  slate: 2,
  teal: 3,
  ocean: 4,
  indigo: 5,
  plum: 6,
};
const AVATAR_THEME_SURFACES = {
  picker: { saturation: 36, tintLightness: 35, baseLightness: 27 },
  ambient: { saturation: 22, tintLightness: 32, baseLightness: 29 },
} as const;

type AvatarThemeDefinition = {
  token: AvatarTheme;
  hue: number;
  className: string;
};

export const AVATAR_THEMES: AvatarThemeDefinition[] = AVATAR_THEME_TOKENS.map(
  (token) => ({
    token,
    hue: HUE_PHASE + HUE_INDEX_BY_TOKEN[token] * HUE_STEP,
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
  if (avatarTheme(theme).token === "ocean") {
    return "bg-[#191c1f] text-white dark:bg-white/10";
  }

  return avatarTheme(theme).className;
}

export function avatarThemeStyle(
  theme: AvatarTheme | undefined,
  surface: keyof typeof AVATAR_THEME_SURFACES = "ambient",
) {
  const resolvedTheme = avatarTheme(theme);
  if (resolvedTheme.token === "ocean") return undefined;

  const { hue } = resolvedTheme;
  const { saturation, tintLightness, baseLightness } =
    AVATAR_THEME_SURFACES[surface];

  return {
    backgroundImage:
      `linear-gradient(145deg, hsl(${hue} ${saturation}% ${tintLightness}%), hsl(${hue} ${saturation}% ${baseLightness}%))`,
  };
}
