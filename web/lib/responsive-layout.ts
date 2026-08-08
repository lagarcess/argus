/**
 * Width-based layout thresholds for the mobile shell (spec section 1).
 *
 * Two thresholds, never device sniffing: below 1024px the run dossier becomes
 * an overlay sheet, below 720px the full mobile treatment applies. Values match
 * the Tailwind stops in globals.css so CSS and behavior cannot drift.
 */

export const TABLET_MIN_WIDTH_PX = 720;
export const DESKTOP_MIN_WIDTH_PX = 1024;

export const BELOW_TABLET_QUERY = `(max-width: ${TABLET_MIN_WIDTH_PX - 0.02}px)`;
export const BELOW_DESKTOP_QUERY = `(max-width: ${DESKTOP_MIN_WIDTH_PX - 0.02}px)`;

export type ResponsiveLayout = {
  /** Below 720px: drawer, sheets, collapsed Omnisearch, no activity rail. */
  isBelowTablet: boolean;
  /** Below 1024px: the run dossier is an overlay rather than a third pane. */
  isBelowDesktop: boolean;
};

/** Server and first client paint agree on desktop, so hydration never mismatches. */
export const DESKTOP_LAYOUT: ResponsiveLayout = {
  isBelowTablet: false,
  isBelowDesktop: false,
};

export function layoutForWidth(width: number): ResponsiveLayout {
  return {
    isBelowTablet: width < TABLET_MIN_WIDTH_PX,
    isBelowDesktop: width < DESKTOP_MIN_WIDTH_PX,
  };
}

export function layoutsEqual(a: ResponsiveLayout, b: ResponsiveLayout): boolean {
  return (
    a.isBelowTablet === b.isBelowTablet && a.isBelowDesktop === b.isBelowDesktop
  );
}

export type ViewportBand = "narrow" | "wide";

/**
 * Width band sent with a turn so the backend can compose a shorter title
 * instead of the client clipping a long one.
 */
export function currentViewportBand(): ViewportBand {
  if (typeof window === "undefined") return "wide";
  return window.innerWidth < TABLET_MIN_WIDTH_PX ? "narrow" : "wide";
}
