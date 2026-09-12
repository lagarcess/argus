import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  GREETING_KEYS,
  greetingAudience,
  greetingRingFor,
  greetingSlotForHour,
  localDayKey,
  pickGreetingKey,
  type DemonstratedInterest,
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
const CATALOGS: [string, Record<string, string>][] = [
  ["en", en.chat.greeting],
  ["es-419", es.chat.greeting],
];

const SLOTS: GreetingSlot[] = ["early", "day", "evening", "night"];
const ALL_SESSIONS: (MarketSessionPhase | null)[] = [
  null,
  "closed_weekend",
  "closed_holiday",
  "pre_market",
  "after_hours",
  "open",
  "closed",
];

/* The spec, per slot: lines everyone hears, and lines only a market fan hears.
 * Named lines are eligible only with a stated name. */
const EVERYONE: Record<GreetingSlot, { plain: string[]; named: string[] }> = {
  early: { plain: ["early_a", "early_c"], named: ["early_named_a"] },
  day: { plain: ["day_d", "day_f"], named: ["day_named_b"] },
  evening: { plain: ["evening_a", "evening_d"], named: ["evening_named_a"] },
  night: { plain: ["night_b", "day_d"], named: ["night_named_a"] },
};
const MARKET_FANS: Record<GreetingSlot, { plain: string[]; named: string[] }> = {
  early: { plain: ["early_b"], named: [] },
  day: { plain: ["day_a", "day_c", "day_e"], named: ["day_named_a"] },
  evening: { plain: ["evening_b"], named: [] },
  night: { plain: ["night_c"], named: [] },
};
const SESSION_LINE: Partial<Record<MarketSessionPhase, string>> = {
  closed_weekend: "session_closed_weekend_a",
  closed_holiday: "session_closed_holiday_a",
  pre_market: "session_pre_market_a",
};

const NAME = "Johana";
const PEOPLE: {
  who: string;
  isGuest: boolean;
  interest: DemonstratedInterest | null;
  fan: boolean;
}[] = [
  { who: "a guest", isGuest: true, interest: { markets: false }, fan: false },
  // A guest's own runs do not earn market flavor; guests are always neutral.
  { who: "a guest with runs", isGuest: true, interest: { markets: true }, fan: false },
  {
    who: "a registered person with no history",
    isGuest: false,
    interest: { markets: false },
    fan: false,
  },
  {
    who: "a registered person whose history is unreadable",
    isGuest: false,
    interest: null,
    fan: false,
  },
  { who: "a market fan", isGuest: false, interest: { markets: true }, fan: true },
];
const DAYS: [string, MarketSessionPhase][] = [
  ["a weekend", "closed_weekend"],
  ["a holiday", "closed_holiday"],
  ["an open-market weekday", "open"],
];

function expectedPool(
  slot: GreetingSlot,
  session: MarketSessionPhase,
  { hasName, fan }: { hasName: boolean; fan: boolean },
): string[] {
  const lines = [...EVERYONE[slot].plain];
  if (hasName) lines.push(...EVERYONE[slot].named);
  if (fan) {
    lines.push(...MARKET_FANS[slot].plain);
    if (hasName) lines.push(...MARKET_FANS[slot].named);
    const sessionLine = SESSION_LINE[session];
    if (sessionLine) lines.push(sessionLine);
  }
  return lines.sort();
}

function pickAcross(
  days: number,
  options: {
    slot?: GreetingSlot;
    session?: MarketSessionPhase | null;
    hasName?: boolean;
    marketFan?: boolean;
  } = {},
): string[] {
  const picks: string[] = [];
  for (let day = 0; day < days; day += 1) {
    picks.push(
      pickGreetingKey({
        slot: options.slot ?? "day",
        session: options.session ?? null,
        hasName: options.hasName ?? false,
        marketFan: options.marketFan ?? true,
        at: new Date(2026, 0, 1 + day, 12, 0, 0),
      }),
    );
  }
  return picks;
}

function render(text: string, name: string): string {
  return text.replaceAll("{{name}}", name);
}

describe("who hears which greeting", () => {
  for (const person of PEOPLE) {
    for (const [day, session] of DAYS) {
      for (const preferredName of [null, NAME]) {
        const label = `${person.who} on ${day}, ${preferredName ? "with" : "without"} a name`;
        test(label, () => {
          const audience = greetingAudience({
            isGuest: person.isGuest,
            preferredName,
            interest: person.interest,
          });
          const hasName = audience.name.length > 0;
          expect(audience.marketFan).toBe(person.fan);
          // A guest has no profile, so a name never reaches the guest pool.
          expect(hasName).toBe(!person.isGuest && preferredName !== null);

          for (const slot of SLOTS) {
            const options = {
              slot,
              session,
              hasName,
              marketFan: audience.marketFan,
            };
            const pool = expectedPool(slot, session, { hasName, fan: person.fan });
            expect({ slot, pool: [...greetingRingFor(options)].sort() }).toEqual({
              slot,
              pool,
            });

            for (const [language, catalog] of CATALOGS) {
              for (const key of pool) {
                const line = render(catalog[key], audience.name);
                expect({ language, key, line: typeof catalog[key] }).toEqual({
                  language,
                  key,
                  line: "string",
                });
                expect(line.includes("{{")).toBe(false);
                if (key.includes("_named_")) expect(line).toContain(NAME);
              }
            }
          }
        });
      }
    }
  }

  test("the neutral pools, spelled out", () => {
    const neutral = { session: "closed_weekend" as const, marketFan: false };
    expect([...greetingRingFor({ ...neutral, slot: "day", hasName: false })].sort())
      .toEqual(["day_d", "day_f"]);
    expect([...greetingRingFor({ ...neutral, slot: "night", hasName: true })].sort())
      .toEqual(["day_d", "night_b", "night_named_a"]);
  });

  test("a guest's greeting reads neither the session nor interest", () => {
    // Which is why a guest never asks the backend for either.
    for (const slot of SLOTS) {
      for (const preferredName of [null, NAME]) {
        const rings = new Set<string>();
        for (const session of ALL_SESSIONS) {
          for (const interest of [null, { markets: false }, { markets: true }]) {
            const audience = greetingAudience({ isGuest: true, preferredName, interest });
            const ring = greetingRingFor({
              slot,
              session,
              hasName: audience.name.length > 0,
              marketFan: audience.marketFan,
            });
            rings.add(JSON.stringify(ring));
          }
        }
        expect({ slot, preferredName, rings: rings.size }).toEqual({
          slot,
          preferredName,
          rings: 1,
        });
      }
    }
  });

  test("a market fan's weekend day pool, spelled out", () => {
    expect(
      [
        ...greetingRingFor({
          slot: "day",
          session: "closed_weekend",
          hasName: true,
          marketFan: true,
        }),
      ].sort(),
    ).toEqual([
      "day_a",
      "day_c",
      "day_d",
      "day_e",
      "day_f",
      "day_named_a",
      "day_named_b",
      "session_closed_weekend_a",
    ]);
  });

  test("the weekend line reads the same in both languages", () => {
    expect(en.chat.greeting.session_closed_weekend_a).toBe(
      "Stocks are closed for the weekend. Crypto is still trading.",
    );
    expect(es.chat.greeting.session_closed_weekend_a).toBe(
      "La bolsa está cerrada por el fin de semana. Las criptos siguen operando.",
    );
  });

  test("retired lines are gone from both languages", () => {
    const retired = [
      "day_b",
      "evening_c",
      "night_a",
      "session_closed_weekend_b",
      "session_closed_holiday_b",
      "session_after_hours_a",
    ];
    for (const [, catalog] of CATALOGS) {
      expect(retired.filter((key) => key in catalog)).toEqual([]);
    }
    expect(retired.filter((key) => GREETING_KEYS.includes(key))).toEqual([]);
  });
});

describe("greeting pool", () => {
  test("a greeting holds all day and does not move on refresh", () => {
    const hours = [9, 12, 15, 17];
    for (const marketFan of [false, true]) {
      const picks = hours.map((hour) =>
        pickGreetingKey({
          slot: "day",
          session: null,
          hasName: false,
          marketFan,
          at: new Date(2026, 4, 14, hour, 37, 12),
        }),
      );
      expect(new Set(picks).size).toBe(1);
    }
  });

  test("tomorrow is a different sentence from today", () => {
    // Seeding from the date is only worth it if consecutive days differ.
    for (const slot of SLOTS) {
      for (const session of ALL_SESSIONS) {
        for (const hasName of [false, true]) {
          for (const marketFan of [false, true]) {
            const picks = pickAcross(400, { slot, session, hasName, marketFan });
            const repeats = picks.filter(
              (key, index) => index > 0 && key === picks[index - 1],
            );
            expect(repeats).toEqual([]);
          }
        }
      }
    }
  });

  test("no pool puts a line next to itself, including around the wrap", () => {
    // The walk is one step a day, so the no-repeat rule is a property of the
    // arrangement.
    for (const slot of SLOTS) {
      for (const session of ALL_SESSIONS) {
        for (const hasName of [false, true]) {
          for (const marketFan of [false, true]) {
            const ring = greetingRingFor({ slot, session, hasName, marketFan });
            expect(ring.length).toBeGreaterThan(1);
            const adjacent = ring.filter(
              (key, index) => key === ring[(index + 1) % ring.length],
            );
            expect({ slot, session, hasName, marketFan, adjacent }).toEqual({
              slot,
              session,
              hasName,
              marketFan,
              adjacent: [],
            });
          }
        }
      }
    }
  });

  test("every line in a pool gets its turn, and no line more than once", () => {
    // A hash-modulo pick leaves lines unseen for weeks. A ring does not.
    for (const marketFan of [false, true]) {
      const options = {
        slot: "day" as const,
        session: "closed_weekend" as const,
        hasName: false,
        marketFan,
      };
      const ring = greetingRingFor(options);
      expect(new Set(ring).size).toBe(ring.length);
      expect(new Set(pickAcross(ring.length, options)).size).toBe(ring.length);
    }
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

  test("an open market, after hours and an overnight lull say nothing about the market", () => {
    // Open is the default state of a weekday, and overnight on a trading day
    // is not a weekend, so the weekend sentence would be false.
    for (const session of ["open", "after_hours", "closed"] as MarketSessionPhase[]) {
      const picks = new Set(pickAcross(200, { session }));
      expect([...picks].filter((key) => key.startsWith("session_"))).toEqual([]);
    }
  });

  test("generic lines stay in play while a session is active", () => {
    // Session lines widen the pool; they never take it over.
    const picks = new Set(pickAcross(200, { session: "closed_weekend" }));
    expect([...picks].some((key) => !key.startsWith("session_"))).toBe(true);
  });

  test("a name appears in some greetings and not most of them", () => {
    // Every greeting using someone's name gets grating in about three days.
    for (const marketFan of [false, true]) {
      const picks = pickAcross(400, { hasName: true, marketFan });
      const named = picks.filter((key) => key.includes("_named_")).length;
      expect(named).toBeGreaterThan(0);
      expect(named / picks.length).toBeLessThan(0.4);
    }
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
    expect(new Set(GREETING_KEYS).size).toBe(GREETING_KEYS.length);
    for (const [, catalog] of CATALOGS) {
      expect(missing(catalog)).toEqual([]);
      // And nothing is stranded in the catalogues that no pool can reach.
      expect(Object.keys(catalog).sort()).toEqual([...GREETING_KEYS].sort());
    }
  });

  test("a named greeting interpolates and a plain one does not", () => {
    for (const [, catalog] of CATALOGS) {
      for (const [key, text] of Object.entries(catalog)) {
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
    expect(closure(en.chat.greeting).length).toBe(2);
  });

  test("an extended-hours line does not say the market is shut", () => {
    // pre_market IS a trading window, so a line that fires in it may not call
    // the day not yet begun.
    const shut = [/\bdone for the day\b/i, /\bclosed\b/i, /\bshut\b/i, /cerrad/i, /no opera/i];
    for (const [, catalog] of CATALOGS) {
      const text = catalog.session_pre_market_a;
      for (const pattern of shut) {
        expect({ text, shut: pattern.test(text) }).toEqual({ text, shut: false });
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
    for (const [, catalog] of CATALOGS) {
      for (const [key, text] of Object.entries(catalog)) {
        if (!key.startsWith("session_")) continue;
        for (const pattern of forbidden) {
          expect({ key, pattern: String(pattern), hit: pattern.test(text) }).toEqual({
            key,
            pattern: String(pattern),
            hit: false,
          });
        }
      }
    }
  });

  test("no greeting uses an em dash", () => {
    for (const [, catalog] of CATALOGS) {
      for (const text of Object.values(catalog)) {
        expect(text).not.toContain("—");
      }
    }
  });
});
