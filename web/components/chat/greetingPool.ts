/**
 * Which greeting the empty chat says today.
 *
 * Rotation is stable for the whole local day and changes tomorrow; seeding from
 * the clock would roll a new line on every refresh. Market session lines are
 * pool members, never overrides: time of day describes the user and session
 * describes the market, and the two decouple outside Eastern time.
 *
 * Market flavor is earned. Lines about testing and about the market go only to
 * a market fan, a registered person whose own records show market interest as
 * the backend reports it. Everyone else, every guest included, gets a neutral
 * line.
 *
 * A memory-driven greeting would plug in at `pickGreetingKey`, choosing its own
 * line and falling back here. Nothing does yet, and the corpus for it does not
 * exist: the `memory` field `research_memory_block()` writes into the research
 * sidecar is not a memory record, the four categories in
 * `src/argus/memory/contracts.py` hold no research subject or open thread, and
 * `ARGUS_RESEARCH_RAIL_ENABLED` is false in `render.yaml`.
 */

export type GreetingSlot = "early" | "day" | "evening" | "night";

/** Backend-resolved, in Eastern time. The client never computes this. */
export type MarketSessionPhase =
  | "pre_market"
  | "open"
  | "after_hours"
  | "closed_weekend"
  | "closed_holiday"
  | "closed";

/** What a person's own records show interest in. Backend-owned. */
export type DemonstratedInterest = {
  markets: boolean;
};

type PoolMember = {
  /** Key under `chat.greeting` in the locale files. */
  key: string;
  /** Eligible only while this session is the active one. */
  session?: MarketSessionPhase;
  /** Eligible only once the user has said what Argus should call them. */
  needsName?: boolean;
  /** Eligible only to a market fan. */
  marketFan?: boolean;
  /**
   * Candidate slots this member takes, which is how often it comes up.
   * Defaults to 1.
   */
  weight?: number;
};

export function greetingSlotForHour(hour: number): GreetingSlot {
  if (hour >= 5 && hour < 9) return "early";
  if (hour >= 9 && hour < 18) return "day";
  if (hour >= 18 && hour < 23) return "evening";
  return "night";
}

/* Only some members carry a name; every greeting using one gets grating in a
 * few days. `day_d` reads true at any hour, so night shares it. */
const SLOT_POOL: Record<GreetingSlot, PoolMember[]> = {
  early: [
    { key: "early_a" },
    { key: "early_b", marketFan: true },
    { key: "early_c" },
    { key: "early_named_a", needsName: true },
  ],
  day: [
    { key: "day_a", marketFan: true },
    { key: "day_c", marketFan: true },
    { key: "day_d" },
    { key: "day_e", marketFan: true },
    { key: "day_f" },
    { key: "day_named_a", needsName: true, marketFan: true },
    { key: "day_named_b", needsName: true },
  ],
  evening: [
    { key: "evening_a" },
    { key: "evening_b", marketFan: true },
    { key: "evening_d" },
    { key: "evening_named_a", needsName: true },
  ],
  night: [
    { key: "night_b" },
    { key: "night_c", marketFan: true },
    { key: "night_named_a", needsName: true },
    { key: "day_d" },
  ],
};

/*
 * A session line comes up no more often than any other line. An open market
 * and an overnight lull get no line at all.
 *
 * The session resolves the US equity calendar and nothing else, so a closure
 * line may name only that and crypto, which genuinely never closes. FX closes
 * most of the weekend and a holiday weekend is not always three days.
 */
const SESSION_POOL: PoolMember[] = [
  { key: "session_closed_weekend_a", session: "closed_weekend", marketFan: true },
  { key: "session_closed_holiday_a", session: "closed_holiday", marketFan: true },
  { key: "session_pre_market_a", session: "pre_market", marketFan: true },
];

/** Every key the pools can ask for, for the locale-coverage guard. */
export const GREETING_KEYS: readonly string[] = [
  ...new Set(
    [...Object.values(SLOT_POOL).flat(), ...SESSION_POOL].map(
      (member) => member.key,
    ),
  ),
];

/**
 * Who the greeting speaks to. A guest has no profile and no history of its
 * own, so a guest is nameless and never a market fan, whatever the backend
 * reports.
 */
export function greetingAudience({
  isGuest,
  preferredName,
  interest,
}: {
  isGuest: boolean;
  preferredName?: string | null;
  interest: DemonstratedInterest | null;
}): { name: string; marketFan: boolean } {
  if (isGuest) return { name: "", marketFan: false };
  return {
    name: preferredName?.trim() ?? "",
    marketFan: interest?.markets === true,
  };
}

/** FNV-1a, so a pool's starting point is the pool and nothing else. */
function hash(text: string): number {
  let value = 0x811c9dc5;
  for (let index = 0; index < text.length; index += 1) {
    value ^= text.charCodeAt(index);
    value = Math.imul(value, 0x01000193) >>> 0;
  }
  return value;
}

/** The local calendar day, which is what the slot is already keyed on. */
export function localDayKey(at: Date): string {
  const month = `${at.getMonth() + 1}`.padStart(2, "0");
  const day = `${at.getDate()}`.padStart(2, "0");
  return `${at.getFullYear()}-${month}-${day}`;
}

/** Whole days, counted off the local calendar date so DST cannot shift it. */
function localDayOrdinal(at: Date): number {
  return Math.floor(
    Date.UTC(at.getFullYear(), at.getMonth(), at.getDate()) / 86_400_000,
  );
}

type PoolOptions = {
  slot: GreetingSlot;
  session: MarketSessionPhase | null;
  hasName: boolean;
  marketFan: boolean;
};

function eligibleMembers({
  slot,
  session,
  hasName,
  marketFan,
}: PoolOptions): PoolMember[] {
  return [...SLOT_POOL[slot], ...SESSION_POOL].filter(
    (member) =>
      (member.session === undefined || member.session === session) &&
      (!member.needsName || hasName) &&
      (!member.marketFan || marketFan),
  );
}

/**
 * The pool as a ring where no two neighbours are the same line: heaviest first
 * into every other position, then the gaps.
 */
function arrangeRing(members: PoolMember[]): string[] {
  const byWeight = [...members].sort(
    (left, right) =>
      (right.weight ?? 1) - (left.weight ?? 1) || left.key.localeCompare(right.key),
  );
  const copies = byWeight.flatMap((member) =>
    Array.from({ length: member.weight ?? 1 }, () => member.key),
  );
  const ring = new Array<string>(copies.length);
  let position = 0;
  for (const key of copies) {
    ring[position] = key;
    position += 2;
    if (position >= copies.length) position = 1;
  }
  return ring;
}

/**
 * The key for today. One step a day around the ring above, so consecutive days
 * are neighbours and neighbours are never equal.
 */
export function pickGreetingKey({
  at,
  ...options
}: PoolOptions & { at: Date }): string {
  const members = eligibleMembers(options);
  const ring = arrangeRing(members);
  // Two pools of the same size start at different points.
  const offset = hash(members.map((member) => member.key).join("|"));
  return ring[(localDayOrdinal(at) + offset) % ring.length];
}

/** Test seam: the ring a pool resolves to, for the adjacency invariant. */
export function greetingRingFor(options: PoolOptions): string[] {
  return arrangeRing(eligibleMembers(options));
}
