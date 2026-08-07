"use client";

import { useEffect, useRef } from "react";

/**
 * System back closes the overlay instead of leaving Argus.
 *
 * `display: standalone` removes the browser back button, so an installed user
 * has no chrome-level way out of a drawer or sheet. Android still sends its
 * hardware back through `popstate`; opening an overlay pushes one same-URL
 * history entry so that press lands here rather than exiting the app. iOS
 * standalone has no back at all, which is why every overlay also carries a
 * visible close control.
 */

export const OVERLAY_HISTORY_KEY = "argusOverlay";

/**
 * Overlays that pushed a history entry and have not yet spent it.
 *
 * This is the single source of truth for who owns an entry, for two reasons.
 * It cannot live in `history.state`, because Next's App Router calls
 * `replaceState` with its own routing tree and drops foreign keys. And a
 * separate "programmatic pop" counter could go stale whenever a `popstate` it
 * expected never arrived, after which the next real back press was swallowed.
 *
 * One rule instead: whoever claims the id first wins. A `popstate` that finds
 * the id already claimed is the echo of our own `history.back()`, so it is
 * ignored; one that still finds it is a user pressing back.
 */
let unconsumedOverlays: string[] = [];

/** Test seam: reset document-level state between cases. */
export function resetOverlayEntries(): void {
  unconsumedOverlays = [];
}

export function claimOverlayEntry(overlayId: string): boolean {
  if (!unconsumedOverlays.includes(overlayId)) return false;
  unconsumedOverlays = unconsumedOverlays.filter((id) => id !== overlayId);
  return true;
}

export function recordOverlayEntry(overlayId: string): void {
  unconsumedOverlays = [...unconsumedOverlays, overlayId];
}

export function openOverlayEntries(): readonly string[] {
  return unconsumedOverlays;
}

export function overlayHistoryState(
  currentState: unknown,
  overlayId: string,
): Record<string, unknown> {
  const base =
    currentState && typeof currentState === "object"
      ? (currentState as Record<string, unknown>)
      : {};
  return { ...base, [OVERLAY_HISTORY_KEY]: overlayId };
}

export function useOverlayBackDismiss({
  isOpen,
  overlayId,
  onDismiss,
}: {
  isOpen: boolean;
  overlayId: string;
  onDismiss: () => void;
}): void {
  const dismissRef = useRef(onDismiss);
  const pendingPopRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    dismissRef.current = onDismiss;
  }, [onDismiss]);

  useEffect(() => {
    if (!isOpen || typeof window === "undefined") return;

    // A remount lands here before the previous cleanup's pop has run, so cancel
    // it: React double-invoking an effect is not the user closing anything.
    if (pendingPopRef.current !== null) {
      clearTimeout(pendingPopRef.current);
      pendingPopRef.current = null;
    }

    // Push at most one entry per open overlay. Without this a remount stacks a
    // second entry that nothing will ever pop.
    if (!openOverlayEntries().includes(overlayId)) {
      recordOverlayEntry(overlayId);
      window.history.pushState(
        overlayHistoryState(window.history.state, overlayId),
        "",
        window.location.href,
      );
    }

    const handlePopState = () => {
      // Already claimed means this is the echo of our own back() below.
      if (!claimOverlayEntry(overlayId)) return;
      dismissRef.current();
    };
    window.addEventListener("popstate", handlePopState);

    return () => {
      window.removeEventListener("popstate", handlePopState);
      // Deferred so a remount can cancel it. A real close has nothing to cancel
      // it, so the entry is spent on the next tick and the stack stays flat.
      pendingPopRef.current = setTimeout(() => {
        pendingPopRef.current = null;
        if (claimOverlayEntry(overlayId)) window.history.back();
      }, 0);
    };
  }, [isOpen, overlayId]);
}
