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
 * gets the explicit menu, whose trigger and items are 44px, so reach never
 * depends on knowing what kind of pointer is in use.
 */
export function paletteRowActionVariant(
  isBelowDesktop: boolean,
): RowActionVariant {
  return isBelowDesktop ? "menu" : "hover";
}
