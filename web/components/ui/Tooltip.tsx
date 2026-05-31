"use client";

import React, { useState, useRef, useEffect } from "react";
import { createPortal } from "react-dom";

type TooltipProps = {
  content: string;
  children: React.ReactElement<
    React.HTMLAttributes<HTMLElement> & React.RefAttributes<HTMLElement>
  >;
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
  delay = 300,
}: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);
  const [coords, setCoords] = useState({ top: 0, left: 0 });
  const [actualSide, setActualSide] = useState<"top" | "bottom" | "left" | "right">(side);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const triggerRef = useRef<HTMLElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  const showTooltip = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    timeoutRef.current = setTimeout(() => {
      if (triggerRef.current) {
        const rect = triggerRef.current.getBoundingClientRect();
        let calculatedSide = side;

        // Smart flip if too close to edges
        if (side === "top" && rect.top < 40) calculatedSide = "bottom";
        if (side === "bottom" && window.innerHeight - rect.bottom < 40) calculatedSide = "top";
        if (side === "left" && rect.left < 60) calculatedSide = "right";
        if (side === "right" && window.innerWidth - rect.right < 60) calculatedSide = "left";

        let top = 0;
        let left = 0;

        if (calculatedSide === "right") {
          top = rect.top + rect.height / 2;
          left = rect.right + 8;
        } else if (calculatedSide === "left") {
          top = rect.top + rect.height / 2;
          left = rect.left - 8;
        } else if (calculatedSide === "top") {
          top = rect.top - 8;
          left = rect.left + rect.width / 2;
        } else {
          top = rect.bottom + 8;
          left = rect.left + rect.width / 2;
        }

        setCoords({ top, left });
        setActualSide(calculatedSide);
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

  const child = children as React.ReactElement<
    React.HTMLAttributes<HTMLElement> & React.RefAttributes<HTMLElement>
  >;
  const childProps = child.props;

  // Use cloneElement to attach refs and events to children.
  const trigger = React.cloneElement(child, {
    ref: triggerRef,
    style: { ...childProps.style, cursor: "pointer" },
    onMouseEnter: (e: React.MouseEvent<HTMLElement>) => {
      childProps.onMouseEnter?.(e);
      showTooltip();
    },
    onMouseLeave: (e: React.MouseEvent<HTMLElement>) => {
      childProps.onMouseLeave?.(e);
      hideTooltip();
    },
    onFocus: (e: React.FocusEvent<HTMLElement>) => {
      childProps.onFocus?.(e);
      showTooltip();
    },
    onBlur: (e: React.FocusEvent<HTMLElement>) => {
      childProps.onBlur?.(e);
      hideTooltip();
    },
  });

  const alignmentClass = 
    actualSide === "top" ? "-translate-x-1/2 -translate-y-full" :
    actualSide === "bottom" ? "-translate-x-1/2" :
    actualSide === "left" ? "-translate-x-full -translate-y-1/2" :
    "-translate-y-1/2";

  const sideClass = 
    actualSide === "left" ? "origin-right" : 
    actualSide === "right" ? "origin-left" : 
    actualSide === "top" ? "origin-bottom" : "origin-top";

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
          className={`pointer-events-none ${alignmentClass} ${sideClass} animate-in fade-in zoom-in-95 duration-200`}
        >
          <div className="rounded-[8px] border border-black/5 bg-white/95 px-2.5 py-1 text-[12px] font-medium text-black shadow-[0_4px_16px_rgba(0,0,0,0.08)] backdrop-blur-md dark:border-white/10 dark:bg-[#1f2225]/95 dark:text-white">
            {content}
          </div>
        </div>,
        document.body
      )}
    </>
  );
}
