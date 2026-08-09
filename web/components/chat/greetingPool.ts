/**
 * Which greeting the empty chat says today.
 *
 * The defect this replaces was repetition, not slot count: the day window is
 * nine hours wide, so anyone opening Argus during a workday saw one identical
 * sentence forever. A fifth slot would not have fixed that.
 *
 * Rotation is stable for the whole local day and changes tomorrow. Seeding from
 * the clock instead would mean refreshing the page rolls a new greeting, which
 * is exactly what makes a line read as generated rather than said.
 *
 * Market session lines are pool members, never overrides. Time of day describes
 * the user and session describes the market, and the two decouple outside
 * Eastern time: 5am local overlaps US pre-market only for an Eastern user. So an
 * active session widens the current slot's pool and the same day-stable seed
 * picks from the wider set, with the generic lines still in play.
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

type PoolMember = {
  /** Key under `chat.greeting` in the locale files. */
  key: string;
  /** Eligible only while this session is the active one. */
  session?: MarketSessionPhase;
  /** Eligible only once the user has said what Argus should call them. */
  needsName?: boolean;
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

/*
 * Six for `day`, because a weekday user lives entirely inside it and three
 * would cycle visibly within a week. Fewer elsewhere is fine; nobody is in the
 * 3am slot on a schedule.
 *
 * Only some members carry a name. Every greeting using someone's name gets
 * grating in about three days.
 */
const SLOT_POOL: Record<GreetingSlot, PoolMember[]> = {
  early: [
    { key: "early_a" },
    { key: "early_b" },
    { key: "early_c" },
    { key: "early_named_a", needsName: true },
  ],
  day: [
    { key: "day_a" },
    { key: "day_b" },
    { key: "day_c" },
    { key: "day_d" },
    { key: "day_e" },
    { key: "day_f" },
    { key: "day_named_a", needsName: true },
    { key: "day_named_b", needsName: true },
  ],
  evening: [
    { key: "evening_a" },
    { key: "evening_b" },
    { key: "evening_c" },
    { key: "evening_d" },
    { key: "evening_named_a", needsName: true },
  ],
  night: [
    { key: "night_a" },
    { key: "night_b" },
    { key: "night_c" },
    { key: "night_named_a", needsName: true },
  ],
};

/*
 * Weighted unevenly on purpose. A closure is a two-day state where the market
 * fact is the most useful thing Argus can say, so it speaks often. Pre-market
 * and after-hours are transient and mostly irrelevant to backtesting, so they
 * surface on the odd day rather than as a headline.
 *
 * An open market gets no line: it is the default state of a weekday and saying
 * so adds nothing. Neither does overnight on a trading day, where the weekend
 * sentence would be false.
 *
 * Every closure line names both asset classes. Argus supports crypto and
 * currency pairs, which do not close, so a bare "markets are closed" is wrong
 * for those users.
 */
const SESSION_POOL: PoolMember[] = [
  { key: "session_closed_weekend_a", session: "closed_weekend", weight: 3 },
  { key: "session_closed_weekend_b", session: "closed_weekend", weight: 3 },
  { key: "session_closed_holiday_a", session: "closed_holiday", weight: 3 },
  { key: "session_closed_holiday_b", session: "closed_holiday", weight: 3 },
  { key: "session_pre_market_a", session: "pre_market" },
  { key: "session_after_hours_a", session: "after_hours" },
];

/** Every key the pools can ask for, for the locale-coverage guard. */
export const GREETING_KEYS: readonly string[] = [
  ...Object.values(SLOT_POOL).flat(),
  ...SESSION_POOL,
].map((member) => member.key);

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

function eligibleMembers({
  slot,
  session,
  hasName,
}: {
  slot: GreetingSlot;
  session: MarketSessionPhase | null;
  hasName: boolean;
}): PoolMember[] {
  return [...SLOT_POOL[slot], ...SESSION_POOL].filter(
    (member) =>
      (member.session === undefined || member.session === session) &&
      (!member.needsName || hasName),
  );
}

/**
 * The pool laid out as a ring where no two neighbours are the same line.
 *
 * Heaviest first into every other position, then the gaps. That is what keeps a
 * weight-3 closure line from landing beside itself, which a plain repeated list
 * would do and which is the one way a day-by-day walk could still repeat.
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
 * The key for today. It holds all day, and tomorrow's is a different line.
 *
 * The walk is one step a day around the ring above, so consecutive days are
 * neighbours and neighbours are never equal. That is the no-repeat rule as a
 * property of the arrangement rather than as a check that has to look up what
 * yesterday actually said, which is unknowable here: yesterday's market session
 * is gone.
 */
export function pickGreetingKey({
  slot,
  session,
  hasName,
  at,
}: {
  slot: GreetingSlot;
  session: MarketSessionPhase | null;
  hasName: boolean;
  at: Date;
}): string {
  const members = eligibleMembers({ slot, session, hasName });
  const ring = arrangeRing(members);
  // Two pools of the same size start at different points, so a name or an open
  // market does not just shift everyone onto the same line.
  const offset = hash(members.map((member) => member.key).join("|"));
  return ring[(localDayOrdinal(at) + offset) % ring.length];
}

/** Test seam: the ring a pool resolves to, for the adjacency invariant. */
export function greetingRingFor(options: {
  slot: GreetingSlot;
  session: MarketSessionPhase | null;
  hasName: boolean;
}): string[] {
  return arrangeRing(eligibleMembers(options));
}
