import { describe, expect, test } from "bun:test";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

describe("guest artifact education", () => {
  // Visible hint ownership is exercised by the real browser in
  // e2e/lift-edit-contract.spec.ts, including an unknown card kind.
  test("persists dismissal only in browser-local presentation state", () => {
    const hintPath = join(root, "components/guest/GuestArtifactHint.tsx");
    expect(existsSync(hintPath)).toBe(true);
    if (!existsSync(hintPath)) return;

    const hint = readFileSync(hintPath, "utf-8");
    expect(hint).toContain("argus:guest-hint:confirmation:v1");
    expect(hint).toContain("argus:guest-hint:result:v1");
    // Browser-local, and through the storage chokepoint so the keys stay in
    // the registry the privacy disclosure derives from.
    expect(hint).toContain("@/lib/browser-storage");
    expect(hint).toContain("writeStored");
    expect(hint).not.toContain("setTimeout");
    expect(hint).not.toContain("patchMe");
    expect(hint).not.toContain("postFeedback");
    expect(hint).not.toContain("fetch(");
  });

  test("ships localized copy for the two evidence-backed moments", () => {
    for (const locale of ["en", "es-419"]) {
      const messages = JSON.parse(
        readFileSync(
          join(root, `public/locales/${locale}/common.json`),
          "utf-8",
        ),
      );
      expect(messages.guest?.hints?.confirmation).toBeString();
      expect(messages.guest?.hints?.result).toBeString();
      expect(messages.guest?.hints?.dismiss).toBeString();
    }
  });
});
