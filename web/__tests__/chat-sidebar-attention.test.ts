import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

describe("chat sidebar attention styling", () => {
  test("attention state remains visually distinct from selected conversation state", () => {
    const sidebar = readFileSync(
      join(root, "components/sidebar/ChatSidebar.tsx"),
      "utf-8",
    );
    const rowClassStart = sidebar.indexOf("className={`group relative flex w-full");
    const rowClassEnd = sidebar.indexOf("}`}", rowClassStart);
    const rowClassBlock = sidebar.slice(rowClassStart, rowClassEnd);

    expect(rowClassStart).toBeGreaterThan(-1);
    expect(rowClassBlock).toContain("isActiveConversation");
    expect(rowClassBlock).not.toContain("bg-[#7da0ca]");
    expect(sidebar).toContain('data-has-attention={hasConversationAttention ? "true" : undefined}');
    expect(sidebar).toContain("const attentionLabel = t(\"chat.history.new_activity\", \"New activity\")");
    expect(sidebar).toContain("aria-label={rowAriaLabel}");
    expect(sidebar).toContain('<span className="sr-only">{attentionLabel}</span>');
    expect(sidebar).toContain("bg-[#70a38d]");
    expect(sidebar).toContain('hasConversationAttention\n                                    ? "text-black/60 dark:text-white/60"');
  });
});
