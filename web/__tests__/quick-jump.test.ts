import { describe, expect, test } from "bun:test";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const primitivePath = join(
  import.meta.dir,
  "../components/keyboard/useQuickJump.ts",
);

describe("shared quick-jump primitive", () => {
  test("keeps the 240px navigation threshold separate from viewport read proof", async () => {
    const { chatScrollPositionState } = await import(
      "../components/chat/useChatScrollControls"
    );

    expect(chatScrollPositionState(240)).toEqual({
      shouldAutoScroll: true,
      showJumpToLatest: false,
    });
    expect(chatScrollPositionState(241)).toEqual({
      shouldAutoScroll: false,
      showJumpToLatest: true,
    });
  });

  test("preserves a scrolled-up position across token and completion renders", () => {
    const chat = readFileSync(
      join(import.meta.dir, "../components/chat/ChatInterface.tsx"),
      "utf8",
    );
    const effectStart = chat.indexOf("if (shouldAutoScrollRef.current) {");
    const effectEnd = chat.indexOf("// ── Load existing conversation", effectStart);
    const scrollEffect = chat.slice(effectStart, effectEnd);

    expect(effectStart).toBeGreaterThan(-1);
    expect(scrollEffect).toContain('scrollToLatest("smooth")');
    expect(scrollEffect).toContain("} else {");
    expect(scrollEffect).toContain("updateScrollPositionState();");
    expect(scrollEffect).toContain("messages.length");
    expect(scrollEffect).toContain("streamStatus");
  });

  test("numbers pinned visible items first and limits every surface to nine", async () => {
    expect(existsSync(primitivePath)).toBe(true);
    if (!existsSync(primitivePath)) return;

    const { numberQuickJumpItems } = await import(
      "../components/keyboard/useQuickJump"
    );

    expect(
      numberQuickJumpItems([
        { id: "recent", pinned: false },
        { id: "pinned", pinned: true },
        { id: "another-pinned", pinned: true },
      ]),
    ).toEqual([
      { id: "pinned", pinned: true, number: 1 },
      { id: "another-pinned", pinned: true, number: 2 },
      { id: "recent", pinned: false, number: 3 },
    ]);

    expect(
      numberQuickJumpItems(
        Array.from({ length: 11 }, (_, index) => ({ id: String(index) })),
      ),
    ).toHaveLength(9);
  });

  test("selects a visible numbered item from the registry's physical digit code", async () => {
    expect(existsSync(primitivePath)).toBe(true);
    if (!existsSync(primitivePath)) return;

    const { quickJumpItemForEvent } = await import(
      "../components/keyboard/useQuickJump"
    );
    const items = [
      { id: "pinned", pinned: true },
      { id: "recent", pinned: false },
    ];

    expect(
      quickJumpItemForEvent(
        items,
        {
          key: "@",
          code: "Digit2",
          metaKey: false,
          ctrlKey: true,
          shiftKey: true,
          altKey: false,
        },
        false,
      ),
    ).toMatchObject({ id: "recent", number: 2 });
  });
});
