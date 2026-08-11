import { describe, expect, test } from "bun:test";
import { readFileSync } from "fs";
import { join } from "path";

/* The not-advice disclosure is a compliance surface, not styling: Argus does
 * not provide investment, legal, tax, accounting, or financial advice, and
 * the research rail widens what Argus answers, so the framing matters more,
 * not less. These pins fail if the notice leaves the empty state. */

const root = join(__dirname, "..");
const source = (path: string) => readFileSync(join(root, path), "utf-8");

describe("empty-chat legal disclosure", () => {
  test("the empty surface renders the legal notice for both audiences", () => {
    const emptyChat = source("components/chat/EmptyChatSurface.tsx");
    expect(emptyChat).toContain("<ChatLegalNotice");
    expect(emptyChat).toContain(
      "showRegisteredDisclaimer={showSignedInGreeting}",
    );
    expect(emptyChat).toContain("showGuestSafetyLine={researchRailEnabled}");
  });

  test("the notice component owns both disclosure lines", () => {
    const notice = source("components/chat/ChatLegalNotice.tsx");
    expect(notice).toContain('data-testid="chat-disclaimer"');
    expect(notice).toContain('"chat.disclaimer"');
    expect(notice).toContain('data-testid="guest-safety-note"');
    expect(notice).toContain('"guest.shell.after_message.safety"');
  });

  test("both languages carry the exact disclosure strings", () => {
    const en = JSON.parse(source("public/locales/en/common.json"));
    const es = JSON.parse(source("public/locales/es-419/common.json"));
    expect(en.chat.disclaimer).toBe(
      "Argus can make mistakes. For education only. Not financial advice.",
    );
    expect(es.chat.disclaimer).toBe(
      "Argus puede equivocarse. Solo con fines educativos. No es asesoría financiera.",
    );
    expect(en.guest.shell.after_message.safety).toBeString();
    expect(es.guest.shell.after_message.safety).toBeString();
  });
});
