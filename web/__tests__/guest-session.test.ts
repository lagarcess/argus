import { describe, expect, test } from "bun:test";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import {
  createGuestSessionBootstrapper,
  guestCaptchaTokenForEnvironment,
} from "../lib/guest-session";
import { guestAccessEnabledFromEnv } from "../lib/private-alpha-flags";

const root = join(import.meta.dir, "..");

describe("guest session entry contract", () => {
  test("defaults Guest presentation on and keeps explicit false as a kill switch", () => {
    expect(guestAccessEnabledFromEnv(undefined)).toBe(true);
    expect(guestAccessEnabledFromEnv("true")).toBe(true);
    expect(guestAccessEnabledFromEnv("false")).toBe(false);
    expect(guestAccessEnabledFromEnv(" OFF ")).toBe(false);
    expect(guestAccessEnabledFromEnv("invalid")).toBe(false);
  });

  test("keeps the auth landing as rollback and makes guest entry dynamic", () => {
    const page = readFileSync(join(root, "app/page.tsx"), "utf-8");
    const guestEntryPath = join(root, "components/guest/GuestEntry.tsx");

    expect(existsSync(guestEntryPath)).toBe(true);
    expect(page).toContain("<GuestEntry");
    expect(page).toContain("guestAccessEnabled");
    expect(page).toContain("loginWithEmail");
    expect(page).toContain("signupWithEmail");
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

  test("allows an explicit production-QA CAPTCHA token only for loopback", () => {
    expect(
      guestCaptchaTokenForEnvironment({
        nodeEnv: "production",
        apiUrl: "http://localhost:8000/api/v1",
        localQaToken: "local-qa-proof",
      }),
    ).toBe("local-qa-proof");
    expect(
      guestCaptchaTokenForEnvironment({
        nodeEnv: "production",
        apiUrl: "https://api.argus.example/api/v1",
        localQaToken: "local-qa-proof",
      }),
    ).toBeNull();
  });

  test("keeps ordinary production closed and development deterministic", () => {
    expect(
      guestCaptchaTokenForEnvironment({
        nodeEnv: "production",
        apiUrl: "http://localhost:8000/api/v1",
        localQaToken: "",
      }),
    ).toBeNull();
    expect(
      guestCaptchaTokenForEnvironment({
        nodeEnv: "development",
        apiUrl: "http://localhost:8000/api/v1",
        localQaToken: "",
      }),
    ).toBe("argus-local-browser-qa");
  });

  test("uses the existing server guest endpoint and persists the provider session", () => {
    const api = readFileSync(join(root, "lib/argus-api.ts"), "utf-8");
    const session = readFileSync(join(root, "lib/guest-session.ts"), "utf-8");
    const entry = readFileSync(
      join(root, "components/guest/GuestEntry.tsx"),
      "utf-8",
    );

    expect(session).toContain("export async function bootstrapGuest");
    expect(session).toContain('"/auth/guest"');
    expect(session).toContain("persistBrowserSession(response)");
    expect(api).toContain("if (error)");
    expect(entry).toContain('router.replace("/chat")');
    expect(entry).not.toContain("router.refresh()");
  });

});
