import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import * as guestCaptcha from "../lib/guest-captcha";

const root = join(import.meta.dir, "..");

type AcquireTurnstileChallenge = (input: {
  turnstile: ReturnType<typeof challengeHarness>["turnstile"];
  shell: ReturnType<typeof challengeHarness>["shell"];
  siteKey: string;
  timeoutMs: number;
  interactiveTimeoutMs: number;
  theme: "light" | "dark";
}) => Promise<string>;

function challengeUnderTest(): AcquireTurnstileChallenge {
  const acquire = (
    guestCaptcha as typeof guestCaptcha & {
      acquireTurnstileChallenge?: AcquireTurnstileChallenge;
    }
  ).acquireTurnstileChallenge;
  expect(typeof acquire).toBe("function");
  return acquire as AcquireTurnstileChallenge;
}

function challengeHarness() {
  let destroyCalls = 0;
  let removeCalls = 0;
  let revealCalls = 0;
  let renderedTheme: "auto" | "light" | "dark" | undefined;
  let callbacks:
    | {
        callback: (token: string) => void;
        "error-callback": () => boolean;
        "expired-callback": () => void;
        "before-interactive-callback": () => void;
      }
    | undefined;

  const shell = {
    container: {} as HTMLElement,
    destroy() {
      destroyCalls += 1;
    },
    reveal() {
      revealCalls += 1;
    },
  };
  const turnstile = {
    render(
      _container: HTMLElement,
      options: {
        theme: "auto" | "light" | "dark";
        callback: (token: string) => void;
        "error-callback": () => boolean;
        "expired-callback": () => void;
        "before-interactive-callback": () => void;
      },
    ) {
      callbacks = options;
      renderedTheme = options.theme;
      return "widget-1";
    },
    remove(widgetId: string) {
      expect(widgetId).toBe("widget-1");
      removeCalls += 1;
    },
  };

  return {
    shell,
    turnstile,
    get callbacks() {
      return callbacks;
    },
    get destroyCalls() {
      return destroyCalls;
    },
    get removeCalls() {
      return removeCalls;
    },
    get revealCalls() {
      return revealCalls;
    },
    get renderedTheme() {
      return renderedTheme;
    },
  };
}

describe("shared CAPTCHA acquisition UX", () => {
  test("times out a Turnstile widget that never settles and ignores a late callback", async () => {
    const harness = challengeHarness();
    const pending = challengeUnderTest()({
      turnstile: harness.turnstile,
      shell: harness.shell,
      siteKey: "test-site-key",
      timeoutMs: 5,
      interactiveTimeoutMs: 100,
      theme: "light",
    });

    const error = await pending.catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(Error);
    expect((error as Error & { code?: string }).code).toBe(
      "captcha_unavailable",
    );
    expect(harness.removeCalls).toBe(1);
    expect(harness.destroyCalls).toBe(1);

    harness.callbacks?.callback("too-late");
    expect(harness.removeCalls).toBe(1);
    expect(harness.destroyCalls).toBe(1);
  });

  test("allows an invisible check to resolve before the deadline", async () => {
    const harness = challengeHarness();
    const pending = challengeUnderTest()({
      turnstile: harness.turnstile,
      shell: harness.shell,
      siteKey: "test-site-key",
      timeoutMs: 100,
      interactiveTimeoutMs: 100,
      theme: "light",
    });

    setTimeout(() => harness.callbacks?.callback("verified-token"), 1);

    await expect(pending).resolves.toBe("verified-token");
    expect(harness.removeCalls).toBe(1);
    expect(harness.destroyCalls).toBe(1);
  });

  test("gives a revealed interactive challenge a fresh completion window", async () => {
    const harness = challengeHarness();
    const pending = challengeUnderTest()({
      turnstile: harness.turnstile,
      shell: harness.shell,
      siteKey: "test-site-key",
      timeoutMs: 10,
      interactiveTimeoutMs: 100,
      theme: "dark",
    });

    setTimeout(
      () => harness.callbacks?.["before-interactive-callback"]?.(),
      1,
    );
    setTimeout(() => harness.callbacks?.callback("interactive-token"), 30);

    await expect(pending).resolves.toBe("interactive-token");
    expect(harness.revealCalls).toBe(1);
    expect(harness.removeCalls).toBe(1);
    expect(harness.destroyCalls).toBe(1);
  });

  test("passes the page's resolved theme to Turnstile", async () => {
    const harness = challengeHarness();
    const pending = challengeUnderTest()({
      turnstile: harness.turnstile,
      shell: harness.shell,
      siteKey: "test-site-key",
      timeoutMs: 100,
      interactiveTimeoutMs: 100,
      theme: "dark",
    });

    harness.callbacks?.callback("verified-token");

    await expect(pending).resolves.toBe("verified-token");
    expect(harness.renderedTheme).toBe("dark");
  });

  test("ships the interactive verification label in English and Spanish", () => {
    const en = JSON.parse(
      readFileSync(join(root, "public/locales/en/common.json"), "utf-8"),
    );
    const es = JSON.parse(
      readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
    );

    expect(en.auth.captcha?.verifying).toBe("Verifying you’re not a bot…");
    expect(es.auth.captcha?.verifying).toBe(
      "Verificando que no eres un bot…",
    );
  });

  test("maps coded Turnstile failures to captcha_unavailable and other errors to generic", () => {
    const coded = Object.assign(new Error("Browser CAPTCHA could not be verified."), {
      code: "captcha_unavailable",
    });
    expect(guestCaptcha.isCaptchaUnavailableError(coded)).toBe(true);
    expect(guestCaptcha.guestEntryErrorKind(coded)).toBe("captcha_unavailable");
    expect(guestCaptcha.guestEntryErrorKind(new Error("network"))).toBe(
      "generic",
    );
    expect(guestCaptcha.guestEntryErrorKind()).toBe("generic");
    expect(guestCaptcha.guestEntryErrorKind("captcha_unavailable")).toBe(
      "generic",
    );
  });

  test("empty-chat guest entry localizes captcha_unavailable and omits a same-path retry", () => {
    const emptyChat = readFileSync(
      join(root, "components/chat/EmptyChatSurface.tsx"),
      "utf-8",
    );
    const experience = readFileSync(
      join(root, "components/guest/useGuestExperience.ts"),
      "utf-8",
    );
    const chat = readFileSync(
      join(root, "components/chat/ChatInterface.tsx"),
      "utf-8",
    );
    const en = JSON.parse(
      readFileSync(join(root, "public/locales/en/common.json"), "utf-8"),
    );
    const es = JSON.parse(
      readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8"),
    );

    expect(emptyChat).toContain("auth.errors.captcha_unavailable");
    expect(emptyChat).toContain("guest.entry.reload");
    expect(emptyChat).toContain("guest.shell.sign_in");
    expect(emptyChat).toContain("window.location.reload()");
    expect(emptyChat).toContain("onSignIn");
    expect(emptyChat).not.toContain("t(guestSubmissionError");
    expect(emptyChat).not.toContain("{guestSubmissionError}");

    const captchaBranch = emptyChat.slice(
      emptyChat.indexOf("CAPTCHA_UNAVAILABLE_CODE"),
    );
    const genericBranch = captchaBranch.slice(captchaBranch.indexOf(") : ("));
    expect(captchaBranch.indexOf("common.try_again")).toBeGreaterThan(
      captchaBranch.indexOf(") : ("),
    );
    expect(genericBranch).toContain("common.try_again");
    expect(genericBranch).toContain("onRetryGuestSubmission");

    expect(experience).toContain("onGuestBootstrapError(error)");
    expect(chat).toContain("guestEntryErrorKind(error)");
    expect(chat).toContain("guestSubmissionRetryRef.current = null");
    expect(chat).toContain("onSignIn={requestGuestSignIn}");

    expect(en.auth.errors.captcha_unavailable).toBe(
      "This browser didn’t pass the security check. Open Argus in a regular browser, or reload the page.",
    );
    expect(es.auth.errors.captcha_unavailable).toBe(
      "Este navegador no pasó la verificación de seguridad. Abre Argus en un navegador normal, o actualiza la página.",
    );
    expect(en.guest.entry.reload).toBe("Reload");
    expect(es.guest.entry.reload).toBe("Actualizar");
    expect(en.auth.errors.captcha_unavailable).not.toBe("captcha_unavailable");
    expect(es.auth.errors.captcha_unavailable).not.toBe("captcha_unavailable");
    expect(en.auth.errors.captcha_unavailable.toLowerCase()).not.toContain(
      "try again",
    );
  });
});
