import { expect, test, describe } from "bun:test";
import fs from "fs";
import path from "path";

describe("Spanish UI Smoke Harness", () => {
  const originalEnv = process.env.NEXT_PUBLIC_ENABLE_SPANISH;
  const webRoot = path.resolve(__dirname, "..");
  const esLocalePath = path.join(webRoot, "public/locales/es-419/common.json");
  const enLocalePath = path.join(webRoot, "public/locales/en/common.json");

  const requiredSmokeKeys = [
    "chat.input_placeholder",
    "chat.message_empty",
    "chat.send_message",
    "chat.disclaimer",
    "chat.backtest_job.queued_title",
    "chat.backtest_job.queued_status",
    "chat.backtest_job.running_title",
    "chat.backtest_job.running_status",
    "chat.backtest_job.succeeded_title",
    "chat.backtest_job.succeeded_status",
    "chat.backtest_job.failed_title",
    "chat.backtest_job.failed_status",
    "chat.backtest_job.expired_title",
    "chat.backtest_job.expired_status",
    "settings.title",
    "settings.profile.title",
    "settings.profile.delete_account",
    "settings.app.language",
    "settings.logout",
    "settings.search_language",
    "settings.no_languages",
    "settings.languages.en",
    "settings.languages.es-419",
    "onboarding.language.title",
    "onboarding.language.continue_in",
  ];

  function readLocale(localePath: string) {
    expect(fs.existsSync(localePath)).toBe(true);
    return JSON.parse(fs.readFileSync(localePath, "utf-8"));
  }

  function valueAtPath(source: unknown, keyPath: string): unknown {
    return keyPath.split(".").reduce<unknown>((current, segment) => {
      if (!current || typeof current !== "object") return undefined;
      return (current as Record<string, unknown>)[segment];
    }, source);
  }

  test("Spanish locale JSON exists and parses", () => {
    const json = readLocale(esLocalePath);
    expect(json).toBeDefined();
  });

  test("Spanish smoke keys exist for the private-alpha UI surface", () => {
    const en = readLocale(enLocalePath);
    const es = readLocale(esLocalePath);

    for (const key of requiredSmokeKeys) {
      expect(valueAtPath(en, key), `missing English key ${key}`).toBeString();
      expect(valueAtPath(es, key), `missing Spanish key ${key}`).toBeString();
      expect(String(valueAtPath(es, key)).trim(), `blank Spanish key ${key}`).not.toBe("");
    }
  });

  test("Source referencing verified keys", () => {
    // Basic checks to ensure source files still reference keys that exist in Spanish bundle
    const languageSource = fs.readFileSync(path.join(webRoot, "components/SettingsMenu.tsx"), "utf-8");
    expect(languageSource).toContain("settings.languages.");

    const chatSource = fs.readFileSync(path.join(webRoot, "components/chat/ChatInput.tsx"), "utf-8");
    expect(chatSource).toContain("chat.message_empty");

    const backtestSource = fs.readFileSync(path.join(webRoot, "lib/backtest-job-card-copy.ts"), "utf-8");
    expect(backtestSource).toContain("chat.backtest_job.queued_title");
  });

  test("Spanish feature flag enables es-419", () => {
    const probe = `
      import { ENABLED_LANGUAGE_CODES, ENABLED_LANGUAGES, SPANISH_ENABLED } from "./lib/language-features.ts";
      if (!SPANISH_ENABLED) throw new Error("Spanish flag did not enable Spanish");
      if (!ENABLED_LANGUAGE_CODES.includes("es-419")) throw new Error("Spanish code missing");
      if (!ENABLED_LANGUAGES.some((language) => language.code === "es-419")) throw new Error("Spanish option missing");
    `;

    try {
      process.env.NEXT_PUBLIC_ENABLE_SPANISH = "true";
      const result = Bun.spawnSync({
        cmd: ["bun", "-e", probe],
        cwd: webRoot,
        env: { ...process.env, NEXT_PUBLIC_ENABLE_SPANISH: "true" },
        stderr: "pipe",
        stdout: "pipe",
      });

      expect(result.exitCode, result.stderr.toString()).toBe(0);
    } finally {
      if (originalEnv === undefined) {
        delete process.env.NEXT_PUBLIC_ENABLE_SPANISH;
      } else {
        process.env.NEXT_PUBLIC_ENABLE_SPANISH = originalEnv;
      }
    }
  });
});
