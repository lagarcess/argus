import { describe, expect, test } from "bun:test";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { guestProfileProbeOutcome } from "../lib/guest-account";

const root = join(import.meta.dir, "..");

function source(relativePath: string) {
  return readFileSync(join(root, relativePath), "utf-8");
}

describe("guest shell contract", () => {
  test("only a missing or expired guest profile enters deferred bootstrap", () => {
    expect(
      guestProfileProbeOutcome({ status: 401, code: "not_authenticated" }),
    ).toBe("bootstrap_required");
    expect(
      guestProfileProbeOutcome({ status: 403, code: "guest_session_expired" }),
    ).toBe("bootstrap_required");
    expect(
      guestProfileProbeOutcome({
        status: 403,
        code: "private_alpha_access_required",
      }),
    ).toBe("fail_closed");
    expect(
      guestProfileProbeOutcome({ status: 500, code: "internal_error" }),
    ).toBe("fail_closed");
  });

  test("renders guest chrome from verified account capabilities", () => {
    const chat = source("components/chat/ChatInterface.tsx");
    const policy = source("components/guest/useGuestShellActions.ts");
    const headerPath = join(root, "components/guest/GuestHeader.tsx");
    const settingsPath = join(root, "components/guest/GuestSettingsMenu.tsx");

    expect(existsSync(headerPath)).toBe(true);
    expect(existsSync(settingsPath)).toBe(true);
    expect(policy).toContain(
      'const isGuest = account?.account_kind === "guest"',
    );
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
    expect(chat).not.toContain(
      "temporaryExpiresAt={account?.guest?.expires_at",
    );
    expect(result).toContain("canSaveDecision");
    expect(result).toContain("onDecisionUnavailable");
  });

  test("hides owner menus without changing registered menu implementations", () => {
    const chat = source("components/chat/ChatInterface.tsx");
    const sidebar = source("components/sidebar/ChatSidebar.tsx");

    expect(chat).toMatch(
      /currentView === "chat" && isGuest \?[\s\S]{0,300}<GuestHeader/,
    );
    expect(chat).toMatch(
      /currentView === "chat" &&\s*conversationId &&\s*canManageConversation \?[\s\S]{0,300}<ChatHeaderMenu/,
    );
    expect(sidebar).toContain("canManageConversation");
    expect(sidebar).toContain("showProfileMenu");
    expect(sidebar).toMatch(
      /canManageConversation[\s\S]{0,300}<RecentChatActions/,
    );
    expect(sidebar).toMatch(/showProfileMenu[\s\S]{0,500}<ProfileMenu/);
  });

  test("keeps guest Recents owner-scoped with truthful expiry and sign-in copy", () => {
    const sidebar = source("components/sidebar/ChatSidebar.tsx");
    const chat = source("components/chat/ChatInterface.tsx");

    expect(chat).toMatch(
      /<ChatSidebar[\s\S]{0,2200}isGuest=\{guestExperience\.isEstablishedGuest\}/,
    );
    expect(sidebar).toContain("item.expires_at");
    expect(sidebar).toContain('"guest.history.keep_history"');
    expect(sidebar).toContain('"guest.history.expires_at"');
  });

  test("scopes guest search to the current workspace with honest discovery truth", () => {
    const chat = source("components/chat/ChatInterface.tsx");
    const palette = source("components/sidebar/ChatCommandPalette.tsx");
    const en = JSON.parse(source("public/locales/en/common.json"));
    const es = JSON.parse(source("public/locales/es-419/common.json"));

    expect(chat).toContain("isGuest={isGuest}");
    expect(chat).toContain(
      "groundedDiscoveryAvailable={canUseGroundedDiscovery}",
    );
    expect(chat).toContain("canManageConversation={canManageConversation}");
    expect(palette).toContain("setLedgerGroups(isGuest ? []");
    expect(palette).toContain("setLedgerGroups([]);");
    expect(palette).toContain("groundedDiscoveryAvailable");
    expect(palette).toContain('"command_palette.guest.discovery_unavailable"');
    expect(en.command_palette.guest.discovery_unavailable).toBe(
      "Search is limited to this temporary conversation. Broader grounded discovery isn’t available yet.",
    );
    expect(es.command_palette.guest.discovery_unavailable).toBe(
      "La búsqueda se limita a esta conversación temporal. El descubrimiento fundamentado más amplio aún no está disponible.",
    );
  });

  test("keeps the temporary-chat notice beneath the composer and out of the sidebar", () => {
    const chat = source("components/chat/ChatInterface.tsx");
    const sidebar = source("components/sidebar/ChatSidebar.tsx");
    const header = source("components/guest/GuestHeader.tsx");
    const intro = source("components/guest/GuestEmptyStateIntro.tsx");

    expect(sidebar).not.toContain("temporaryExpiresAt");
    expect(sidebar).not.toContain("guest-sidebar-expiry");
    expect(chat).not.toContain(
      "temporaryExpiresAt={account?.guest?.expires_at",
    );
    expect(header).not.toContain("temporary_until");
    expect(intro).not.toContain("value_body");
    expect(chat).toContain('"guest.shell.input_placeholder"');
  });

  test("shows exact server expiry metadata and permanent legal links in both states", () => {
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
    expect(footer).toContain('data-testid="guest-temporary-notice"');
    expect(footer).toContain("dateTime={expiresAt}");
    expect(footer).not.toContain("Date.now");
  });

  test("uses the compact settings menu and shared centered language modal", () => {
    const settings = source("components/guest/GuestSettingsMenu.tsx");
    const languageModal = source("components/settings/LanguageModal.tsx");

    expect(settings).not.toContain('"settings.appearance.title"');
    expect(settings).toContain("<LanguageModal");
    expect(settings).toContain("persistProfile={false}");
    expect(settings).toContain('role="group"');
    expect(settings.match(/role="menuitem"/g)?.length).toBe(2);
    expect(settings).not.toContain('role="menuitemradio"');
    expect(languageModal).toContain("persistProfile = true");
    expect(languageModal).toContain("if (persistProfile)");
  });

  test("keeps English and Spanish guest shell keys in parity", () => {
    const en = JSON.parse(source("public/locales/en/common.json"));
    const es = JSON.parse(source("public/locales/es-419/common.json"));
    const requiredKeys = [
      "value_title",
      "input_placeholder",
      "sign_in",
      "settings",
      "language",
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
      expect(
        valueAt(en.guest?.shell, key),
        `missing en guest.shell.${key}`,
      ).toBeString();
      expect(
        valueAt(es.guest?.shell, key),
        `missing es guest.shell.${key}`,
      ).toBeString();
    }

    // Spec 2026-08-07 section 10b: the guest empty-state placeholder invites
    // questions; the pre-rail string stays behind the flag-off path.
    expect(en.guest.shell.input_placeholder).toBe("Ask about any company or idea");
    expect(es.guest.shell.input_placeholder).toBe(
      "Pregunta sobre cualquier empresa o idea",
    );
    expect(en.guest.shell.input_placeholder_prerail).toBe(
      "What do you want to test?",
    );
    expect(es.guest.shell.input_placeholder_prerail).toBe("¿Qué quieres probar?");
    expect(en.guest.shell.temporary_until).toBe(
      "Temporary chat · available until {{date}}",
    );
    expect(es.guest.shell.temporary_until).toBe(
      "Chat temporal · disponible hasta {{date}}",
    );
  });
});
