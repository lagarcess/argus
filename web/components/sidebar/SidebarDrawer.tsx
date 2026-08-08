"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { useModalSurface } from "@/components/layout/useModalSurface";

/** A leftward drag past a third of the panel, or any flick, dismisses. */
const DISMISS_TRAVEL_RATIO = 0.33;
const DISMISS_FLICK_VELOCITY = 0.5;
const DRAG_CAPTURE_THRESHOLD_PX = 6;

/**
 * Whether the gesture ended because the user let go, or because the browser
 * took it away. `pointercancel` is the second, and it decides nothing: the
 * panel allows vertical panning, so scrolling Recents hands the pointer to the
 * scroller mid-drag, and the sideways drift of a thumb scroll was enough
 * travel to read as a dismissal.
 */
export type SidebarDrawerGesturePhase = "release" | "cancel";

export function sidebarDrawerDragOutcome({
  deltaX,
  panelWidth,
  velocityX,
  phase = "release",
}: {
  deltaX: number;
  panelWidth: number;
  velocityX: number;
  phase?: SidebarDrawerGesturePhase;
}): "dismiss" | "settle" {
  if (phase === "cancel") return "settle";
  if (deltaX >= 0) return "settle";
  const travel = Math.abs(deltaX);
  if (Math.abs(velocityX) >= DISMISS_FLICK_VELOCITY) return "dismiss";
  return travel >= panelWidth * DISMISS_TRAVEL_RATIO ? "dismiss" : "settle";
}

type SidebarDrawerProps = {
  isOpen: boolean;
  onClose: () => void;
  /** Accessible name for the drawer region. */
  label: string;
  children: ReactNode;
};

/**
 * Off-canvas sidebar below the mobile threshold (spec section 2). The panel
 * covers 82 percent so the remaining strip of chat stays visible and tappable,
 * and dismisses by scrim tap, leftward swipe, Escape, or system back. The close
 * control lives in the sidebar header, which owns the drawer chrome.
 */
export default function SidebarDrawer({
  isOpen,
  onClose,
  label,
  children,
}: SidebarDrawerProps) {
  const overlayId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const dragOriginRef = useRef<{ x: number; at: number } | null>(null);
  const [dragOffset, setDragOffset] = useState(0);

  // Declaring aria-modal is a promise the rest of the page is inert; without
  // this the opener kept focus behind the scrim and Tab walked the chat.
  useModalSurface({
    isOpen,
    overlayId,
    containerRef: panelRef,
    onDismiss: onClose,
    onEscape: onClose,
  });

  useEffect(() => {
    if (!isOpen) return;
    setDragOffset(0);
    dragOriginRef.current = null;
  }, [isOpen]);


  const handleDragStart = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.target instanceof Element && event.target.closest("a,button,input,select,textarea")) {
      return;
    }
    dragOriginRef.current = { x: event.clientX, at: event.timeStamp };
  };

  const handleDragMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const origin = dragOriginRef.current;
    if (!origin) return;
    const deltaX = event.clientX - origin.x;
    if (
      Math.abs(deltaX) > DRAG_CAPTURE_THRESHOLD_PX &&
      !event.currentTarget.hasPointerCapture(event.pointerId)
    ) {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    setDragOffset(Math.min(0, deltaX));
  };

  const endGesture = (
    event: ReactPointerEvent<HTMLDivElement>,
    phase: SidebarDrawerGesturePhase,
  ) => {
    const origin = dragOriginRef.current;
    dragOriginRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setDragOffset(0);
    if (!origin) return;
    const deltaX = event.clientX - origin.x;
    const elapsed = Math.max(1, event.timeStamp - origin.at);
    const outcome = sidebarDrawerDragOutcome({
      deltaX,
      panelWidth: panelRef.current?.offsetWidth ?? 0,
      velocityX: deltaX / elapsed,
      phase,
    });
    if (outcome === "dismiss") onClose();
  };

  const handleDragEnd = (event: ReactPointerEvent<HTMLDivElement>) =>
    endGesture(event, "release");

  const handleDragCancel = (event: ReactPointerEvent<HTMLDivElement>) =>
    endGesture(event, "cancel");

  if (!isOpen) return null;

  return (
    /*
     * The drawer sits above page chrome and below every dialog, because
     * everything it hosts opens on top of it. At z-100 it outranked the six
     * settings modals and the profile dialogs, which all live at 70 to 80, so
     * Settings opened behind the panel that launched it. Keep this under 70.
     */
    <div className="fixed inset-0 z-[68] flex" data-testid="sidebar-drawer">
      <div
        aria-hidden="true"
        onClick={onClose}
        className="argus-drawer-scrim absolute inset-0 bg-black/35 backdrop-blur-sm dark:bg-black/60"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={label}
        onPointerDown={handleDragStart}
        onPointerMove={handleDragMove}
        onPointerUp={handleDragEnd}
        onPointerCancel={handleDragCancel}
        style={
          dragOffset < 0
            ? { transform: `translate3d(${dragOffset}px, 0, 0)` }
            : undefined
        }
        className={`argus-drawer-panel relative flex h-full w-[82%] max-w-[380px] flex-col ${
          dragOffset < 0 ? "" : "argus-drawer-enter"
        }`}
      >
        {children}
      </div>
    </div>
  );
}
