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
 * Programmatic `history.back()` calls whose `popstate` has not arrived yet.
 * The event is asynchronous and fires on whatever listener is mounted when it
 * lands, so ownership has to be tracked for the document rather than per hook
 * instance. Without this, an overlay that remounts pops its own entry and then
 * reads the resulting event as a user pressing back.
 */
let pendingProgrammaticPops = 0;

export function claimProgrammaticPop(): boolean {
  if (pendingProgrammaticPops <= 0) return false;
  pendingProgrammaticPops -= 1;
  return true;
}

export function recordProgrammaticPop(): void {
  pendingProgrammaticPops += 1;
}

/** Test seam: reset the document-level counter between cases. */
export function resetProgrammaticPops(): void {
  pendingProgrammaticPops = 0;
}

/** Only pop an entry we still own; a route change elsewhere clears the marker. */
export function ownsPushedHistoryEntry(
  state: unknown,
  overlayId: string,
): boolean {
  if (!state || typeof state !== "object") return false;
  return (state as Record<string, unknown>)[OVERLAY_HISTORY_KEY] === overlayId;
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

  useEffect(() => {
    dismissRef.current = onDismiss;
  }, [onDismiss]);

  useEffect(() => {
    if (!isOpen || typeof window === "undefined") return;

    window.history.pushState(
      overlayHistoryState(window.history.state, overlayId),
      "",
      window.location.href,
    );

    const handlePopState = () => {
      if (claimProgrammaticPop()) return;
      dismissRef.current();
    };
    window.addEventListener("popstate", handlePopState);

    return () => {
      window.removeEventListener("popstate", handlePopState);
      if (ownsPushedHistoryEntry(window.history.state, overlayId)) {
        recordProgrammaticPop();
        window.history.back();
      }
    };
  }, [isOpen, overlayId]);
}
