"use client";

import Image from "next/image";
import { useEffect, useRef, type ReactNode } from "react";
import styles from "./touchup-shell.module.css";

export function FooterMotion({
  children,
  presentation = "pair",
}: {
  children: ReactNode;
  presentation?: "pair" | "sequence";
}) {
  const panel = useRef<HTMLDivElement>(null);
  const track = useRef<HTMLDivElement>(null);
  const photos = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const frame = panel.current;
    const moving = track.current;
    const strip = photos.current;
    if (!frame || !moving || !strip) return;

    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let returnTimer: ReturnType<typeof setTimeout> | undefined;
    let touchY: number | undefined;
    let reveal = 0;
    let returning = false;
    const atBottom = () =>
      window.scrollY + window.innerHeight >=
      document.documentElement.scrollHeight - 2;
    const settle = () => {
      clearTimeout(returnTimer);
      returning = true;
      moving.style.transitionDuration = "500ms";
      moving.style.setProperty("--footer-peek", "0px");
      if (presentation === "sequence" && new DOMMatrixReadOnly(getComputedStyle(moving).transform).m42 === 0) {
        reveal = 0;
        frame.removeAttribute("data-revealing");
      }
    };
    const peek = (delta: number) => {
      if (delta <= 0 || !atBottom() || reducedMotion.matches) {
        settle();
        return;
      }
      if (returning) {
        reveal = -new DOMMatrixReadOnly(getComputedStyle(moving).transform).m42;
        returning = false;
      }
      reveal = Math.min(strip.offsetHeight, reveal + delta * 0.75);
      if (presentation === "sequence" && reveal > 0 && !frame.hasAttribute("data-revealing")) {
        frame.setAttribute("data-revealing", "");
      }
      clearTimeout(returnTimer);
      moving.style.transitionDuration = "60ms";
      moving.style.setProperty("--footer-peek", `${reveal}px`);
    };
    const wheel = (event: WheelEvent) => {
      if (event.ctrlKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? innerHeight : 1;
      peek(event.deltaY * unit);
      if (touchY === undefined) returnTimer = setTimeout(settle, 240);
    };
    const touchStart = (event: TouchEvent) => {
      touchY = event.touches.length === 1 ? event.touches[0].clientY : undefined;
      if (touchY !== undefined) clearTimeout(returnTimer);
      else settle();
    };
    const touchMove = (event: TouchEvent) => {
      if (event.touches.length !== 1 || touchY === undefined) return;
      const nextY = event.touches[0].clientY;
      peek(touchY - nextY);
      touchY = nextY;
    };
    const touchEnd = () => {
      touchY = undefined;
      settle();
    };
    const scroll = () => {
      if (!atBottom()) settle();
    };
    const reset = () => {
      touchY = undefined;
      frame.removeAttribute("data-revealing");
      settle();
    };
    const returned = (event: TransitionEvent) => {
      if (event.target !== moving || event.propertyName !== "transform" || !returning) return;
      reveal = 0;
      frame.removeAttribute("data-revealing");
    };

    moving.addEventListener("transitionend", returned);
    window.addEventListener("wheel", wheel, { passive: true });
    window.addEventListener("touchstart", touchStart, { passive: true });
    window.addEventListener("touchmove", touchMove, { passive: true });
    window.addEventListener("touchend", touchEnd, { passive: true });
    window.addEventListener("touchcancel", touchEnd, { passive: true });
    window.addEventListener("scroll", scroll, { passive: true });
    window.addEventListener("resize", reset);
    reducedMotion.addEventListener("change", reset);
    return () => {
      clearTimeout(returnTimer);
      moving.removeEventListener("transitionend", returned);
      window.removeEventListener("wheel", wheel);
      window.removeEventListener("touchstart", touchStart);
      window.removeEventListener("touchmove", touchMove);
      window.removeEventListener("touchend", touchEnd);
      window.removeEventListener("touchcancel", touchEnd);
      window.removeEventListener("scroll", scroll);
      window.removeEventListener("resize", reset);
      reducedMotion.removeEventListener("change", reset);
    };
  }, [presentation]);

  return (
    <div ref={panel} className={styles.motion} data-footer-peek>
      <div ref={track} className={styles.peekTrack}>
        {children}
        <div ref={photos} className={`${styles.photoStrip} ${presentation === "sequence" ? styles.photoSequence : ""}`} aria-hidden="true">
          <Image
            src="/cuadrao-site/footer-dressmaker.png"
            width={1456}
            height={1360}
            sizes={presentation === "sequence" ? "100vw" : "50vw"}
            loading="eager"
            alt=""
          />
          <Image
            src="/cuadrao-site/footer-artisan.jpg"
            width={1728}
            height={1152}
            sizes={presentation === "sequence" ? "100vw" : "50vw"}
            loading="eager"
            alt=""
          />
        </div>
      </div>
    </div>
  );
}
