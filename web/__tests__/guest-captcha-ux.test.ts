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
});
