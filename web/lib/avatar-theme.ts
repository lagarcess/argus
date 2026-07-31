export const AVATAR_THEMES = [
  { token: "ocean", className: "bg-[#1E5A86] text-white" },
  { token: "plum", className: "bg-[#633B7A] text-white" },
  { token: "teal", className: "bg-[#176B61] text-white" },
  { token: "ember", className: "bg-[#9A4B2D] text-white" },
  { token: "gold", className: "bg-[#C79B2B] text-[#191c1f]" },
  { token: "indigo", className: "bg-[#474C99] text-white" },
  { token: "slate", className: "bg-[#536170] text-white" },
] as const;

export type AvatarTheme = (typeof AVATAR_THEMES)[number]["token"];

const AVATAR_THEME_CLASS_BY_TOKEN = new Map(
  AVATAR_THEMES.map((theme) => [theme.token, theme.className]),
);

export function avatarThemeClassName(theme: AvatarTheme | undefined): string {
  return AVATAR_THEME_CLASS_BY_TOKEN.get(theme ?? "ocean") ??
    AVATAR_THEME_CLASS_BY_TOKEN.get("ocean")!;
}
