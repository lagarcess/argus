"use client";

import Image from "next/image";
import { useEffect, useRef, type ReactNode } from "react";
import styles from "./touchup-shell.module.css";

export function FooterMotion({ children }: { children: ReactNode }) {
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
    const atBottom = () =>
      window.scrollY + window.innerHeight >=
      document.documentElement.scrollHeight - 2;
    const settle = () => {
      clearTimeout(returnTimer);
      moving.style.transitionDuration = "420ms";
      moving.style.setProperty("--footer-peek", "0px");
    };
    const peek = (delta: number) => {
      if (delta <= 0 || !atBottom() || reducedMotion.matches) {
        settle();
        return;
      }
      const current = -new DOMMatrixReadOnly(
        getComputedStyle(moving).transform,
      ).m42;
      const limit = Math.min(strip.offsetHeight, frame.offsetHeight * 0.6);
      const reveal = Math.min(limit, current + delta * 0.35);
      clearTimeout(returnTimer);
      moving.style.transitionDuration = "60ms";
      moving.style.setProperty("--footer-peek", `${reveal}px`);
      returnTimer = setTimeout(settle, 140);
    };
    const wheel = (event: WheelEvent) => {
      if (event.ctrlKey || Math.abs(event.deltaX) > Math.abs(event.deltaY)) return;
      const unit = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? innerHeight : 1;
      peek(event.deltaY * unit);
    };
    const touchStart = (event: TouchEvent) => {
      touchY = event.touches.length === 1 ? event.touches[0].clientY : undefined;
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
      settle();
    };

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
      window.removeEventListener("wheel", wheel);
      window.removeEventListener("touchstart", touchStart);
      window.removeEventListener("touchmove", touchMove);
      window.removeEventListener("touchend", touchEnd);
      window.removeEventListener("touchcancel", touchEnd);
      window.removeEventListener("scroll", scroll);
      window.removeEventListener("resize", reset);
      reducedMotion.removeEventListener("change", reset);
    };
  }, []);

  return (
    <div ref={panel} className={styles.motion} data-footer-peek aria-hidden="true">
      <div ref={track} className={styles.peekTrack}>
        {children}
        <div ref={photos} className={styles.photoStrip}>
          <Image
            src="/cuadrao-site/footer-dressmaker.png"
            width={1456}
            height={1360}
            sizes="50vw"
            loading="eager"
            alt=""
          />
          <Image
            src="/cuadrao-site/footer-artisan.jpg"
            width={1728}
            height={1152}
            sizes="50vw"
            loading="eager"
            alt=""
          />
        </div>
      </div>
    </div>
  );
}
