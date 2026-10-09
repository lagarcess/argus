"use client";

import Image from "next/image";
import { useEffect, useId, useRef, useState, type CSSProperties } from "react";
import styles from "./personal-signup-scene.module.css";

const welcome = { src: "/cuadrao-site/personal-welcome-preview.png", width: 1320, height: 2868, logo: { x: 50, y: 41 } } as const;
type Point = Readonly<{ x: number; y: number }>;
type Flight = Readonly<{ pet: Point; envelope: Point; target: Point }>;
const center = (element: HTMLElement): Point => {
  const rect = element.getBoundingClientRect();
  return { x: rect.left + rect.width / 2, y: rect.top + rect.height / 2 };
};

export function usePersonalSignupScene() {
  const root = useRef<HTMLElement>(null);
  const pet = useRef<HTMLSpanElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const logo = useRef<HTMLSpanElement>(null);
  const [flight, setFlight] = useState<Flight | null>(null);

  useEffect(() => {
    const surface = root.current;
    if (!surface) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
    const fine = window.matchMedia("(hover: hover) and (pointer: fine)");
    let frame = 0;
    const resetEyes = () => {
      cancelAnimationFrame(frame);
      surface.style.setProperty("--eye-x", "0px");
      surface.style.setProperty("--eye-y", "0px");
    };
    const follow = (event: PointerEvent) => {
      if (reduced.matches || !fine.matches || event.pointerType === "touch" || !pet.current) return;
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        if (!pet.current) return;
        const origin = center(pet.current);
        const dx = event.clientX - origin.x;
        const dy = event.clientY - origin.y;
        const distance = Math.max(1, Math.hypot(dx, dy));
        surface.style.setProperty("--eye-x", `${dx / distance * 3}px`);
        surface.style.setProperty("--eye-y", `${dy / distance * 3}px`);
      });
    };
    const settle = () => setFlight(null);
    const preference = () => { resetEyes(); settle(); };
    const keyboard = (event: KeyboardEvent) => { if (event.key === "Tab") resetEyes(); };
    surface.addEventListener("pointermove", follow);
    surface.addEventListener("pointerleave", resetEyes);
    surface.addEventListener("keydown", keyboard);
    window.addEventListener("resize", settle);
    window.addEventListener("scroll", settle, { passive: true });
    reduced.addEventListener("change", preference);
    fine.addEventListener("change", resetEyes);
    return () => {
      cancelAnimationFrame(frame);
      surface.removeEventListener("pointermove", follow);
      surface.removeEventListener("pointerleave", resetEyes);
      surface.removeEventListener("keydown", keyboard);
      window.removeEventListener("resize", settle);
      window.removeEventListener("scroll", settle);
      reduced.removeEventListener("change", preference);
      fine.removeEventListener("change", resetEyes);
    };
  }, []);

  function celebrate() {
    if (!pet.current || !button.current || !logo.current || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const target = center(logo.current);
    const origin = center(pet.current);
    if ([target, origin].some(({ x, y }) => x < 24 || x > window.innerWidth - 24 || y < 24 || y > window.innerHeight - 24)) return;
    setFlight({ pet: origin, envelope: center(button.current), target });
  }

  return { rootRef: root, petRef: pet, buttonRef: button, logoRef: logo, flight, celebrate, finish: () => setFlight(null) };
}

type Scene = ReturnType<typeof usePersonalSignupScene>;

export function SignupPet({ petRef, pose = "rest" }: { petRef?: Scene["petRef"]; pose?: "rest" | "excited" | "delivered" }) {
  return <span ref={petRef} className={styles.pet} data-signup-pet="" data-pose={pose} aria-hidden="true">
    <span className={styles.eyes}><i /><i /></span><span className={styles.smile} />
    <span className={styles.foot} /><span className={styles.foot} />
  </span>;
}

export function WelcomePhone({ logoRef, flying, alt, delivered }: { logoRef: Scene["logoRef"]; flying: boolean; alt: string; delivered: boolean }) {
  const wrist = useId();
  return <div className={styles.scene} data-welcome-phone="">
    <svg className={styles.palm} viewBox="0 0 460 690" aria-hidden="true">
      <defs><linearGradient id={wrist} x1="0" y1="0" x2="0" y2="1"><stop offset=".78" stopColor="#050505" /><stop offset="1" stopColor="#050505" stopOpacity="0" /></linearGradient></defs>
      <path fill={`url(#${wrist})`} d="M91 690C103 637 74 593 61 548C48 502 50 444 54 396L64 283C66 261 79 251 92 257C106 263 107 277 105 298L103 374C127 345 171 306 229 259L384 151C400 133 424 135 431 151C440 169 430 184 415 199L365 263L376 330C403 369 405 404 388 456L345 568C333 606 321 647 315 690Z" />
    </svg>
    <div className={styles.device}>
      <div className={styles.screen}>
        <Image src={welcome.src} width={welcome.width} height={welcome.height} alt={alt} sizes="(max-width: 700px) 240px, 280px" priority />
        <span className={styles.wordmark} aria-hidden="true"><Image src="/cuadrao-site/cuadrao-lockup-light.svg" width={268} height={56} alt="" /></span>
        <span ref={logoRef} className={styles.logo} style={{ left: `${welcome.logo.x}%`, top: `${welcome.logo.y}%` }} data-phone-logo="" aria-hidden="true">
          {flying && <span className={styles.ripple} />}
          {delivered && !flying && <span className={styles.deliveredPet}><SignupPet pose="delivered" /></span>}
        </span>
      </div>
    </div>
    <svg className={styles.fingers} viewBox="0 0 460 690" aria-hidden="true">
      <g fill="#050505">
        <path d="M348 270C366 260 389 272 391 290C394 310 382 327 365 327L327 323C310 321 302 307 307 293C312 279 333 279 348 270Z" />
        <path d="M351 350C370 342 391 354 391 372C392 391 379 405 362 404L312 397C296 395 290 383 295 370C301 355 333 358 351 350Z" />
        <path d="M344 428C360 421 378 432 377 448C376 466 363 478 348 474L319 468C304 466 298 453 304 442C312 430 330 434 344 428Z" />
      </g>
    </svg>
  </div>;
}

export function SignupFlight({ flight, onFinish }: { flight: Flight | null; onFinish: () => void }) {
  if (!flight) return null;
  const { pet, envelope, target } = flight;
  const style = {
    "--pet-x": `${pet.x}px`, "--pet-y": `${pet.y}px`,
    "--from-x": `${envelope.x}px`, "--from-y": `${envelope.y}px`,
    "--to-x": `${target.x}px`, "--to-y": `${target.y}px`,
    "--arc-x": `${envelope.x + (target.x - envelope.x) * .55}px`,
    "--arc-y": `${Math.min(envelope.y, target.y) - 90}px`,
  } as CSSProperties;
  return <div className={styles.flight} style={style} data-signup-flight="" aria-hidden="true">
    <div className={styles.flyingPet} onAnimationEnd={onFinish}><SignupPet pose="excited" /></div>
    <div className={styles.envelope}><svg viewBox="0 0 52 38"><rect x="1" y="1" width="50" height="36" rx="6" fill="#fffdf4" stroke="#294f43" strokeWidth="2" /><path d="m3 4 23 17L49 4M3 34l17-15m12 0 17 15" fill="none" stroke="#294f43" strokeWidth="2" strokeLinejoin="round" /></svg></div>
  </div>;
}
