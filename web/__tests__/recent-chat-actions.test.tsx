import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const source = readFileSync(
  join(import.meta.dir, "../components/sidebar/RecentChatActions.tsx"),
  "utf-8",
);
const sidebar = readFileSync(
  join(import.meta.dir, "../components/sidebar/ChatSidebar.tsx"),
  "utf-8",
);

describe("RecentChatActions unread control", () => {
  test("keeps one pointer-aware touch-safe ellipsis outside quick-jump mode", () => {
    expect(source.match(/<MoreVertical/g)).toHaveLength(1);
    expect(source).toContain("h-11 w-11");
    expect(source).toContain('MoreVertical className="h-3.5 w-3.5');
    expect(source).toContain("pointerAffordances.recentsOwnerAction");
    expect(source).toContain("isMenuOpen || isTriggerFocused || !quickJumpHint");
    expect(source).toContain('w-[88px]');
    expect(source).not.toContain("ConversationActivityIndicator");
    expect(source).not.toContain("data-activity-dot");
  });

  test("puts unread first and keeps delete separated and destructive", () => {
    const unread = source.indexOf('"chat.activity.mark_read"');
    const pin = source.indexOf("onPin(item.id");
    const rename = source.indexOf("onRename(item.id)");
    const archive = source.indexOf("onArchive(item.id)");
    const separator = source.indexOf('role="separator"');
    const remove = source.indexOf("onDelete(item.id)");

    expect(unread).toBeGreaterThan(-1);
    expect(unread).toBeLessThan(pin);
    expect(pin).toBeLessThan(rename);
    expect(rename).toBeLessThan(archive);
    expect(archive).toBeLessThan(separator);
    expect(separator).toBeLessThan(remove);
    expect(source.slice(separator, remove)).toContain("border-black/10");
    expect(source.slice(remove)).toContain("text-[#d66d75]");
  });

  test("closes optimistically and restores trigger focus on Escape", () => {
    const toggleStart = source.indexOf("const handleToggleUnread");
    const toggleEnd = source.indexOf("};", toggleStart);
    const toggle = source.slice(toggleStart, toggleEnd);
    const escapeStart = source.indexOf('event.key === "Escape"');
    const escapeEnd = source.indexOf("}", escapeStart);
    const escape = source.slice(escapeStart, escapeEnd);

    expect(toggle.indexOf("setIsMenuOpen(false)")).toBeLessThan(
      toggle.indexOf("onToggleUnread()"),
    );
    expect(escape).toContain("setIsMenuOpen(false)");
    expect(escape).toContain("triggerRef.current?.focus()");
  });

  test("uses the shared activity owner and current canonical cursor without changing row order", () => {
    expect(sidebar).toContain("conversationActivity.hasEffectiveUnread(itemConversationId)");
    expect(sidebar).toContain("conversationActivity.selectAttentionCursor(itemConversationId)");
    expect(sidebar).toContain('conversationActivity.isMutationPending(itemConversationId, "mark_read")');
    expect(sidebar).toContain('conversationActivity.isMutationPending(itemConversationId, "mark_unread")');
    expect(sidebar).toContain("conversationActivity.markRead(itemConversationId,");
    expect(sidebar).toContain("conversationActivity.markUnread(itemConversationId)");
    expect(sidebar).not.toContain("sort(");
  });
});
