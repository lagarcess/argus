/**
 * Layout constants shared by the public receipt surfaces.
 *
 * Deliberately not exported from the action bar itself. That module is
 * `"use client"`, which turns every one of its exports into a client reference, so a
 * server component importing a plain string from it receives a stub instead. The
 * stub stringifies into the class attribute as a JavaScript error message, the
 * padding silently never applies, and the bar covers the last line of the page it
 * sits on.
 */

/**
 * Bottom clearance for a page that renders the action bar.
 *
 * Underscores are Tailwind's escape for the spaces CSS `calc()` requires around its
 * operators; without them the declaration is invalid and drops. 112px clears the
 * tallest observed bar, which is the Spanish framing wrapping to two lines at 87px.
 * `env()` reports zero unless the viewport opts into the full screen, which the
 * route layout does with `viewportFit: "cover"`.
 */
export const RECEIPT_ACTION_BAR_CLEARANCE =
  "pb-[calc(112px_+_env(safe-area-inset-bottom))]";
