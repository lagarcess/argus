import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

import {
  applyProfileUpdate,
  greetingNameFor,
} from "../lib/account-profile";
import {
  DISPLAY_NAME_MAX_LENGTH,
  PREFERRED_NAME_MAX_LENGTH,
  normalizeProfileName,
  profileNameExceeds,
  profileNameLength,
} from "../lib/profile-names";
import type { ApiUser, UserResponse } from "../lib/guest-account";

const root = join(import.meta.dir, "..");
const source = (relativePath: string) =>
  readFileSync(join(root, relativePath), "utf-8");

const user = (overrides: Partial<ApiUser> = {}): ApiUser => ({
  id: "user-1",
  email: "a@b.c",
  username: "lucas",
  display_name: "Lucas Garces",
  preferred_name: null,
  language: "en",
  locale: "en-US",
  onboarding: {
    completed: false,
    stage: "language_selection",
    language_confirmed: false,
    primary_goal: null,
  },
  ...overrides,
});

const account = (overrides: Partial<ApiUser> = {}): UserResponse => ({
  user: user(overrides),
  account_kind: "registered",
  guest: null,
  capabilities: {
    can_create_additional_conversation: true,
    can_manage_conversation: true,
    can_save_decision: true,
    can_manage_account: true,
    can_use_omnisearch: true,
    can_search_current_workspace: true,
    can_use_grounded_discovery: true,
    can_submit_feedback: true,
  },
  public_account_access_enabled: false,
});

describe("a saved profile reaches the greeting", () => {
  test("the greeting's name changes on save, with no refetch and no reload", () => {
    // The exact defect: the menu saved, its own copy updated, and the shell went
    // on rendering the name the page had loaded with.
    const loaded = account({ preferred_name: null });
    expect(greetingNameFor(loaded)).toBeNull();

    const saved = applyProfileUpdate(loaded, user({ preferred_name: "Lucas" }));

    expect(greetingNameFor(saved)).toBe("Lucas");
    // Same snapshot the surface reads, not a second request.
    expect(saved).not.toBe(loaded);
    expect(saved?.account_kind).toBe("registered");
    expect(saved?.capabilities.can_manage_account).toBe(true);
  });

  test("clearing the name reaches the greeting the same way", () => {
    const named = account({ preferred_name: "Lucas" });
    expect(greetingNameFor(named)).toBe("Lucas");

    const cleared = applyProfileUpdate(named, user({ preferred_name: null }));

    expect(greetingNameFor(cleared)).toBeNull();
  });

  test("a save that is not the name still refreshes the shell's copy", () => {
    // Propagation is per patch, not per field, so a surface added later cannot
    // go stale by omission.
    const loaded = account({ display_name: "Lucas Garces" });

    const saved = applyProfileUpdate(
      loaded,
      user({ display_name: "L. Garces", preferred_name: "Lucas" }),
    );

    expect(saved?.user.display_name).toBe("L. Garces");
    expect(greetingNameFor(saved)).toBe("Lucas");
  });

  test("a guest with no profile resolves to the nameless pool", () => {
    expect(greetingNameFor(null)).toBeNull();
    expect(greetingNameFor(account({ preferred_name: undefined }))).toBeNull();
  });

  test("nothing to apply to is left alone rather than invented", () => {
    expect(applyProfileUpdate(null, user({ preferred_name: "Lucas" }))).toBeNull();
  });

  test("every successful patch propagates, not just the one that was noticed", () => {
    const menu = source("components/sidebar/ProfileMenu.tsx");
    const patches = menu.match(/await patchMe\(/g) ?? [];
    const propagations = menu.match(/applyPatchedProfile\(user\)/g) ?? [];
    expect(patches.length).toBeGreaterThanOrEqual(4);
    expect(propagations.length).toBe(patches.length);
    // The menu's own copy is no longer set directly from a patch response.
    const afterHelper = menu.slice(menu.indexOf("const applyPatchedProfile"));
    expect(afterHelper).not.toContain("      setProfile(user);\n      setEditing");
  });

  test("the shell owns the propagation and the greeting reads one place", () => {
    const chat = source("components/chat/ChatInterface.tsx");
    const sidebar = source("components/sidebar/ChatSidebar.tsx");

    const hook = source("components/chat/useProfileUpdates.ts");
    expect(chat).toContain("useProfileUpdates(account, setAccount)");
    expect(chat).toContain("onProfileUpdated={onProfileUpdated}");
    expect(chat).toContain("preferredName={greetingName}");
    expect(hook).toContain("applyProfileUpdate(current, user)");
    expect(hook).toContain("greetingNameFor(account)");
    // No second reader of the raw field, which is how the two copies drifted.
    expect(chat).not.toContain("account?.user.preferred_name");
    expect(sidebar).toContain("onProfileUpdated={onProfileUpdated}");
  });
});

describe("a name is measured after it is normalized", () => {
  test("a bound is never applied to what was typed around the name", () => {
    // The exact defect: one leading space in front of a full-length name.
    const padded = ` ${"x".repeat(PREFERRED_NAME_MAX_LENGTH)}`;
    expect(padded.length).toBe(PREFERRED_NAME_MAX_LENGTH + 1);

    expect(normalizeProfileName(padded).length).toBe(PREFERRED_NAME_MAX_LENGTH);
    expect(profileNameExceeds(padded, PREFERRED_NAME_MAX_LENGTH)).toBe(false);
  });

  test("a genuinely over-long name is still refused", () => {
    const tooLong = "x".repeat(PREFERRED_NAME_MAX_LENGTH + 1);
    expect(profileNameExceeds(tooLong, PREFERRED_NAME_MAX_LENGTH)).toBe(true);
    expect(profileNameExceeds(`  ${tooLong}  `, PREFERRED_NAME_MAX_LENGTH)).toBe(
      true,
    );
  });

  test("both name fields use the one rule", () => {
    const padded = ` ${"x".repeat(DISPLAY_NAME_MAX_LENGTH)}`;
    expect(profileNameExceeds(padded, DISPLAY_NAME_MAX_LENGTH)).toBe(false);
  });

  test("a name is measured in the units the bound is stated in", () => {
    // String.length counts UTF-16 code units, so anything outside the BMP counts
    // twice and the browser refused names the API and the database both take.
    const emoji = "👍".repeat(21);
    expect(emoji.length).toBe(42);
    expect(profileNameLength(emoji)).toBe(21);
    expect(profileNameExceeds(emoji, PREFERRED_NAME_MAX_LENGTH)).toBe(false);

    // And it is still a bound: code points past it are refused.
    const tooMany = "👍".repeat(PREFERRED_NAME_MAX_LENGTH + 1);
    expect(profileNameExceeds(tooMany, PREFERRED_NAME_MAX_LENGTH)).toBe(true);
    // Exactly at the bound is allowed, padded or not.
    const exact = "👍".repeat(PREFERRED_NAME_MAX_LENGTH);
    expect(profileNameExceeds(exact, PREFERRED_NAME_MAX_LENGTH)).toBe(false);
    expect(profileNameExceeds(`  ${exact}  `, PREFERRED_NAME_MAX_LENGTH)).toBe(
      false,
    );
  });

  test("neither input truncates what the user typed", () => {
    // Slicing the raw value to the bound dropped its last character whenever a
    // space led it, silently.
    const dialog = source("components/sidebar/ProfileDetailsDialog.tsx");
    expect(dialog).not.toContain("slice(0, 60)");
    expect(dialog).not.toContain("slice(0, PREFERRED_NAME_MAX_LENGTH)");
    expect(dialog).not.toContain("maxLength=");
  });

  test("both save paths refuse an over-long name and say so", () => {
    const menu = source("components/sidebar/ProfileMenu.tsx");
    expect(menu).toContain(
      "profileNameExceeds(nameValue, DISPLAY_NAME_MAX_LENGTH)",
    );
    expect(menu).toContain(
      "profileNameExceeds(preferredNameValue, PREFERRED_NAME_MAX_LENGTH)",
    );
    expect(menu).toContain("settings.profile.display_name_too_long");
    expect(menu).toContain("settings.profile.preferred_name_too_long");
    expect(menu).toContain("normalizeProfileName(nameValue)");
    expect(menu).toContain("normalizeProfileName(preferredNameValue)");

    for (const locale of ["en", "es-419"]) {
      const catalog = JSON.parse(source(`public/locales/${locale}/common.json`));
      for (const key of [
        "display_name_too_long",
        "preferred_name_too_long",
      ]) {
        expect(typeof catalog.settings.profile[key]).toBe("string");
        expect(catalog.settings.profile[key]).toContain("{{count}}");
      }
    }
  });

  test("leaving an edit takes the refusal with it", () => {
    // The error renders beside the field in read mode too, so an exit that only
    // flipped the mode left "Keep this to 40 characters or fewer." pinned under
    // a value that had nothing wrong with it. On the sheet path nothing could
    // clear it for the rest of the session.
    const menu = source("components/sidebar/ProfileMenu.tsx");
    const dialog = source("components/sidebar/ProfileDetailsDialog.tsx");

    for (const stop of ["stopEditingName", "stopEditingPreferredName"]) {
      const body = menu.slice(
        menu.indexOf(`const ${stop} = useCallback`),
        menu.indexOf("}, []);", menu.indexOf(`const ${stop} = useCallback`)),
      );
      expect(body).toContain("(false)");
      expect(body).toContain("(null)");
    }
    // No exit path sets the mode without going through the pair above.
    expect(dialog).not.toContain("setEditingName(false)");
    expect(dialog).not.toContain("setEditingPreferredName(false)");
    expect(menu).not.toContain("      setEditingName(false);\n      return;");
    expect(menu).not.toContain(
      "      setEditingPreferredName(false);\n      return;",
    );
  });

  test("closing the dialog does not leave a cleared box to confirm later", () => {
    // Clearing the box, closing with the X, then reopening showed an empty
    // input claiming the name was gone; pressing Enter there sent the clear.
    const menu = source("components/sidebar/ProfileMenu.tsx");
    const close = menu.slice(
      menu.indexOf("const closeProfileModal = useCallback"),
      menu.indexOf("setActiveModal(null);", menu.indexOf("const closeProfileModal")),
    );

    expect(close).toContain("stopEditingName()");
    expect(close).toContain("stopEditingPreferredName()");
    expect(close).toContain('setNameValue("")');
    expect(close).toContain('setPreferredNameValue("")');
  });

  test("a save in flight cannot reach the edit that replaced it", () => {
    // Closing the dialog does not cancel a request already on the wire, and the
    // sheet keeps the menu mounted underneath. A late failure pinned an error on
    // a field nobody was editing; a late success dismissed a fresh edit.
    const menu = source("components/sidebar/ProfileMenu.tsx");

    // Every await of a patch captures the session it belongs to.
    const awaits = menu.match(/await patchMe\(/g) ?? [];
    const captures = menu.match(/const session = editSessionRef\.current;/g) ?? [];
    expect(captures.length).toBe(awaits.length);
    // And closing bumps it, so those captures stop matching.
    const close = menu.slice(
      menu.indexOf("const closeProfileModal = useCallback"),
      menu.indexOf("setActiveModal(null);", menu.indexOf("const closeProfileModal")),
    );
    expect(close).toContain("editSessionRef.current += 1");
    // Including the in-flight flags, or a reopened dialog would stay disabled.
    expect(close).toContain("setIsSavingName(false)");
    expect(close).toContain("setIsSavingPreferredName(false)");

    // Every edit-local write after an await is guarded.
    for (const guarded of [
      "if (isCurrentEditSession(session)) stopEditingName();",
      "if (isCurrentEditSession(session)) stopEditingPreferredName();",
      "if (isCurrentEditSession(session)) setIsSavingName(false);",
      "if (isCurrentEditSession(session)) setIsSavingPreferredName(false);",
    ]) {
      expect(menu).toContain(guarded);
    }

    // The propagation is deliberately NOT guarded: the server changed whatever
    // the dialog is doing, and dropping it is how the shell's copy went stale.
    expect(menu).not.toContain("if (isCurrentEditSession(session)) applyPatchedProfile");
    const propagations = menu.match(/applyPatchedProfile\(user\)/g) ?? [];
    expect(propagations.length).toBe(awaits.length);
  });

  test("the bound has one frontend home", () => {
    // Two exported copies is the shape the finding is about; only the one in
    // profile-names.ts is pinned against the backend.
    expect(source("lib/argus-api.ts")).not.toContain("PREFERRED_NAME_MAX_LENGTH");
  });

  test("the frontend bound matches the backend's", () => {
    const schemas = readFileSync(
      join(root, "../src/argus/api/schemas.py"),
      "utf-8",
    );
    expect(schemas).toContain(
      `PREFERRED_NAME_MAX_LENGTH = ${PREFERRED_NAME_MAX_LENGTH}`,
    );
    // And the backend normalizes before it measures, or the two disagree on
    // exactly the padded case above.
    expect(schemas).toContain("BeforeValidator(_blank_preferred_name_is_no_name)");
  });
});
