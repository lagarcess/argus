import { describe, expect, test } from "bun:test";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

function source(relativePath: string) {
  return readFileSync(join(root, relativePath), "utf-8");
}

describe("guest shell contract", () => {
  test("renders guest chrome from verified account capabilities", () => {
    const chat = source("components/chat/ChatInterface.tsx");
    const policy = source("components/guest/useGuestShellActions.ts");
    const headerPath = join(root, "components/guest/GuestHeader.tsx");
    const settingsPath = join(root, "components/guest/GuestSettingsMenu.tsx");

    expect(existsSync(headerPath)).toBe(true);
    expect(existsSync(settingsPath)).toBe(true);
    expect(policy).toContain('const isGuest = account?.account_kind === "guest"');
    expect(policy).toContain("capabilities?.can_manage_conversation");
    expect(policy).toContain("capabilities?.can_use_omnisearch");
    expect(policy).toContain("capabilities?.can_save_decision");
    expect(chat).toContain("<GuestHeader");
    expect(chat).toContain("expiresAt={account?.guest?.expires_at");
  });

  test("keeps visible guest actions fail closed before Block 3", () => {
    const chat = source("components/chat/ChatInterface.tsx");
    const result = source("components/chat/StrategyResultCard.tsx");

    expect(chat).toContain("requestNewChat");
    expect(chat).toContain("requestOmnisearch");
    expect(chat).toContain("requestGuestSignIn");
    expect(chat).toContain("requestGuestDecision");
    expect(chat).toContain("canManageConversation={canManageConversation}");
    expect(chat).toContain("showProfileMenu={!isGuest}");
    expect(chat).toContain("temporaryExpiresAt={account?.guest?.expires_at");
    expect(result).toContain("canSaveDecision");
    expect(result).toContain("onDecisionUnavailable");
  });

  test("hides owner menus without changing registered menu implementations", () => {
    const sidebar = source("components/sidebar/ChatSidebar.tsx");

    expect(sidebar).toContain("canManageConversation");
    expect(sidebar).toContain("showProfileMenu");
    expect(sidebar).toMatch(
      /canManageConversation[\s\S]{0,300}<RecentChatActions/,
    );
    expect(sidebar).toMatch(/showProfileMenu[\s\S]{0,500}<ProfileMenu/);
  });

  test("shows exact server expiry and permanent legal links in both states", () => {
    const footerPath = join(root, "components/guest/GuestLegalFooter.tsx");
    expect(existsSync(footerPath)).toBe(true);
    if (!existsSync(footerPath)) return;

    const footer = readFileSync(footerPath, "utf-8");
    expect(footer).toContain('href="/terms"');
    expect(footer).toContain('href="/privacy"');
    expect(footer).toContain('"before_message"');
    expect(footer).toContain('"after_message"');
    expect(footer).toContain("Intl.DateTimeFormat");
    expect(footer).toContain("expiresAt");
    expect(footer).not.toContain("Date.now");
  });

  test("keeps English and Spanish guest shell keys in parity", () => {
    const en = JSON.parse(source("public/locales/en/common.json"));
    const es = JSON.parse(source("public/locales/es-419/common.json"));
    const requiredKeys = [
      "value_title",
      "value_body",
      "sign_in",
      "settings",
      "feedback",
      "temporary_until",
      "before_message.prefix",
      "before_message.terms",
      "before_message.middle",
      "before_message.privacy",
      "after_message.safety",
      "after_message.terms",
      "after_message.privacy",
      "new_chat_unavailable",
      "search_unavailable",
      "decision_unavailable",
      "sign_in_unavailable",
    ];

    const valueAt = (value: unknown, path: string) =>
      path.split(".").reduce<unknown>((current, segment) => {
        if (!current || typeof current !== "object") return undefined;
        return (current as Record<string, unknown>)[segment];
      }, value);

    for (const key of requiredKeys) {
      expect(valueAt(en.guest?.shell, key), `missing en guest.shell.${key}`).toBeString();
      expect(valueAt(es.guest?.shell, key), `missing es guest.shell.${key}`).toBeString();
    }
  });
});
