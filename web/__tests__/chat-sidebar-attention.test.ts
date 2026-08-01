import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

describe("chat sidebar activity ownership", () => {
  test("removes the legacy Set marker while preserving row and quick-jump geometry", () => {
    const sidebar = readFileSync(
      join(root, "components/sidebar/ChatSidebar.tsx"),
      "utf-8",
    );
    const rowClassStart = sidebar.indexOf("className={`group relative flex w-full");
    const rowClassEnd = sidebar.indexOf("}`}", rowClassStart);
    const rowClassBlock = sidebar.slice(rowClassStart, rowClassEnd);
    const attentionLaneStart = sidebar.indexOf(
      'className="flex h-6 w-11 flex-shrink-0 items-center justify-center"',
    );
    const attentionLaneEnd = sidebar.indexOf("</div>", attentionLaneStart);
    const attentionLaneBlock = sidebar.slice(
      attentionLaneStart,
      attentionLaneEnd,
    );

    expect(rowClassStart).toBeGreaterThan(-1);
    expect(attentionLaneStart).toBeGreaterThan(-1);
    expect(rowClassBlock).toContain("isActiveConversation");
    expect(rowClassBlock).not.toContain("bg-[#7da0ca]");
    expect(sidebar).not.toContain("attentionConversationIds");
    expect(sidebar).not.toContain("EMPTY_ATTENTION_IDS");
    expect(sidebar).not.toContain("hasConversationAttention");
    expect(sidebar).not.toContain("data-has-attention");
    expect(sidebar).toContain("aria-label={displayTitle}");
    expect(sidebar).not.toContain("bg-[#70a38d]");
    expect(attentionLaneBlock).not.toContain("QuickJumpBadge");
    expect(sidebar).toContain("data-quick-jump-hint={quickJumpNumber}");
    expect(sidebar.indexOf("quickJumpHint={quickJumpHint}", attentionLaneEnd))
      .toBeGreaterThan(attentionLaneEnd);
  });
});
