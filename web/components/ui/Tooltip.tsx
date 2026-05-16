"use client";

import React, { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";

type TooltipProps = {
  content: string;
  children: React.ReactElement;
  side?: "top" | "bottom" | "left" | "right";
  align?: "start" | "center" | "end";
  delay?: number;
};

/**
 * Premium SOTA Tooltip component.
 * Minimalist design with smooth fade-in and backdrop blur.
 */
export function Tooltip({
  content,
  children,
  side = "right",
  align = "center",
  delay = 300,
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const triggerRef = useRef<HTMLElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const showTooltip = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        let top = 0;
        let left = 0;

        if (side === "right") {
          top = rect.top + rect.height / 2;
          left = rect.right + 8;
        } else if (side === "left") {
          top = rect.top + rect.height / 2;
          left = rect.left - 8;
        } else if (side === "top") {
          top = rect.top - 8;
          left = rect.left + rect.width / 2;
        } else {
          top = rect.bottom + 8;
          left = rect.left + rect.width / 2;
        }

        setCoords({ top, left });
        setIsVisible(true);
      }
    }, delay);
  };

  const hideTooltip = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setIsVisible(false);
  };

  useEffect(() => {
    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, []);

  // Use cloneElement to attach refs and events to children
  const trigger = React.cloneElement(children, {
    ref: triggerRef,
    onMouseEnter: (e: React.MouseEvent) => {
      children.props.onMouseEnter?.(e);
      showTooltip();
    },
    onMouseLeave: (e: React.MouseEvent) => {
      children.props.onMouseLeave?.(e);
      hideTooltip();
    },
    onFocus: (e: React.FocusEvent) => {
      children.props.onFocus?.(e);
      showTooltip();
    },
    onBlur: (e: React.FocusEvent) => {
      children.props.onBlur?.(e);
      hideTooltip();
    },
  });

  const alignmentClass = 
    side === "right" || side === "left" 
      ? "-translate-y-1/2" 
      : "-translate-x-1/2";

  const sideClass = 
    side === "left" ? "origin-right" : 
    side === "right" ? "origin-left" : 
    side === "top" ? "origin-bottom" : "origin-top";

  return (
    <>
      {trigger}
      {isVisible && typeof document !== "undefined" && createPortal(
        <div
          ref={tooltipRef}
          style={{
            position: "fixed",
            top: coords.top,
            left: coords.left,
            zIndex: 9999,
          }}
          className={`pointer-events-none ${alignmentClass} ${sideClass} animate-in fade-in zoom-in-95 duration-150`}
        >
          <div className="rounded-[10px] border border-black/10 bg-white/95 px-3 py-1.5 text-[13px] font-medium text-black shadow-[0_4px_12px_rgba(0,0,0,0.08)] backdrop-blur-md dark:border-white/10 dark:bg-[#1f2225]/95 dark:text-white">
            {content}
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
