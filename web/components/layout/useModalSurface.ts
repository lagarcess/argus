"use client";

import type { RefObject } from "react";
import { useOverlayBackDismiss } from "./useOverlayBackDismiss";
import { useOverlayLayer } from "./overlayStack";
import { useModalFocusTrap } from "./useModalFocusTrap";

/**
 * Everything a modal surface owes its user, in one call.
 *
 * These obligations were separate hooks and every surface picked its own
 * subset, which produced exactly the incoherent combinations you would predict:
 * a drawer that trapped nothing, a confirmation that owned Escape but not
 * system back, and parent traps that kept stealing Tab from the dialog above
 * them. Each gap looked small on its own and none was visible in review.
 *
 * They are bundled so a surface cannot take one and skip another, and the
 * input-owning half is routed by the layer registry rather than by listeners
 * the surface installs, so it cannot answer for a press meant for something
 * above it. The ownership test requires this call on anything declaring
 * `aria-modal`, so a partial registration is a failing test rather than a
 * subtle bug.
 */
export function useModalSurface({
  isOpen,
  overlayId,
  containerRef,
  onDismiss,
  canDismiss,
  onEscape,
  onKeyDown,
  onOutsidePointerDown,
  trapFocus = true,
  initialFocusRef,
  returnFocusRef,
}: {
  isOpen: boolean;
  /** Stable per instance; `useId()` at the call site. */
  overlayId: string;
  containerRef: RefObject<HTMLElement | null>;
  /** Runs for system back. */
  onDismiss: () => void;
  /** Checked before the history entry is spent, for surfaces that can refuse. */
  canDismiss?: () => boolean;
  /** Escape, routed only while this layer is topmost. Defaults to `onDismiss`. */
  onEscape?: () => void;
  /** For layers owning more than Escape; replaces `onEscape` when given. */
  onKeyDown?: (event: KeyboardEvent) => void;
  /** A press outside the container, routed only while this layer is topmost. */
  onOutsidePointerDown?: (event: PointerEvent) => void;
  /** Menus and popovers may opt out of containment; modals should not. */
  trapFocus?: boolean;
  initialFocusRef?: RefObject<HTMLElement | null>;
  returnFocusRef?: RefObject<HTMLElement | null>;
}): void {
  useOverlayLayer({
    isOpen,
    overlayId,
    containerRef,
    trapFocus,
    onEscape: onEscape ?? onDismiss,
    onKeyDown,
    onOutsidePointerDown,
  });
  useOverlayBackDismiss({ isOpen, overlayId, onDismiss, canDismiss });
  useModalFocusTrap({
    isOpen,
    containerRef,
    initialFocusRef,
    returnFocusRef,
  });
}
