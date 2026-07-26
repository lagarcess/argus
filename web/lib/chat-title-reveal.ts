export const TITLE_REVEAL_DURATION_MS = 700;
export const TITLE_REVEAL_CHAR_CYCLE_MS = 55;

const SCRAMBLE_CHARSET =
  "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789";

export type TitleRevealFrame = {
  settled: string;
  scrambled: string;
};

export function defaultRandomChar(): string {
  return (
    SCRAMBLE_CHARSET[Math.floor(Math.random() * SCRAMBLE_CHARSET.length)] ?? ""
  );
}

/**
 * One animation frame of the left-to-right reveal. Settled characters are
 * final; the tail cycles quiet glyphs. Spaces never scramble so word shape
 * stays readable.
 */
export function titleRevealFrame(
  target: string,
  progress: number,
  randomChar: (index: number) => string = defaultRandomChar,
): TitleRevealFrame {
  const clamped = Math.min(1, Math.max(0, progress));
  const eased = 1 - (1 - clamped) * (1 - clamped);
  const settledCount = Math.floor(eased * target.length);
  const settled = target.slice(0, settledCount);
  let scrambled = "";
  for (let index = settledCount; index < target.length; index += 1) {
    scrambled += target[index] === " " ? " " : randomChar(index);
  }
  return { settled, scrambled };
}

/**
 * Advance the settle boundary while keeping the previous frame's glyphs, so
 * the tail only re-randomizes on the cycle cadence instead of every frame.
 */
export function advanceRevealFrame(
  previous: TitleRevealFrame,
  target: string,
  progress: number,
): TitleRevealFrame {
  const fresh = titleRevealFrame(target, progress);
  if (fresh.scrambled.length >= previous.scrambled.length) return fresh;
  return {
    settled: fresh.settled,
    scrambled: previous.scrambled.slice(
      previous.scrambled.length - fresh.scrambled.length,
    ),
  };
}
