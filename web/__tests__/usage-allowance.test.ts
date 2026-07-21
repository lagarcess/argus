import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  classifyAllowance,
  formatAllowancePeriodEnd,
  showsHourlyWindow,
} from "@/lib/usage-allowance";

const root = join(import.meta.dir, "..");

function readLocale(locale: "en" | "es-419") {
  return JSON.parse(
    readFileSync(join(root, "public/locales", locale, "common.json"), "utf-8"),
  );
}

describe("private-alpha usage allowance", () => {
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
    // Run actions must reuse the confirmation identity as the
    // Idempotency-Key so retries and reconnects replay the one durable
    // admission instead of opening a second reservation.
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
    // The frontend renders backend truth; it must not restate quota limits
    // or recompute reset times locally.
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
    expect(modal).toContain("dialogTabTarget");
    expect(modal).toContain('event.key === "Escape"');
    expect(modal).toContain("returnFocusRef");
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
    // The quiet gauge leads with what remains; the subtitle, used-count
    // badges, and the zero-usage badge are retired.
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

    // Guidance stays plain product language: no program branding and no
    // provider/API plumbing.
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

    // Remaining capacity is the primary value per section; the header
    // carries no subtitle.
    expect(modal).toContain("left_today");
    expect(modal).toContain("day.remaining");
    expect(modal).not.toContain("usage_panel.description");
    // One flat surface: no per-allowance bordered card tiles and no
    // decorative icon tiles.
    expect(modal).not.toContain("rounded-2xl border");
    expect(modal).not.toContain("MessageSquareText");
    expect(modal).not.toContain("LineChart");
    // No usage-state badges; healthy and zero states stay neutral.
    expect(modal).not.toContain("no_usage");
    expect(modal).not.toContain("usage_panel.remaining");
    // Exactly one progressive disclosure owns both counting rules.
    expect(modal.match(/what_counts/g)?.length).toBeGreaterThanOrEqual(1);
    expect(modal.match(/aria-expanded/g)?.length).toBe(1);
    expect(modal).toContain("message_rule");
    expect(modal).toContain("simulation_rule");
    // Warning styling exists only behind genuine exhaustion checks.
    expect(modal).toContain("classifyAllowance");
  });
});
