/**
 * What Omnisearch shows at a given width.
 *
 * Width, never pointer type. A pointer check was how the palette used to
 * decide this, which gave a touch laptop the phone layout and a stylus tablet
 * the desktop one; the spec settles it on the DESIGN.md stops instead.
 */
export type LayoutMode = "expanded" | "collapsed";
export type RowActionVariant = "menu" | "hover";

/** Below the mobile threshold there is no room for a second pane. */
export function effectivePaletteLayout(
  layoutMode: LayoutMode,
  isBelowTablet: boolean,
): LayoutMode {
  return isBelowTablet ? "collapsed" : layoutMode;
}

/**
 * Hover reveal is an affordance, not a gate. Every width below the desktop stop
 * gets the explicit menu, and the hover variant stays visible under
 * `@media (any-pointer: coarse)` so a touch screen at desktop width is covered.
 */
export function paletteRowActionVariant(
  isBelowDesktop: boolean,
): RowActionVariant {
  return isBelowDesktop ? "menu" : "hover";
}
