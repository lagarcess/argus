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
  let callbacks:
    | {
        callback: (token: string) => void;
        "error-callback": () => boolean;
        "expired-callback": () => void;
      }
    | undefined;

  const shell = {
    container: {} as HTMLElement,
    destroy() {
      destroyCalls += 1;
    },
  };
  const turnstile = {
    render(
      _container: HTMLElement,
      options: {
        callback: (token: string) => void;
        "error-callback": () => boolean;
        "expired-callback": () => void;
      },
    ) {
      callbacks = options;
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
    });

    setTimeout(() => harness.callbacks?.callback("verified-token"), 1);

    await expect(pending).resolves.toBe("verified-token");
    expect(harness.removeCalls).toBe(1);
    expect(harness.destroyCalls).toBe(1);
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
