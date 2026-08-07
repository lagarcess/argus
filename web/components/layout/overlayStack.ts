"use client";

import { useEffect } from "react";

/**
 * Which overlay currently owns Escape.
 *
 * Overlays listen on `document` in the capture phase, and listeners on the same
 * target fire in registration order, so an ancestor that mounted first always
 * runs before its own child. `stopPropagation` cannot help: it stops the
 * journey between targets, not siblings on one. So a child cannot defend
 * itself, and the parent has to stand down instead.
 *
 * Guarding on one named child does not scale, which the palette proved twice:
 * a dossier-only guard still let Escape close the whole of Omnisearch while its
 * row menu was open. Depth is the general rule, so this tracks it.
 */

let stack: string[] = [];

export function pushOverlay(overlayId: string): void {
  stack = [...stack.filter((id) => id !== overlayId), overlayId];
}

export function popOverlay(overlayId: string): void {
  stack = stack.filter((id) => id !== overlayId);
}

/** True when something opened on top of this overlay and should answer first. */
export function hasOverlayAbove(overlayId: string): boolean {
  const index = stack.indexOf(overlayId);
  return index >= 0 && index < stack.length - 1;
}

export function isTopOverlay(overlayId: string): boolean {
  return stack.length > 0 && stack[stack.length - 1] === overlayId;
}

export function overlayStackIds(): readonly string[] {
  return stack;
}

/** Test seam: reset between cases. */
export function resetOverlayStack(): void {
  stack = [];
}

/** Registers an overlay for as long as it is open. */
export function useOverlayStackEntry(isOpen: boolean, overlayId: string): void {
  useEffect(() => {
    if (!isOpen) return;
    pushOverlay(overlayId);
    return () => popOverlay(overlayId);
  }, [isOpen, overlayId]);
}
