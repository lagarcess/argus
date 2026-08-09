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
