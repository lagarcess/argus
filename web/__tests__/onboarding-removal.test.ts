import { expect, test, describe } from "bun:test";
import fs from "fs";
import path from "path";

import { retryLastTurnActionFromMessage } from "../lib/chat-retry-actions";

const webRoot = path.resolve(__dirname, "..");

const read = (relativePath: string) =>
  fs.readFileSync(path.join(webRoot, relativePath), "utf-8");

const flattenKeys = (value: unknown, prefix = ""): string[] => {
  if (typeof value !== "object" || value === null) return [prefix];
  return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) =>
    flattenKeys(child, prefix ? `${prefix}.${key}` : key),
  );
};

describe("onboarding strip-out: first use is ordinary chat", () => {
  test("no onboarding gate component exists", () => {
    expect(fs.existsSync(path.join(webRoot, "components/onboarding"))).toBe(false);
  });

  test("home and chat pages do not import or render an onboarding gate", () => {
    const landing = read("app/page.tsx");
    const chatPage = read("app/chat/page.tsx");
    for (const source of [landing, chatPage]) {
      expect(source).not.toContain("OnboardingGate");
      expect(source.toLowerCase()).not.toContain("onboarding");
    }
  });

  test("chat surface renders no onboarding goal cards or hidden protocol", () => {
    const chat = read("components/chat/ChatInterface.tsx");
    expect(chat).not.toContain("onboarding-goal-cards");
    expect(chat).not.toContain("onboarding-skip");
    expect(chat).not.toContain("__ONBOARDING_");
    expect(chat.toLowerCase()).not.toContain("onboarding");
  });

  test("chat message rendering has no onboarding marker substitution", () => {
    const message = read("components/chat/ChatMessage.tsx");
    expect(message).not.toContain("__ONBOARDING_");
    expect(message.toLowerCase()).not.toContain("onboarding");
  });

  test("no private-alpha onboarding feature flag remains", () => {
    const flags = read("lib/private-alpha-flags.ts");
    expect(flags).not.toContain("ONBOARDING");
    const settings = read("components/views/SettingsView.tsx");
    expect(settings).not.toContain("ONBOARDING");
    expect(settings.toLowerCase()).not.toContain("onboarding");
    const envExample = read(".env.local.example");
    expect(envExample).not.toContain("ONBOARDING");
    const playwrightConfig = read("playwright.config.ts");
    expect(playwrightConfig).not.toContain("ONBOARDING");
    const guestQaRunner = read("../scripts/qa/run-guest-experience-qa.sh");
    expect(guestQaRunner).not.toContain("ONBOARDING");
    const guestQaSupport = read("e2e/support/guest-qa.ts");
    expect(guestQaSupport).not.toContain("ONBOARDING");
  });

  test("profile api surface cannot write onboarding state", () => {
    const api = read("lib/argus-api.ts");
    expect(api.toLowerCase()).not.toContain("onboarding");
  });

  test("dev tooling has no onboarding reset", () => {
    const badge = read("components/ui/DevModeBadge.tsx");
    expect(badge.toLowerCase()).not.toContain("onboarding");
  });

  test("locale catalogs carry no onboarding strings and stay key-equal", () => {
    const en = JSON.parse(read("public/locales/en/common.json"));
    const es = JSON.parse(read("public/locales/es-419/common.json"));
    expect(Object.keys(en)).not.toContain("onboarding");
    expect(Object.keys(es)).not.toContain("onboarding");
    const enKeys = flattenKeys(en).sort();
    const esKeys = flattenKeys(es).sort();
    expect(esKeys).toEqual(enKeys);
    expect(enKeys.some((key) => key.toLowerCase().includes("onboarding"))).toBe(false);
  });

  test("generic localized starter prompts remain on the empty chat surface", () => {
    const chat = read("components/chat/ChatInterface.tsx");
    const starters = read("components/chat/StarterActions.tsx");
    expect(chat).toContain("<StarterActions");
    expect(starters).toContain("chat.starter_actions.tsla.value");
    expect(starters).toContain("chat.starter_actions.btc.value");
    expect(starters).toContain("chat.starter_actions.dca.value");
    const en = JSON.parse(read("public/locales/en/common.json"));
    const es = JSON.parse(read("public/locales/es-419/common.json"));
    expect(en.chat.starter_actions.tsla.value.length).toBeGreaterThan(0);
    expect(es.chat.starter_actions.tsla.value.length).toBeGreaterThan(0);
  });

  test("chat first paint waits for the authenticated profile language", () => {
    const chat = read("components/chat/ChatInterface.tsx");
    expect(chat).toContain("isBootstrappingProfile");
    const bootstrapFlip = chat.indexOf("setIsBootstrappingProfile(false)");
    const languageApply = chat.indexOf("await i18n.changeLanguage(resolvedLanguage)");
    expect(languageApply).toBeGreaterThan(-1);
    expect(bootstrapFlip).toBeGreaterThan(languageApply);
    expect(chat).toContain("if (isBootstrappingProfile) {");
  });

  test("an unreachable backend surfaces the offline message, not a healthy chat", () => {
    const chat = read("components/chat/ChatInterface.tsx");
    expect(chat).toContain("profileUnreachable = status !== 401 && status !== 403");
    const unreachableBranch = chat.indexOf("if (profileUnreachable) {");
    expect(unreachableBranch).toBeGreaterThan(-1);
    expect(
      chat.slice(unreachableBranch, unreachableBranch + 400),
    ).toContain("chat.error_offline");
  });

  test("legacy persisted marker content still cannot become a retry action", () => {
    expect(retryLastTurnActionFromMessage("__ONBOARDING_SKIP__")).toBeNull();
    expect(
      retryLastTurnActionFromMessage("__ONBOARDING_GOAL__:test_stock_idea"),
    ).toBeNull();
    expect(retryLastTurnActionFromMessage("Buy AAPL monthly")).not.toBeNull();
  });
});
