/**
 * Whether to badge sidebar rows with the chord that triggers them.
 *
 * The drawer is the sidebar below the mobile threshold, and that width does
 * not register the shortcut layer at all, so a badge there would name a chord
 * that does nothing. It is the same reason the profile menu withholds the
 * shortcut sheet on a phone, applied to the other place a key is advertised.
 */
export function sidebarShortcutHintsVisible({
  modifierHeld,
  suppressed,
  variant,
}: {
  modifierHeld: boolean;
  suppressed: boolean;
  variant: "rail" | "drawer";
}): boolean {
  if (variant === "drawer") return false;
  return modifierHeld && !suppressed;
}

export function nextSidebarRecentsState(
  sidebarOpen: boolean,
  recentsExpanded: boolean,
) {
  if (sidebarOpen && recentsExpanded) {
    return { sidebarOpen: false, recentsExpanded: false };
  }

  return { sidebarOpen: true, recentsExpanded: true };
}
