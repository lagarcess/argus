"use client";

import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type RefObject,
} from "react";
import { X } from "lucide-react";
import { useOverlayBackDismiss } from "@/components/layout/useOverlayBackDismiss";

/** Detents from the mobile shell spec: run dossier, sources pane, capital editor. */
export type BottomSheetHeight = "full" | "tall" | "short";

const HEIGHT_CLASS: Record<BottomSheetHeight, string> = {
  full: "h-[96dvh]",
  tall: "h-[70dvh]",
  short: "h-[40dvh]",
};

const FOCUSABLE_SELECTOR = [
  "a[href]",
  "button:not([disabled])",
  "input:not([disabled]):not([type='hidden'])",
  "select:not([disabled])",
  "textarea:not([disabled])",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

const INTERACTIVE_SELECTOR = "a[href],button,input,select,textarea,[role='button']";

/** A downward drag past a quarter of the sheet, or any flick, dismisses. */
const DISMISS_TRAVEL_FLOOR_PX = 64;
const DISMISS_TRAVEL_RATIO = 0.25;
const DISMISS_FLICK_VELOCITY = 0.6;
const DRAG_CAPTURE_THRESHOLD_PX = 3;

export function bottomSheetHeightClass(height: BottomSheetHeight): string {
  return HEIGHT_CLASS[height];
}

export function bottomSheetDragOutcome({
  deltaY,
  sheetHeight,
  velocityY,
}: {
  deltaY: number;
  sheetHeight: number;
  velocityY: number;
}): "dismiss" | "settle" {
  if (deltaY <= 0) return "settle";
  if (velocityY >= DISMISS_FLICK_VELOCITY) return "dismiss";
  const travelThreshold = Math.max(
    DISMISS_TRAVEL_FLOOR_PX,
    sheetHeight * DISMISS_TRAVEL_RATIO,
  );
  return deltaY >= travelThreshold ? "dismiss" : "settle";
}

export function bottomSheetKeyboardAction({
  key,
  shiftKey,
}: {
  key: string;
  shiftKey: boolean;
}): "close" | "focus-next" | "focus-previous" | "none" {
  if (key === "Escape") return "close";
  if (key === "Tab") return shiftKey ? "focus-previous" : "focus-next";
  return "none";
}

/** Wraps at both ends so focus never escapes an open sheet. */
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

type BottomSheetProps = {
  isOpen: boolean;
  onClose: () => void;
  /** Accessible name for the sheet, rendered as its heading unless hidden. */
  title: string;
  /** Accessible name for the close control. */
  closeLabel: string;
  height?: BottomSheetHeight;
  titleHidden?: boolean;
  description?: string;
  /** Pinned below the scrolling body, for a sticky primary action. */
  footer?: ReactNode;
  initialFocusRef?: RefObject<HTMLElement | null>;
  children: ReactNode;
};

/** Bottom sheet primitive: swipe, scrim tap, or the close control dismisses. */
export function BottomSheet({
  isOpen,
  onClose,
  title,
  closeLabel,
  height = "tall",
  titleHidden = false,
  description,
  footer,
  initialFocusRef,
  children,
}: BottomSheetProps) {
  const headingId = useId();
  const descriptionId = useId();
  const overlayId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const dragOriginRef = useRef<{ y: number; at: number } | null>(null);
  const [dragOffset, setDragOffset] = useState(0);

  useOverlayBackDismiss({ isOpen, overlayId, onDismiss: onClose });

  const focusableElements = useCallback((): HTMLElement[] => {
    const panel = panelRef.current;
    if (!panel) return [];
    return Array.from(
      panel.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR),
    ).filter((element) => element.offsetParent !== null || element === panel);
  }, []);

  useEffect(() => {
    if (!isOpen) return;
    restoreFocusRef.current =
      document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const target = initialFocusRef?.current ?? closeButtonRef.current;
    target?.focus();
    return () => {
      restoreFocusRef.current?.focus();
      restoreFocusRef.current = null;
    };
  }, [initialFocusRef, isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    setDragOffset(0);
    dragOriginRef.current = null;
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) return;
    const onKeyDown = (event: KeyboardEvent) => {
      const action = bottomSheetKeyboardAction({
        key: event.key,
        shiftKey: event.shiftKey,
      });
      if (action === "none") return;
      if (action === "close") {
        event.preventDefault();
        event.stopPropagation();
        onClose();
        return;
      }
      const elements = focusableElements();
      if (elements.length === 0) return;
      event.preventDefault();
      const currentIndex = elements.indexOf(
        document.activeElement as HTMLElement,
      );
      const index = nextFocusIndex({
        count: elements.length,
        currentIndex,
        direction: action,
      });
      elements[index]?.focus();
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [focusableElements, isOpen, onClose]);

  const handleDragStart = (event: ReactPointerEvent<HTMLDivElement>) => {
    // Controls in the header keep their own clicks; capturing here would eat them.
    if (
      event.target instanceof Element &&
      event.target.closest(INTERACTIVE_SELECTOR)
    ) {
      return;
    }
    dragOriginRef.current = { y: event.clientY, at: event.timeStamp };
  };

  const handleDragMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const origin = dragOriginRef.current;
    if (!origin) return;
    const deltaY = event.clientY - origin.y;
    // Capture only once this reads as a drag, so a tap stays a tap.
    if (
      Math.abs(deltaY) > DRAG_CAPTURE_THRESHOLD_PX &&
      !event.currentTarget.hasPointerCapture(event.pointerId)
    ) {
      event.currentTarget.setPointerCapture(event.pointerId);
    }
    setDragOffset(Math.max(0, deltaY));
  };

  const handleDragEnd = (event: ReactPointerEvent<HTMLDivElement>) => {
    const origin = dragOriginRef.current;
    dragOriginRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    if (!origin) return;
    const deltaY = event.clientY - origin.y;
    const elapsed = Math.max(1, event.timeStamp - origin.at);
    const outcome = bottomSheetDragOutcome({
      deltaY,
      sheetHeight: panelRef.current?.offsetHeight ?? 0,
      velocityY: deltaY / elapsed,
    });
    setDragOffset(0);
    if (outcome === "dismiss") onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[120] flex items-end justify-center">
      <div
        aria-hidden="true"
        onClick={onClose}
        className="argus-sheet-scrim absolute inset-0 bg-black/25 backdrop-blur-sm dark:bg-black/60"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={headingId}
        aria-describedby={description ? descriptionId : undefined}
        style={
          dragOffset > 0 ? { transform: `translate3d(0, ${dragOffset}px, 0)` } : undefined
        }
        className={`argus-sheet relative flex w-full max-w-[720px] flex-col overflow-hidden rounded-t-[28px] border-t border-black/5 bg-white dark:border-white/5 dark:bg-[#1f2225] ${bottomSheetHeightClass(height)} ${dragOffset > 0 ? "" : "argus-sheet-enter"}`}
      >
        <div
          onPointerDown={handleDragStart}
          onPointerMove={handleDragMove}
          onPointerUp={handleDragEnd}
          onPointerCancel={handleDragEnd}
          className="argus-sheet-grip shrink-0 cursor-grab px-4 pb-2 pt-2 active:cursor-grabbing"
        >
          <div className="mx-auto my-1 h-1.5 w-12 rounded-full bg-black/10 dark:bg-white/10" />
          <div className="mt-1 flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1 pt-2">
              <h2
                id={headingId}
                className={
                  titleHidden
                    ? "sr-only"
                    : "font-display truncate text-[17px] font-semibold tracking-tight text-black dark:text-white"
                }
              >
                {title}
              </h2>
              {description && (
                <p
                  id={descriptionId}
                  className="mt-1 text-[13px] leading-relaxed text-black/55 dark:text-white/55"
                >
                  {description}
                </p>
              )}
            </div>
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onClose}
              aria-label={closeLabel}
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-black/60 transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-[0.125rem] focus-visible:ring-black/25 dark:text-white/60 dark:hover:bg-white/5 dark:focus-visible:ring-white/30"
            >
              <X className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </div>
        <div
          className={`argus-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-contain px-4 ${footer ? "pb-4" : "pb-[max(1rem,env(safe-area-inset-bottom))]"}`}
        >
          {children}
        </div>
        {footer && (
          <div className="argus-sheet-footer shrink-0 border-t border-black/5 px-4 pt-3 pb-[max(1rem,env(safe-area-inset-bottom))] dark:border-white/5">
            {footer}
          </div>
        )}
      </div>
    </div>
  );
}

export default BottomSheet;
