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

  test("wires the authenticated API response directly into the Usage modal", () => {
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
    expect(profileMenu).toContain('openModal("usage")');
    expect(profileMenu).toContain("<UsageModal");
    expect(modal).toContain("getUsageAllowances");
    expect(modal).toContain("allowance.period_end");
    expect(modal).not.toContain("Retry-After");
  });

  test("localizes allowance labels and consumption rules", () => {
    const en = readLocale("en").settings.data.usage_panel;
    const es = readLocale("es-419").settings.data.usage_panel;

    expect(en.messages).toBe("Messages");
    expect(en.simulations).toBe("Simulations");
    expect(en.no_usage).toBe("No usage yet");
    expect(en.exhausted).toBe("Allowance used for this period");
    expect(en.simulation_zero_rule).toContain("Replays");
    expect(es.messages).toBe("Mensajes");
    expect(es.simulations).toBe("Simulaciones");
    expect(es.no_usage).toBe("Aún no hay uso");
    expect(es.exhausted).toBe("Cupo agotado para este periodo");
    expect(es.simulation_zero_rule).toContain("repeticiones");
  });
});
