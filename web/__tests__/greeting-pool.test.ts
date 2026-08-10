import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  GREETING_KEYS,
  greetingRingFor,
  greetingSlotForHour,
  localDayKey,
  pickGreetingKey,
  type GreetingSlot,
  type MarketSessionPhase,
} from "../components/chat/greetingPool";

const root = join(import.meta.dir, "..");
const en = JSON.parse(
  readFileSync(join(root, "public/locales/en/common.json"), "utf-8"),
);
const es = JSON.parse(
  readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
);

const SLOTS: GreetingSlot[] = ["early", "day", "evening", "night"];

function pickAcross(
  days: number,
  options: {
    slot?: GreetingSlot;
    session?: MarketSessionPhase | null;
    hasName?: boolean;
  } = {},
): string[] {
  const picks: string[] = [];
  for (let day = 0; day < days; day += 1) {
    picks.push(
      pickGreetingKey({
        slot: options.slot ?? "day",
        session: options.session ?? null,
        hasName: options.hasName ?? false,
        at: new Date(2026, 0, 1 + day, 12, 0, 0),
      }),
    );
  }
  return picks;
}

describe("greeting pool", () => {
  test("the day slot is wide enough that a weekday user does not see a cycle", () => {
    // The defect was repetition, not slot count: the day window is nine hours,
    // so a workday user lives entirely inside it.
    const distinct = new Set(pickAcross(30));
    expect(distinct.size).toBeGreaterThanOrEqual(5);
  });

  test("a greeting holds all day and does not move on refresh", () => {
    const hours = [9, 12, 15, 17];
    const picks = hours.map((hour) =>
      pickGreetingKey({
        slot: "day",
        session: null,
        hasName: false,
        at: new Date(2026, 4, 14, hour, 37, 12),
      }),
    );
    expect(new Set(picks).size).toBe(1);
  });

  test("tomorrow is a different sentence from today", () => {
    // Seeding from the date is only worth it if consecutive days differ.
    const sessions: (MarketSessionPhase | null)[] = [
      null,
      "closed_weekend",
      "closed_holiday",
      "pre_market",
      "after_hours",
      "open",
    ];
    for (const slot of SLOTS) {
      for (const session of sessions) {
        for (const hasName of [false, true]) {
          const picks = pickAcross(400, { slot, session, hasName });
          const repeats = picks.filter(
            (key, index) => index > 0 && key === picks[index - 1],
          );
          expect(repeats).toEqual([]);
        }
      }
    }
  });

  test("no pool puts a line next to itself, including around the wrap", () => {
    // The walk is one step a day, so the no-repeat rule is a property of the
    // arrangement. A weight-3 closure line beside itself would break it.
    const sessions: (MarketSessionPhase | null)[] = [
      null,
      "closed_weekend",
      "closed_holiday",
      "pre_market",
      "after_hours",
      "open",
      "closed",
    ];
    for (const slot of SLOTS) {
      for (const session of sessions) {
        for (const hasName of [false, true]) {
          const ring = greetingRingFor({ slot, session, hasName });
          expect(ring.length).toBeGreaterThan(1);
          const adjacent = ring.filter(
            (key, index) => key === ring[(index + 1) % ring.length],
          );
          expect({ slot, session, hasName, adjacent }).toEqual({
            slot,
            session,
            hasName,
            adjacent: [],
          });
        }
      }
    }
  });

  test("every line in a pool gets its turn", () => {
    // A hash-modulo pick leaves lines unseen for weeks. A ring does not.
    const ring = greetingRingFor({ slot: "day", session: null, hasName: false });
    expect(new Set(pickAcross(ring.length)).size).toBe(ring.length);
  });

  test("a session line cannot appear outside its session", () => {
    const sessionless = new Set(pickAcross(200, { slot: "day", session: null }));
    expect([...sessionless].filter((key) => key.startsWith("session_"))).toEqual([]);

    const preMarket = new Set(pickAcross(200, { session: "pre_market" }));
    expect(
      [...preMarket].filter(
        (key) => key.startsWith("session_") && !key.includes("pre_market"),
      ),
    ).toEqual([]);
  });

  test("an open market and an overnight lull say nothing about the market", () => {
    // Open is the default state of a weekday, and overnight on a trading day
    // is not a weekend, so the weekend sentence would be false.
    for (const session of ["open", "closed"] as MarketSessionPhase[]) {
      const picks = new Set(pickAcross(200, { session }));
      expect([...picks].filter((key) => key.startsWith("session_"))).toEqual([]);
    }
  });

  test("a closure speaks often and a transient session only occasionally", () => {
    const share = (session: MarketSessionPhase) => {
      const picks = pickAcross(400, { session });
      return picks.filter((key) => key.startsWith("session_")).length / picks.length;
    };
    // Weekend and holiday closure is the most useful thing Argus can say on a
    // two-day shutdown, so it carries weight; pre-market and after-hours are
    // transient and mostly irrelevant to backtesting.
    expect(share("closed_weekend")).toBeGreaterThan(0.35);
    expect(share("closed_holiday")).toBeGreaterThan(0.35);
    expect(share("pre_market")).toBeLessThan(0.25);
    expect(share("after_hours")).toBeLessThan(0.25);
  });

  test("generic lines stay in play while a session is active", () => {
    // Session lines widen the pool; they never take it over.
    const picks = new Set(pickAcross(200, { session: "closed_weekend" }));
    expect([...picks].some((key) => !key.startsWith("session_"))).toBe(true);
  });

  test("a name appears in some greetings and not most of them", () => {
    // Every greeting using someone's name gets grating in about three days.
    const picks = pickAcross(400, { hasName: true });
    const named = picks.filter((key) => key.includes("_named_")).length;
    expect(named).toBeGreaterThan(0);
    expect(named / picks.length).toBeLessThan(0.4);
  });

  test("without a name the named members are not eligible at all", () => {
    for (const slot of SLOTS) {
      const picks = new Set(pickAcross(200, { slot, hasName: false }));
      expect([...picks].filter((key) => key.includes("_named_"))).toEqual([]);
    }
  });

  test("the slot boundaries are unchanged", () => {
    expect(greetingSlotForHour(5)).toBe("early");
    expect(greetingSlotForHour(8)).toBe("early");
    expect(greetingSlotForHour(9)).toBe("day");
    expect(greetingSlotForHour(17)).toBe("day");
    expect(greetingSlotForHour(18)).toBe("evening");
    expect(greetingSlotForHour(22)).toBe("evening");
    expect(greetingSlotForHour(23)).toBe("night");
    expect(greetingSlotForHour(4)).toBe("night");
  });

  test("the day key is the local calendar day, not UTC", () => {
    // 23:30 local on the 31st is already the next day in UTC for much of the
    // world, and the slot it pairs with is local too.
    expect(localDayKey(new Date(2026, 11, 31, 23, 30))).toBe("2026-12-31");
    expect(localDayKey(new Date(2026, 0, 5, 0, 15))).toBe("2026-01-05");
  });

  test("every pool key is translated in both languages", () => {
    const missing = (catalog: Record<string, string>) =>
      GREETING_KEYS.filter((key) => typeof catalog[key] !== "string");
    expect(missing(en.chat.greeting)).toEqual([]);
    expect(missing(es.chat.greeting)).toEqual([]);
    // And nothing is stranded in the catalogues that no pool can reach.
    expect(Object.keys(en.chat.greeting).sort()).toEqual([...GREETING_KEYS].sort());
    expect(Object.keys(es.chat.greeting).sort()).toEqual([...GREETING_KEYS].sort());
  });

  test("a named greeting interpolates and a plain one does not", () => {
    for (const catalog of [en.chat.greeting, es.chat.greeting]) {
      for (const [key, text] of Object.entries(catalog) as [string, string][]) {
        expect(text.includes("{{name}}")).toBe(key.includes("_named_"));
      }
    }
  });

  test("a closure line names the asset class that keeps trading", () => {
    // A bare "markets are closed" is wrong for the users on an asset that does
    // not close.
    const closure = (catalog: Record<string, string>) =>
      Object.entries(catalog).filter(([key]) => key.includes("closed_"));
    for (const [, text] of closure(en.chat.greeting)) {
      expect(text.toLowerCase()).toContain("crypto");
    }
    for (const [, text] of closure(es.chat.greeting)) {
      expect(text.toLowerCase()).toContain("cripto");
    }
    expect(closure(en.chat.greeting).length).toBeGreaterThanOrEqual(4);
  });

  test("an extended-hours line does not say the market is shut", () => {
    // pre_market and after_hours ARE trading windows, so a line that fires in
    // them may not call the day done or not yet begun.
    const shut = [/\bdone for the day\b/i, /\bclosed\b/i, /\bshut\b/i, /cerrad/i, /no opera/i];
    for (const catalog of [en.chat.greeting, es.chat.greeting]) {
      for (const key of ["session_pre_market_a", "session_after_hours_a"]) {
        const text = catalog[key] as string;
        for (const pattern of shut) {
          expect({ key, text, shut: pattern.test(text) }).toEqual({
            key,
            text,
            shut: false,
          });
        }
      }
    }
  });

  test("no session line claims a fact the endpoint does not resolve", () => {
    // The session comes from the US equity calendar. Crypto never closing is a
    // property of the asset, but FX closes most of the weekend and a holiday
    // weekend is not always three days, so neither may be asserted.
    const forbidden = [
      /currenc/i,
      /\bdivisa/i,
      /\bforex\b/i,
      /\bfx\b/i,
      /\bmonday\b/i,
      /\blunes\b/i,
    ];
    for (const catalog of [en.chat.greeting, es.chat.greeting]) {
      for (const [key, text] of Object.entries(catalog) as [string, string][]) {
        if (!key.startsWith("session_")) continue;
        for (const pattern of forbidden) {
          expect({ key, text, pattern: String(pattern) }).toEqual({
            key,
            text,
            pattern: String(pattern),
          });
          expect(pattern.test(text)).toBe(false);
        }
      }
    }
  });

  test("no greeting uses an em dash", () => {
    for (const catalog of [en.chat.greeting, es.chat.greeting]) {
      for (const text of Object.values(catalog) as string[]) {
        expect(text).not.toContain("—");
      }
    }
  });
});
