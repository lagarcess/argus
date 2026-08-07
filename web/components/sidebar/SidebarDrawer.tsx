"use client";

import {
  useEffect,
  useId,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";
import { useOverlayBackDismiss } from "@/components/layout/useOverlayBackDismiss";

/** A leftward drag past a third of the panel, or any flick, dismisses. */
const DISMISS_TRAVEL_RATIO = 0.33;
const DISMISS_FLICK_VELOCITY = 0.5;
const DRAG_CAPTURE_THRESHOLD_PX = 6;

export function sidebarDrawerDragOutcome({
  deltaX,
  panelWidth,
  velocityX,
}: {
  deltaX: number;
  panelWidth: number;
  velocityX: number;
}): "dismiss" | "settle" {
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

  useOverlayBackDismiss({ isOpen, overlayId, onDismiss: onClose });

  useEffect(() => {
    if (!isOpen) return;
    setDragOffset(0);
    dragOriginRef.current = null;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      event.preventDefault();
      event.stopPropagation();
      onClose();
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [isOpen, onClose]);

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

  const handleDragEnd = (event: ReactPointerEvent<HTMLDivElement>) => {
    const origin = dragOriginRef.current;
    dragOriginRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (!origin) return;
    const deltaX = event.clientX - origin.x;
    const elapsed = Math.max(1, event.timeStamp - origin.at);
    const outcome = sidebarDrawerDragOutcome({
      deltaX,
      panelWidth: panelRef.current?.offsetWidth ?? 0,
      velocityX: deltaX / elapsed,
    });
    setDragOffset(0);
    if (outcome === "dismiss") onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex" data-testid="sidebar-drawer">
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
        onPointerCancel={handleDragEnd}
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
