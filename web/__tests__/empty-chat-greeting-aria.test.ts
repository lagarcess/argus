import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

function source(relativePath: string) {
  return readFileSync(join(root, relativePath), "utf-8");
}

describe("empty-chat greeting accessibility", () => {
  test("a screen reader hears the greeting exactly once", () => {
    const greeting = source("components/chat/EmptyChatGreeting.tsx");

    // The visible typewriter paragraph is decoration to assistive tech: it
    // would otherwise announce character by character and then again in the
    // status region. Its caret is hidden with it.
    const paragraph = greeting.slice(
      greeting.indexOf("<p"),
      greeting.indexOf("</p>"),
    );
    expect(paragraph).toContain('aria-hidden="true"');

    // Exactly one accessible copy exists: the polite status region, filled
    // once with the full sentence (never the sliced animation text), so the
    // announcement happens a single time when the greeting mounts.
    expect(greeting.match(/role="status"/g)?.length).toBe(1);
    const status = greeting.slice(greeting.indexOf('role="status"'));
    expect(status).toContain("{greeting ?? \"\"}");
    expect(status).not.toContain("slice(0, visibleCount)");

    // The duplicated line in rendered-text captures is expected: innerText
    // includes both the aria-hidden visual and the sr-only region. The
    // accessibility tree contains the sentence once.
  });
});

describe("what Argus calls the user", () => {
  test("the name is a stated setting, not an inferred one", () => {
    // Argus does not work out what to call you from how you type. Memory
    // infers; settings are stated.
    const greeting = source("components/chat/EmptyChatGreeting.tsx");
    const surface = source("components/chat/EmptyChatSurface.tsx");
    const chat = source("components/chat/ChatInterface.tsx");

    expect(chat).toContain("preferredName={account?.user.preferred_name}");
    expect(surface).toContain("preferredName={preferredName}");
    expect(greeting).toContain("preferredName");
    // It reaches the pool as a plain eligibility flag, so no greeting can
    // interpolate a name the pool did not ask for.
    expect(greeting).toContain("hasName: name.length > 0");
    expect(greeting).not.toContain("display_name");
  });

  test("the settings field is separate from display name", () => {
    // display_name is an identity field people fill with a legal name.
    const dialog = source("components/sidebar/ProfileDetailsDialog.tsx");
    const menu = source("components/sidebar/ProfileMenu.tsx");
    const en = JSON.parse(source("public/locales/en/common.json"));
    const es = JSON.parse(source("public/locales/es-419/common.json"));

    expect(dialog).toContain("settings.profile.preferred_name");
    expect(dialog).toContain("argus-profile-preferred-name");
    expect(menu).toContain("patchMe({ preferred_name: trimmed || null })");
    expect(menu).toContain("patchMe({ display_name: trimmed })");
    // Blank clears it, which is how a user opts out after opting in.
    expect(en.settings.profile.preferred_name).toBe(
      "What should Argus call you?",
    );
    for (const catalog of [en, es]) {
      for (const key of [
        "preferred_name",
        "preferred_name_placeholder",
        "preferred_name_unset",
        "preferred_name_save_error",
      ]) {
        expect(typeof catalog.settings.profile[key]).toBe("string");
      }
      expect(catalog.settings.profile.preferred_name).not.toBe(
        catalog.settings.profile.display_name,
      );
    }
  });

  test("guests never reach the named pool", () => {
    // They have no profile, so there is nothing to address them by.
    const surface = source("components/chat/EmptyChatSurface.tsx");

    expect(surface).toContain("researchRailEnabled && !isGuest");
  });
});
