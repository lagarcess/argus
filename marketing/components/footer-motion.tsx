"use client";

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import { Pause, Play } from "lucide-react";
import type { BusinessLocale } from "./content";
import styles from "./touchup-shell.module.css";

export function FooterMotion({ locale }: { locale: BusinessLocale }) {
  const [paused, setPaused] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const element = panel.current;
    if (!element) return;
    const observer = new IntersectionObserver(([entry]) => {
      element.dataset.visible = String(entry.isIntersecting);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  const label = paused
    ? locale === "es"
      ? "Reanudar animación"
      : "Resume animation"
    : locale === "es"
      ? "Pausar animación"
      : "Pause animation";
  return (
    <div
      ref={panel}
      className={styles.motion}
      data-paused={paused}
      data-visible="false"
    >
      <div className={styles.photoStrip} aria-hidden="true">
        <Image
          src="/cuadrao-site/florist.webp"
          width={1200}
          height={800}
          sizes="50vw"
          alt=""
        />
        <Image
          src="/cuadrao-site/accountant.webp"
          width={1200}
          height={800}
          sizes="50vw"
          alt=""
        />
      </div>
      <div className={styles.grid} aria-hidden="true">
        <i className={styles.vertical} />
        <i className={styles.horizontal} />
        <i className={styles.corner} />
        <i className={styles.cornerEnd} />
      </div>
      <button
        type="button"
        className={styles.motionControl}
        onClick={() => setPaused(!paused)}
        aria-label={label}
        aria-pressed={paused}
      >
        {paused ? (
          <Play size={14} aria-hidden="true" />
        ) : (
          <Pause size={14} aria-hidden="true" />
        )}
        {label}
      </button>
    </div>
  );
}
