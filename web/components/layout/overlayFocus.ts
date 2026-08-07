/**
 * Which elements a trapped layer may move focus between.
 *
 * Shared so the registry and the focus hook cannot disagree about what counts
 * as focusable, which is the kind of drift that lets Tab fall out of a dialog
 * through an element only one of them could see.
 */

export const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

export function focusableWithin(container: HTMLElement | null): HTMLElement[] {
  if (!container) return [];
  return Array.from(
    container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
  ).filter((element) => element.offsetParent !== null);
}

/** Wraps at both ends so focus never escapes an open modal. */
export function nextFocusIndex({
  count,
  currentIndex,
  direction,
}: {
  count: number;
  currentIndex: number;
  direction: "focus-next" | "focus-previous";
}): number {
  if (count <= 0) return -1;
  if (direction === "focus-next") {
    return currentIndex >= count - 1 || currentIndex < 0 ? 0 : currentIndex + 1;
  }
  return currentIndex <= 0 ? count - 1 : currentIndex - 1;
}
