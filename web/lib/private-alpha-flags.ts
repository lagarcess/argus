export const omnisearchEnabled =
  process.env.NEXT_PUBLIC_OMNISEARCH_ENABLED !== "false";

// Research rail presentation: entry copy, range-spanning chips, the signed-in
// empty-chat greeting, and confirmation peer offers. Default off; flag-off
// behavior stays byte-identical to the pre-rail surface.
export const researchRailEnabled =
  process.env.NEXT_PUBLIC_RESEARCH_RAIL_ENABLED === "true";

export function guestAccessEnabledFromEnv(value: string | undefined): boolean {
  if (value === undefined || value.trim() === "") return true;
  const normalized = value.trim().toLowerCase();
  if (["1", "true", "yes", "on"].includes(normalized)) return true;
  return false;
}

export const guestAccessEnabled = guestAccessEnabledFromEnv(
  process.env.NEXT_PUBLIC_GUEST_ACCESS_ENABLED,
);
