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
  const gradient = useId();
  return <div className={styles.scene} data-welcome-phone="">
    <svg className={styles.palm} viewBox="0 0 460 690" aria-hidden="true">
      <defs><linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#36584b" /><stop offset=".6" stopColor="#142d25" /><stop offset="1" stopColor="#071a14" /></linearGradient></defs>
      <path fill={`url(#${gradient})`} d="M110 686C105 637 81 601 65 542C48 480 44 425 51 361L61 280C63 258 78 251 92 257C110 265 108 295 108 319L111 378C134 345 188 295 230 263L330 146C343 128 363 129 374 142C385 154 381 171 371 186L324 261L385 340C414 380 410 421 385 475L337 578L324 686Z" />
      <path d="M82 348C75 435 78 491 108 541" fill="none" stroke="#688477" strokeOpacity=".23" strokeWidth="3" strokeLinecap="round" />
    </svg>
    <div className={styles.device}>
      <div className={styles.screen}>
        <Image src={welcome.src} width={welcome.width} height={welcome.height} alt={alt} sizes="(max-width: 700px) 240px, 280px" priority />
        <span ref={logoRef} className={styles.logo} style={{ left: `${welcome.logo.x}%`, top: `${welcome.logo.y}%` }} data-phone-logo="" aria-hidden="true">
          {flying && <span className={styles.ripple} />}
          {delivered && !flying && <span className={styles.deliveredPet}><SignupPet pose="delivered" /></span>}
        </span>
      </div>
    </div>
    <svg className={styles.fingers} viewBox="0 0 460 690" aria-hidden="true">
      <defs><linearGradient id={`${gradient}-fingers`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#3b5a4e" /><stop offset=".4" stopColor="#203c31" /><stop offset="1" stopColor="#10251d" /></linearGradient></defs>
      <g fill={`url(#${gradient}-fingers)`} stroke="#0b2119" strokeWidth="1.5">
        <path d="M343 280C360 266 390 274 398 294C410 323 395 342 372 343L321 338C302 335 296 314 305 301C313 289 331 289 343 280Z" />
        <path d="M348 358C368 343 395 352 400 373C407 398 391 416 370 415L309 408C289 405 284 385 295 371C306 357 330 364 348 358Z" />
        <path d="M341 432C361 420 383 431 383 450C384 471 369 486 347 482L312 477C293 474 286 457 296 443C306 430 324 438 341 432Z" />
      </g>
      <path d="M321 301Q350 294 373 300M309 375Q343 371 376 378M310 446Q336 442 356 448" fill="none" stroke="#8da596" strokeOpacity=".17" strokeWidth="3" strokeLinecap="round" />
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
