"use client";

import {
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
} from "react";
import { FileText, Check, Search } from "lucide-react";
import type { BusinessLocale } from "./content";
import { touchupCopy } from "./touchup-copy";
import styles from "./touchup.module.css";

export function CaptureStory({ locale }: { locale: BusinessLocale }) {
  const c = touchupCopy[locale];
  const [active, setActive] = useState(0);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const current = c.steps[active];
  const Icon = [FileText, Search, Check][active];
  const onKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    index: number,
  ) => {
    const keys: Record<string, number> = {
      ArrowRight: (index + 1) % c.steps.length,
      ArrowLeft: (index + c.steps.length - 1) % c.steps.length,
      Home: 0,
      End: c.steps.length - 1,
    };
    if (!(event.key in keys)) return;
    event.preventDefault();
    const next = keys[event.key];
    setActive(next);
    buttons.current[next]?.focus();
  };
  return (
    <section
      className={`${styles.section} ${styles.story}`}
      id="la-idea"
      aria-labelledby="capture-title"
    >
      <div>
        <p className={styles.eyebrow}>{c.storyLabel}</p>
        <h2 id="capture-title">{c.storyTitle}</h2>
        <p>{c.storyBody}</p>
        <div
          className={styles.rail}
          role="tablist"
          aria-label={c.storyLabel}
          style={{ "--step": active } as CSSProperties}
        >
          {c.steps.map((step, index) => (
            <button
              key={step.title}
              type="button"
              role="tab"
              id={`capture-tab-${index}`}
              aria-selected={active === index}
              aria-controls="capture-panel"
              tabIndex={active === index ? 0 : -1}
              ref={(element) => {
                buttons.current[index] = element;
              }}
              onClick={() => setActive(index)}
              onKeyDown={(event) => onKeyDown(event, index)}
            >
              {step.title}
            </button>
          ))}
        </div>
        <p className={styles.caption}>{c.truth}</p>
      </div>
      <div
        className={styles.recordCard}
        role="tabpanel"
        id="capture-panel"
        aria-labelledby={`capture-tab-${active}`}
        tabIndex={0}
      >
        <Icon size={26} strokeWidth={1.4} aria-hidden="true" />
        <h3>{current.label}</h3>
        <p>{current.body}</p>
        <div className={styles.recordDetail}>
          <span>{current.detail}</span>
          <strong>{current.amount}</strong>
          <small>{current.status}</small>
        </div>
      </div>
    </section>
  );
}
