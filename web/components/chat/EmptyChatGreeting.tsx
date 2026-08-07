"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArgusLogo } from "@/components/ArgusLogo";

/* The signed-in empty chat: the muted mark reuses the treatment from
 * ConversationRetrievalState (currentColor at low alpha), and the typewriter
 * greeting is the screen's one animated element. Screen readers get the full
 * sentence once through a polite status region, never character by character;
 * reduced motion renders the sentence instantly. */

type GreetingSlot = "early" | "day" | "evening" | "night";

export function greetingSlotForHour(hour: number): GreetingSlot {
  if (hour >= 5 && hour < 9) return "early";
  if (hour >= 9 && hour < 18) return "day";
  if (hour >= 18 && hour < 23) return "evening";
  return "night";
}

const TYPE_INTERVAL_MS = 35;

export default function EmptyChatGreeting() {
  const { t } = useTranslation();
  const [greeting, setGreeting] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(0);
  const [done, setDone] = useState(false);

  useEffect(() => {
    // Local clock only after mount: the server cannot know the visitor's hour,
    // and a mismatched SSR greeting would flash-correct on hydration.
    const slot = greetingSlotForHour(new Date().getHours());
    const text = t(`chat.greeting.${slot}`, "What should we try today?");
    setGreeting(text);
    const reduceMotion = window.matchMedia?.(
      "(prefers-reduced-motion: reduce)",
    )?.matches;
    if (reduceMotion) {
      setVisibleCount(text.length);
      setDone(true);
      return;
    }
    let shown = 0;
    const interval = window.setInterval(() => {
      shown += 1;
      setVisibleCount(shown);
      if (shown >= text.length) {
        window.clearInterval(interval);
        setDone(true);
      }
    }, TYPE_INTERVAL_MS);
    return () => window.clearInterval(interval);
  }, [t]);

  return (
    <div
      className="mb-8 flex min-h-[108px] flex-col items-center gap-5"
      data-testid="empty-chat-greeting"
    >
      <ArgusLogo
        aria-hidden="true"
        className="h-12 w-12 text-black/15 dark:text-white/15"
      />
      <p
        aria-hidden="true"
        className="font-display min-h-[1.4em] text-center text-[24px] font-medium leading-[1.3] tracking-[-0.24px] text-black/80 sm:text-[28px] dark:text-white/80"
      >
        {greeting ? greeting.slice(0, visibleCount) : " "}
        {greeting && !done ? (
          <span
            aria-hidden="true"
            className="ml-0.5 inline-block h-[1.05em] w-[2px] translate-y-[0.18em] animate-pulse bg-black/40 motion-reduce:animate-none dark:bg-white/40"
          />
        ) : null}
      </p>
      <span className="sr-only" role="status">
        {greeting ?? ""}
      </span>
    </div>
  );
}
