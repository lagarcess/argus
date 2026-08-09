"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ArgusLogo } from "@/components/ArgusLogo";
import { getMarketSession } from "@/lib/argus-api";
import {
  greetingSlotForHour,
  pickGreetingKey,
  type MarketSessionPhase,
} from "./greetingPool";


/* The signed-in empty chat: the muted mark reuses the treatment from
 * ConversationRetrievalState (currentColor at low alpha), and the typewriter
 * greeting is the screen's one animated element. Screen readers get the full
 * sentence once through a polite status region, never character by character;
 * reduced motion renders the sentence instantly. */

const TYPE_INTERVAL_MS = 35;

// The greeting is cosmetic, so it waits only briefly on the market session and
// then speaks without it rather than leaving the screen wordless.
const SESSION_TIMEOUT_MS = 2_000;

export default function EmptyChatGreeting({
  preferredName,
}: {
  /** What the user asked to be called. Blank means the nameless pool. */
  preferredName?: string | null;
}) {
  const { t } = useTranslation();
  const [greeting, setGreeting] = useState<string | null>(null);
  const [visibleCount, setVisibleCount] = useState(0);
  const [done, setDone] = useState(false);
  const [session, setSession] = useState<MarketSessionPhase | null>(null);
  const [sessionSettled, setSessionSettled] = useState(false);

  // Session is backend truth, computed in Eastern time against the real trading
  // calendar. Reading it from the visitor's clock puts someone in London at 2pm
  // in the middle of a session US pre-market has not opened yet.
  useEffect(() => {
    const controller = new AbortController();
    const timeout = window.setTimeout(
      () => controller.abort(),
      SESSION_TIMEOUT_MS,
    );
    getMarketSession(controller.signal)
      .then((response) => setSession(response.session?.phase ?? null))
      .catch(() => setSession(null))
      .finally(() => {
        window.clearTimeout(timeout);
        setSessionSettled(true);
      });
    return () => {
      window.clearTimeout(timeout);
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!sessionSettled) return;
    // Local clock only after mount: the server cannot know the visitor's hour,
    // and a mismatched SSR greeting would flash-correct on hydration.
    const now = new Date();
    const name = preferredName?.trim() ?? "";
    const key = pickGreetingKey({
      slot: greetingSlotForHour(now.getHours()),
      session,
      hasName: name.length > 0,
      at: now,
    });
    const text = t(`chat.greeting.${key}`, {
      defaultValue: "What should we try today?",
      name,
    });
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
  }, [preferredName, session, sessionSettled, t]);

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
        className="font-display min-h-[1.4em] text-balance text-center text-[24px] font-medium leading-[1.3] tracking-[-0.24px] text-black/80 sm:text-[28px] dark:text-white/80"
      >
        {greeting ? greeting.slice(0, visibleCount) : " "}
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
