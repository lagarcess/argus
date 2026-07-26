"use client";

import { useLayoutEffect, useRef, useState } from "react";
import type { TitleSource } from "@/lib/argus-api";
import {
  shouldPlayTitleReveal,
  type HeaderTitleState,
} from "@/lib/chat-title-display";
import {
  advanceRevealFrame,
  TITLE_REVEAL_CHAR_CYCLE_MS,
  TITLE_REVEAL_DURATION_MS,
  titleRevealFrame,
  type TitleRevealFrame,
} from "@/lib/chat-title-reveal";

type ChatHeaderTitleProps = {
  conversationId: string | null;
  title: string;
  titleSource: TitleSource | null;
};

/**
 * Conversation name in the chat header. Plays the scramble reveal only when
 * the active conversation earns its generated name; renders statically for
 * navigation, renames, and reduced motion (which gets a plain fade).
 */
export default function ChatHeaderTitle({
  conversationId,
  title,
  titleSource,
}: ChatHeaderTitleProps) {
  const [frame, setFrame] = useState<TitleRevealFrame | null>(null);
  const [fadeTick, setFadeTick] = useState(0);
  const previousStateRef = useRef<HeaderTitleState | null>(null);
  const animationFrameRef = useRef<number | null>(null);
  const settleTimeoutRef = useRef<number | null>(null);

  // Layout effect so the reveal's first frame paints instead of the final
  // title flashing for one frame before the animation starts.
  useLayoutEffect(() => {
    const next: HeaderTitleState | null = conversationId
      ? { conversationId, title, titleSource }
      : null;
    const previous = previousStateRef.current;
    previousStateRef.current = next;

    const cancelTimers = () => {
      if (animationFrameRef.current !== null) {
        window.cancelAnimationFrame(animationFrameRef.current);
        animationFrameRef.current = null;
      }
      if (settleTimeoutRef.current !== null) {
        window.clearTimeout(settleTimeoutRef.current);
        settleTimeoutRef.current = null;
      }
    };
    cancelTimers();

    if (!next || !shouldPlayTitleReveal(previous, next)) {
      setFrame(null);
      return;
    }
    // Hidden tabs pause rAF; nobody is watching, so skip straight to the name.
    if (document.visibilityState !== "visible") {
      setFrame(null);
      return;
    }
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setFrame(null);
      setFadeTick((tick) => tick + 1);
      return;
    }

    const start = performance.now();
    let lastCycleAt = start;
    let currentFrame = titleRevealFrame(next.title, 0);
    setFrame(currentFrame);

    const tick = (now: number) => {
      const progress = (now - start) / TITLE_REVEAL_DURATION_MS;
      if (progress >= 1) {
        cancelTimers();
        setFrame(null);
        return;
      }
      if (now - lastCycleAt >= TITLE_REVEAL_CHAR_CYCLE_MS) {
        lastCycleAt = now;
        currentFrame = titleRevealFrame(next.title, progress);
      } else {
        currentFrame = advanceRevealFrame(currentFrame, next.title, progress);
      }
      setFrame(currentFrame);
      animationFrameRef.current = window.requestAnimationFrame(tick);
    };
    animationFrameRef.current = window.requestAnimationFrame(tick);
    // rAF stops in backgrounded tabs; this guarantees the name still settles.
    settleTimeoutRef.current = window.setTimeout(() => {
      cancelTimers();
      setFrame(null);
    }, TITLE_REVEAL_DURATION_MS + 250);

    return cancelTimers;
  }, [conversationId, title, titleSource]);

  if (frame !== null) {
    return (
      <>
        <span aria-hidden="true" className="whitespace-pre">
          {frame.settled}
          <span className="opacity-55">{frame.scrambled}</span>
        </span>
        <span className="sr-only">{title}</span>
      </>
    );
  }
  return (
    <span
      key={fadeTick}
      className={fadeTick > 0 ? "animate-in fade-in duration-300" : undefined}
    >
      {title}
    </span>
  );
}
