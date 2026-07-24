import { describe, expect, test } from "bun:test";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { createGuestSessionBootstrapper } from "../lib/guest-session";

const root = join(import.meta.dir, "..");

describe("guest session entry contract", () => {
  test("keeps the auth landing as rollback and makes guest entry dynamic", () => {
    const page = readFileSync(join(root, "app/page.tsx"), "utf-8");
    const landingPath = join(root, "components/auth/AuthLanding.tsx");
    const guestEntryPath = join(root, "components/guest/GuestEntry.tsx");

    expect(existsSync(landingPath)).toBe(true);
    expect(existsSync(guestEntryPath)).toBe(true);
    expect(page).toContain('export const dynamic = "force-dynamic"');
    expect(page).toContain("<AuthLanding");
    expect(page).toContain("<GuestEntry");
    expect(page).toContain("NEXT_PUBLIC_GUEST_ACCESS_ENABLED");
  });

  test("owns one idempotent bootstrap and fails closed without a production captcha", () => {
    const sessionPath = join(root, "lib/guest-session.ts");
    expect(existsSync(sessionPath)).toBe(true);
    if (!existsSync(sessionPath)) return;

    const session = readFileSync(sessionPath, "utf-8");
    expect(session).toContain("createGuestSessionBootstrapper");
    expect(session).toContain("production");
    expect(session).toContain("captcha");
    expect(session).not.toContain("signInAnonymously");
    expect(session).not.toContain("service_role");
  });

  test("coalesces concurrent bootstrap calls and retries only after failure", async () => {
    let calls = 0;
    const bootstrapper = createGuestSessionBootstrapper(
      async (value: string) => {
        calls += 1;
        if (value === "fail") throw new Error("failed");
        return value;
      },
    );

    const first = bootstrapper.run("guest");
    const duplicate = bootstrapper.run("ignored");
    expect(await first).toBe("guest");
    expect(await duplicate).toBe("guest");
    expect(calls).toBe(1);

    bootstrapper.reset();
    await expect(bootstrapper.run("fail")).rejects.toThrow("failed");
    expect(await bootstrapper.run("recovered")).toBe("recovered");
    expect(calls).toBe(3);
  });

  test("uses the existing server guest endpoint and persists the provider session", () => {
    const api = readFileSync(join(root, "lib/argus-api.ts"), "utf-8");

    expect(api).toContain("export async function bootstrapGuest");
    expect(api).toContain('"/auth/guest"');
    expect(api).toContain("persistBrowserSession(response)");
  });

  test("guest onboarding depends on verified account kind and never patches profile truth", () => {
    const gate = readFileSync(
      join(root, "components/onboarding/OnboardingGate.tsx"),
      "utf-8",
    );

    expect(gate).toContain('me.account_kind === "guest"');
    expect(gate).toContain("setStep(\"done\")");
    expect(gate).not.toMatch(
      /me\.account_kind === "guest"[\s\S]{0,500}patchMe\(\{[\s\S]{0,300}primary_goal/,
    );
  });
});
