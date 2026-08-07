import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  allowanceMeterTone,
  classifyAllowance,
  formatAllowancePeriodEnd,
  showsHourlyWindow,
  type UsageAllowance,
} from "@/lib/usage-allowance";

const root = join(import.meta.dir, "..");

function readLocale(locale: "en" | "es-419") {
  return JSON.parse(
    readFileSync(join(root, "public/locales", locale, "common.json"), "utf-8"),
  );
}

describe("private-alpha usage allowance", () => {
  test("colors each allowance from its lowest normalized active window", () => {
    const allowanceAtThirtyPercent: UsageAllowance = {
      hour: {
        limit: 60,
        used: 0,
        remaining: 60,
        period_end: "2026-08-06T15:00:00Z",
      },
      day: {
        limit: 100,
        used: 70,
        remaining: 30,
        period_end: "2026-08-07T00:00:00Z",
      },
      guest_session: null,
      available_now: true,
      limiting_window: "day",
    };
    const allowanceBelowThirtyPercent: UsageAllowance = {
      ...allowanceAtThirtyPercent,
      day: {
        ...allowanceAtThirtyPercent.day,
        used: 71,
        remaining: 29,
      },
    };
    const allowanceAtTenPercent: UsageAllowance = {
      ...allowanceAtThirtyPercent,
      day: {
        ...allowanceAtThirtyPercent.day,
        used: 90,
        remaining: 10,
      },
    };
    const allowanceExhausted: UsageAllowance = {
      ...allowanceAtThirtyPercent,
      day: {
        ...allowanceAtThirtyPercent.day,
        used: 100,
        remaining: 0,
      },
      available_now: false,
    };
    const tighterHourlyWindow: UsageAllowance = {
      hour: {
        limit: 60,
        used: 54,
        remaining: 6,
        period_end: "2026-08-06T15:00:00Z",
      },
      day: {
        limit: 200,
        used: 100,
        remaining: 100,
        period_end: "2026-08-07T00:00:00Z",
      },
      guest_session: null,
      available_now: true,
      limiting_window: "hour",
    };
    const guestDailyWindow: UsageAllowance = {
      hour: null,
      day: {
        limit: 10,
        used: 8,
        remaining: 2,
        period_end: "2026-08-07T00:00:00Z",
      },
      guest_session: null,
      available_now: true,
      limiting_window: "day",
    };

    expect(allowanceMeterTone(allowanceAtThirtyPercent)).toBe("teal");
    expect(allowanceMeterTone(allowanceBelowThirtyPercent)).toBe("warning");
    expect(allowanceMeterTone(allowanceAtTenPercent)).toBe("danger");
    expect(allowanceMeterTone(allowanceExhausted)).toBe("danger");
    expect(allowanceMeterTone(tighterHourlyWindow)).toBe("danger");
    expect(allowanceMeterTone(guestDailyWindow)).toBe("warning");
  });

  test("classifies message and backtest gauges independently", () => {
    const messageAllowance: UsageAllowance = {
      hour: {
        limit: 60,
        used: 54,
        remaining: 6,
        period_end: "2026-08-06T15:00:00Z",
      },
      day: {
        limit: 200,
        used: 40,
        remaining: 160,
        period_end: "2026-08-07T00:00:00Z",
      },
      guest_session: null,
      available_now: true,
      limiting_window: "hour",
    };
    const backtestAllowance: UsageAllowance = {
      hour: {
        limit: 10,
        used: 0,
        remaining: 10,
        period_end: "2026-08-06T15:00:00Z",
      },
      day: {
        limit: 50,
        used: 36,
        remaining: 14,
        period_end: "2026-08-07T00:00:00Z",
      },
      guest_session: null,
      available_now: true,
      limiting_window: "day",
    };

    expect(allowanceMeterTone(messageAllowance)).toBe("danger");
    expect(allowanceMeterTone(backtestAllowance)).toBe("warning");
  });

  test("classifies presentation state from backend-derived truth only", () => {
    expect(
      classifyAllowance({
        available_now: true,
        day: { used: 0, remaining: 50 },
      }),
    ).toBe("zero");
    expect(
      classifyAllowance({
        available_now: true,
        day: { used: 3, remaining: 47 },
      }),
    ).toBe("active");
    expect(
      classifyAllowance({
        available_now: false,
        day: { used: 3, remaining: 47 },
      }),
    ).toBe("hourly_limited");
    expect(
      classifyAllowance({
        available_now: false,
        day: { used: 50, remaining: 0 },
      }),
    ).toBe("exhausted");
  });

  test("reveals the hourly window only when the backend marks it limiting", () => {
    expect(showsHourlyWindow({ limiting_window: "hour" })).toBe(true);
    expect(showsHourlyWindow({ limiting_window: "day" })).toBe(false);
  });

  test("formats the exact backend period end in English and Spanish", () => {
    const periodEnd = "2026-07-17T00:00:00Z";

    expect(formatAllowancePeriodEnd(periodEnd, "en-US", "UTC")).toContain(
      "Jul 17, 2026",
    );
    expect(formatAllowancePeriodEnd(periodEnd, "es-419", "UTC")).toContain(
      "17 jul 2026",
    );
  });

  test("renders message and simulation truth without frontend quota logic", () => {
    const api = readFileSync(join(root, "lib/argus-api.ts"), "utf-8");
    const usageLib = readFileSync(
      join(root, "lib/usage-allowance.ts"),
      "utf-8",
    );
    const profileMenu = readFileSync(
      join(root, "components/sidebar/ProfileMenu.tsx"),
      "utf-8",
    );
    const modal = readFileSync(
      join(root, "components/settings/UsageModal.tsx"),
      "utf-8",
    );

    expect(api).toContain('apiFetch<UsageAllowanceResponse>("/me/usage")');
    expect(api).toContain("runActionIdempotencyKey(input)");
    expect(usageLib).toContain('input.type !== "run_backtest"');
    expect(usageLib).toContain("confirmation_id");
    expect(usageLib).toContain("backtests: UsageAllowance");
    expect(usageLib).toContain('limiting_window: "hour" | "day"');
    expect(profileMenu).toContain('openModal("usage")');
    expect(profileMenu).toContain("<UsageModal");
    expect(modal).toContain("getUsageAllowances");
    expect(modal).toContain("usage.allowances.messages");
    expect(modal).toContain("usage.allowances.backtests");
    expect(modal).toContain("simulation_rule");
    expect(modal).toContain("showsHourlyWindow");
    expect(modal).not.toContain("Retry-After");
    expect(modal).not.toMatch(/limit:\s*\d/);
    expect(modal).not.toContain("setHours");
    expect(modal).not.toContain("Date.now() +");
  });

  test("wraps keyboard focus inside the Usage dialog", async () => {
    let dialogFocus: typeof import("@/lib/dialog-focus") | undefined;
    try {
      dialogFocus = await import("@/lib/dialog-focus");
    } catch {
      dialogFocus = undefined;
    }
    expect(dialogFocus).toBeDefined();
    if (!dialogFocus) return;

    const first = { id: "first" };
    const middle = { id: "middle" };
    const last = { id: "last" };
    const focusable = [first, middle, last];

    expect(dialogFocus.dialogTabTarget(focusable, last, false)).toBe(first);
    expect(dialogFocus.dialogTabTarget(focusable, first, true)).toBe(last);
    expect(
      dialogFocus.dialogTabTarget(focusable, { id: "outside" }, false),
    ).toBe(first);
    expect(dialogFocus.dialogTabTarget(focusable, middle, false)).toBeNull();

    const modal = readFileSync(
      join(root, "components/settings/UsageModal.tsx"),
      "utf-8",
    );
    // Tab containment belongs to the shared hook now. Running a private copy
    // beside it moved focus twice per press and skipped a control each time.
    expect(modal).not.toContain("dialogTabTarget");
    expect(modal).toContain("useModalSurface");
    expect(modal).toContain('event.key !== "Escape"');
    // The opener can be gone by the time this closes, so the fallback is
    // handed to the hook rather than managed here.
    expect(modal).toContain("returnFocusRef,");
  });

  test("uses flat styling and mobile-sized Usage controls", () => {
    const profileMenu = readFileSync(
      join(root, "components/sidebar/ProfileMenu.tsx"),
      "utf-8",
    );
    const modal = readFileSync(
      join(root, "components/settings/UsageModal.tsx"),
      "utf-8",
    );
    const usageButton = profileMenu.slice(
      profileMenu.indexOf('onClick={() => openModal("usage")}'),
      profileMenu.indexOf('onClick={() => openModal("usage")}') + 350,
    );

    expect(modal).not.toContain("shadow-sm");
    expect(modal).toContain("min-h-11 min-w-11");
    expect(modal.match(/min-h-11/g)?.length).toBeGreaterThanOrEqual(2);
    expect(usageButton).toContain("min-h-11");
  });

  test("localizes remaining-primary allowance truth in both languages", () => {
    const en = readLocale("en").settings.data.usage_panel;
    const es = readLocale("es-419").settings.data.usage_panel;

    expect(en.messages).toBe("Messages");
    expect(en.simulations).toBe("Simulations");
    expect(en.left_today).toContain("{{count}}");
    expect(en.hourly_available).toContain("{{count}}");
    expect(en.what_counts).toBe("What counts?");
    expect(en.message_rule).toBe(
      "Messages count when Argus completes a response. Failed or interrupted responses don’t count.",
    );
    expect(en.simulation_rule).toBe(
      "New simulations count once. Retrying the same simulation doesn’t count again.",
    );
    expect(en.description).toBeUndefined();
    expect(en.no_usage).toBeUndefined();
    expect(en.remaining).toBeUndefined();
    expect(es.messages).toBe("Mensajes");
    expect(es.simulations).toBe("Simulaciones");
    expect(es.left_today).toContain("{{count}}");
    expect(es.hourly_available).toContain("{{count}}");
    expect(es.what_counts.length).toBeGreaterThan(0);
    expect(es.message_rule).toBe(
      "Los mensajes cuentan cuando Argus completa una respuesta. Las respuestas fallidas o interrumpidas no cuentan.",
    );
    expect(es.simulation_rule).toBe(
      "Las simulaciones nuevas cuentan una vez. Reintentar la misma simulación no vuelve a contar.",
    );
    expect(es.description).toBeUndefined();
    expect(es.no_usage).toBeUndefined();
    expect(es.remaining).toBeUndefined();

    for (const catalog of [en, es]) {
      for (const value of Object.values(catalog)) {
        expect(String(value)).not.toContain("private-alpha");
        expect(String(value)).not.toContain("alfa privada");
        expect(String(value)).not.toContain("API");
      }
    }

    for (const key of Object.keys(en)) {
      expect(es[key]).toBeDefined();
    }
    for (const key of Object.keys(es)) {
      expect(en[key]).toBeDefined();
    }
  });

  test("presents a flat quiet gauge with one What counts disclosure", () => {
    const modal = readFileSync(
      join(root, "components/settings/UsageModal.tsx"),
      "utf-8",
    );

    expect(modal).toContain("left_today");
    expect(modal).toContain("day.remaining");
    expect(modal).not.toContain("usage_panel.description");
    expect(modal).not.toContain("rounded-2xl border");
    expect(modal).not.toContain("MessageSquareText");
    expect(modal).not.toContain("LineChart");
    expect(modal).not.toContain("no_usage");
    expect(modal).not.toContain("usage_panel.remaining");
    expect(modal.match(/what_counts/g)?.length).toBeGreaterThanOrEqual(1);
    expect(modal.match(/aria-expanded/g)?.length).toBe(1);
    expect(modal).toContain("message_rule");
    expect(modal).toContain("simulation_rule");
    expect(modal).toContain("classifyAllowance");
  });
});
