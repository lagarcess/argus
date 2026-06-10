import { expect, test, describe } from "bun:test";
import fs from "fs";
import path from "path";

describe("Spanish UI Smoke Harness", () => {
  const originalEnv = process.env.NEXT_PUBLIC_ENABLE_SPANISH;
  const esLocalePath = path.join(process.cwd(), "public/locales/es-419/common.json");

  test("Spanish locale JSON exists and parses", () => {
    expect(fs.existsSync(esLocalePath)).toBe(true);
    const content = fs.readFileSync(esLocalePath, "utf-8");
    const json = JSON.parse(content);
    expect(json).toBeDefined();

    // Verify key translation paths
    expect(json.settings?.languages?.["es-419"]).toBeDefined();
    expect(json.onboarding?.language).toBeDefined();
    expect(json.chat?.message_empty).toBeDefined();
    expect(json.chat?.backtest_job?.queued_title).toBeDefined();
    expect(json.chat?.backtest_job?.running_title).toBeDefined();
    expect(json.chat?.backtest_job?.succeeded_title).toBeDefined();
    expect(json.chat?.backtest_job?.failed_title).toBeDefined();
    expect(json.settings?.profile).toBeDefined();
  });

  test("Source referencing verified keys", () => {
    // Basic checks to ensure source files still reference keys that exist in Spanish bundle
    const languageSource = fs.readFileSync(path.join(process.cwd(), "components/SettingsMenu.tsx"), "utf-8");
    expect(languageSource).toContain("settings.languages.");

    const chatSource = fs.readFileSync(path.join(process.cwd(), "components/chat/ChatInput.tsx"), "utf-8");
    expect(chatSource).toContain("chat.message_empty");

    const backtestSource = fs.readFileSync(path.join(process.cwd(), "lib/backtest-job-card-copy.ts"), "utf-8");
    expect(backtestSource).toContain("chat.backtest_job.queued_title");
  });

  test("Spanish feature flag enables es-419", async () => {
    process.env.NEXT_PUBLIC_ENABLE_SPANISH = "true";

    // Use dynamic import to bust cache and reload the module with the new env
    const modulePath = path.join(process.cwd(), "lib/language-features.ts");
    const timestamp = Date.now();
    const languageFeatures = await import(`${modulePath}?v=${timestamp}`);

    expect(languageFeatures.SPANISH_ENABLED).toBe(true);
    expect(languageFeatures.ENABLED_LANGUAGE_CODES).toContain("es-419");
    expect(languageFeatures.ENABLED_LANGUAGES.some((l: { code: string }) => l.code === "es-419")).toBe(true);

    // restore
    if (originalEnv === undefined) {
      delete process.env.NEXT_PUBLIC_ENABLE_SPANISH;
    } else {
      process.env.NEXT_PUBLIC_ENABLE_SPANISH = originalEnv;
    }
  });

});
