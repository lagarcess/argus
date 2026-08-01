import { describe, expect, test } from "bun:test";
import { resolveLandingEntrySurface } from "../lib/landing-entry";

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
});
