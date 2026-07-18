import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  classifyAllowance,
  formatAllowancePeriodEnd,
} from "@/lib/usage-allowance";

const root = join(import.meta.dir, "..");

function readLocale(locale: "en" | "es-419") {
  return JSON.parse(
    readFileSync(join(root, "public/locales", locale, "common.json"), "utf-8"),
  );
}

describe("private-alpha usage allowance", () => {
  test("classifies zero, active, and exhausted backend states", () => {
    expect(classifyAllowance({ used: 0, remaining: 50 })).toBe("zero");
    expect(classifyAllowance({ used: 3, remaining: 47 })).toBe("active");
    expect(classifyAllowance({ used: 50, remaining: 0 })).toBe("exhausted");
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

  test("shows message and durable-admission simulation truth", () => {
    const api = readFileSync(join(root, "lib/argus-api.ts"), "utf-8");
    const profileMenu = readFileSync(
      join(root, "components/sidebar/ProfileMenu.tsx"),
      "utf-8",
    );
    const modal = readFileSync(
      join(root, "components/settings/UsageModal.tsx"),
      "utf-8",
    );

    expect(api).toContain('apiFetch<UsageAllowanceResponse>("/me/usage")');
    // #247 x #230: simulation counts became truthful once the atomic
    // admission operation owned the one-unit charge, so both surface now.
    expect(api).toContain("backtests: UsageAllowance");
    expect(profileMenu).toContain('openModal("usage")');
    expect(profileMenu).toContain("<UsageModal");
    expect(modal).toContain("getUsageAllowances");
    expect(modal).toContain("allowance.period_end");
    expect(modal).toContain("usage.allowances.messages");
    expect(modal).toContain("usage.allowances.backtests");
    expect(modal).not.toContain("Retry-After");
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

  test("localizes the truthful simulation allowance in both languages", () => {
    const en = readLocale("en").settings.data.usage_panel;
    const es = readLocale("es-419").settings.data.usage_panel;

    expect(en.messages).toBe("Messages");
    expect(en.no_usage).toBe("No usage yet");
    expect(en.exhausted).toBe("Allowance used for this period");
    expect(en.description).toBe(
      "Your current message and simulation allowances.",
    );
    expect(en.backtests).toBe("Simulations");
    expect(en.backtest_rule).toContain("unique run is durably admitted");
    expect(en.backtest_rule).toContain("Replays and rejected requests count nothing");
    expect(es.messages).toBe("Mensajes");
    expect(es.no_usage).toBe("Aún no hay uso");
    expect(es.exhausted).toBe("Cupo agotado para este periodo");
    expect(es.description).toBe(
      "Tus límites actuales de mensajes y simulaciones.",
    );
    expect(es.backtests).toBe("Simulaciones");
    expect(es.backtest_rule).toContain("se admite de forma durable");
  });
});
