import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import * as landingEntry from "../lib/landing-entry";

const root = join(import.meta.dir, "..");
const { resolveLandingEntrySurface } = landingEntry;

type ResolveChatEntrySurface = (input: {
  hasEstablishedUser: boolean;
  guestAccessEnabled: boolean;
  guestCaptchaConfigured: boolean;
}) => "chat" | "auth";

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

  test("requires both guest gates to render unauthenticated chat", () => {
    const resolveChatEntrySurface = (
      landingEntry as typeof landingEntry & {
        resolveChatEntrySurface?: ResolveChatEntrySurface;
      }
    ).resolveChatEntrySurface;

    expect(resolveChatEntrySurface).toBeFunction();
    if (!resolveChatEntrySurface) return;

    expect(
      resolveChatEntrySurface({
        hasEstablishedUser: false,
        guestAccessEnabled: true,
        guestCaptchaConfigured: true,
      }),
    ).toBe("chat");
    for (const rollback of [
      { guestAccessEnabled: false, guestCaptchaConfigured: true },
      { guestAccessEnabled: true, guestCaptchaConfigured: false },
      { guestAccessEnabled: false, guestCaptchaConfigured: false },
    ]) {
      expect(
        resolveChatEntrySurface({
          hasEstablishedUser: false,
          ...rollback,
        }),
      ).toBe("auth");
    }
    expect(
      resolveChatEntrySurface({
        hasEstablishedUser: true,
        guestAccessEnabled: false,
        guestCaptchaConfigured: false,
      }),
    ).toBe("chat");
  });

  test("uses the shared chat-entry decision without bouncing guests to root", () => {
    const chatPage = readFileSync(join(root, "app/chat/page.tsx"), "utf-8");

    expect(chatPage).toContain("resolveChatEntrySurface");
    expect(chatPage).not.toContain('redirect("/")');
    expect(chatPage).toContain('redirect("/?auth=login")');
    expect(chatPage).toContain("<ChatInterface />");
  });
});
