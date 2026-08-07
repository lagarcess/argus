"use client";

import type { RefObject } from "react";
import { useOverlayBackDismiss } from "./useOverlayBackDismiss";
import { useOverlayStackEntry } from "./overlayStack";
import { useModalFocusTrap } from "./useModalFocusTrap";

/**
 * Everything a modal surface owes its user, in one call.
 *
 * These three obligations were separate hooks and every surface picked its own
 * subset, which produced exactly the incoherent combinations you would predict:
 * a drawer that trapped nothing, a confirmation that owned Escape but not
 * system back, and parent traps that kept stealing Tab from the dialog above
 * them. Each gap looked small on its own and none was visible in review.
 *
 * They are bundled so a surface cannot take one and skip another. The
 * ownership test requires this call on anything declaring `aria-modal`, so a
 * partial registration is now a failing test rather than a subtle bug.
 */
export function useModalSurface({
  isOpen,
  overlayId,
  containerRef,
  onDismiss,
  initialFocusRef,
}: {
  isOpen: boolean;
  /** Stable per instance; `useId()` at the call site. */
  overlayId: string;
  containerRef: RefObject<HTMLElement | null>;
  /** Runs for system back. Escape stays with the caller, which may have its own rules. */
  onDismiss: () => void;
  initialFocusRef?: RefObject<HTMLElement | null>;
}): void {
  useOverlayStackEntry(isOpen, overlayId);
  useOverlayBackDismiss({ isOpen, overlayId, onDismiss });
  useModalFocusTrap({ isOpen, overlayId, containerRef, initialFocusRef });
}
