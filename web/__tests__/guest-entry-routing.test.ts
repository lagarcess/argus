import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { resolveLandingEntrySurface } from "../lib/landing-entry";

const root = join(import.meta.dir, "..");

describe("landing entry routing", () => {
  test("resolves the existing session before default-on guest entry", () => {
    expect(
      resolveLandingEntrySurface({
        authMode: "intro",
        guestEntryAvailable: true,
        isCheckingSession: true,
      }),
    ).toBe("loading");
  });

  test("keeps explicit request, login, and signup states on the auth surface", () => {
    for (const authMode of ["request", "login", "signup"] as const) {
      expect(
        resolveLandingEntrySurface({
          authMode,
          guestEntryAvailable: true,
          isCheckingSession: false,
        }),
      ).toBe("auth");
    }
  });

  test("uses guest entry only after an unauthenticated intro request resolves", () => {
    expect(
      resolveLandingEntrySurface({
        authMode: "intro",
        guestEntryAvailable: true,
        isCheckingSession: false,
      }),
    ).toBe("guest");
    expect(
      resolveLandingEntrySurface({
        authMode: "intro",
        guestEntryAvailable: false,
        isCheckingSession: false,
      }),
    ).toBe("auth");
  });

  test("lets a configured guest render chat while preserving auth-first rollback", () => {
    const chatPage = readFileSync(join(root, "app/chat/page.tsx"), "utf-8");
    const guardStart = chatPage.indexOf("if (error || !data.user) {");
    const guardEnd = chatPage.indexOf("\n  }\n\n  return", guardStart);
    const unauthenticatedGuard = chatPage.slice(guardStart, guardEnd);

    expect(guardStart).toBeGreaterThan(-1);
    expect(guardEnd).toBeGreaterThan(guardStart);
    expect(chatPage).toContain("guestCaptchaConfigured");
    expect(unauthenticatedGuard).toContain("guestAccessEnabled");
    expect(unauthenticatedGuard).toContain("guestCaptchaConfigured");
    expect(unauthenticatedGuard).not.toContain('redirect("/")');
    expect(unauthenticatedGuard).toContain('redirect("/?auth=login")');
    expect(chatPage).toContain("<ChatInterface />");
  });
});
