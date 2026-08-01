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

  test("executes token and terminal scroll updates without moving a detached transcript", async () => {
    const { executeChatTranscriptUpdateScroll } = await import(
      "../components/chat/useChatScrollControls"
    );
    for (const update of ["token", "terminal"] as const) {
      const container = { scrollTop: 137 };
      const shouldAutoScrollRef = { current: false };
      let scrollCalls = 0;
      let preserveCalls = 0;

      executeChatTranscriptUpdateScroll({
        shouldAutoScrollRef,
        scrollToLatest: () => {
          scrollCalls += 1;
          container.scrollTop = 999;
        },
        updateScrollPositionState: () => {
          preserveCalls += 1;
          expect(container.scrollTop).toBe(137);
        },
      });

      expect(update).toBeOneOf(["token", "terminal"]);
      expect(scrollCalls).toBe(0);
      expect(preserveCalls).toBe(1);
      expect(container.scrollTop).toBe(137);
      expect(shouldAutoScrollRef.current).toBe(false);
    }
  });

  test("executes a following transcript update through the real scroll owner", async () => {
    const { executeChatTranscriptUpdateScroll } = await import(
      "../components/chat/useChatScrollControls"
    );
    const shouldAutoScrollRef = { current: true };
    let scrollCalls = 0;
    let preserveCalls = 0;

    executeChatTranscriptUpdateScroll({
      shouldAutoScrollRef,
      scrollToLatest: (behavior) => {
        expect(behavior).toBe("smooth");
        scrollCalls += 1;
      },
      updateScrollPositionState: () => {
        preserveCalls += 1;
      },
    });

    expect(scrollCalls).toBe(1);
    expect(preserveCalls).toBe(0);
    expect(shouldAutoScrollRef.current).toBe(true);
  });

  test("wires transcript renders to the tested scroll executor", () => {
    const chat = readFileSync(
      join(import.meta.dir, "../components/chat/ChatInterface.tsx"),
      "utf8",
    );

    expect(chat).toContain("executeChatTranscriptUpdateScroll({ shouldAutoScrollRef");
    expect(chat).not.toContain("conversationTranscriptUpdateScrollAction");
  });

  test("evolves the one existing Jump to latest target instead of adding another control", () => {
    const chat = readFileSync(
      join(import.meta.dir, "../components/chat/ChatInterface.tsx"),
      "utf8",
    );

    expect(chat.match(/<ConversationActivityJumpButton/g)).toHaveLength(1);
    expect(chat).not.toContain('aria-label="Jump to latest"');
    expect(chat).toContain('onJump={() => scrollToLatest("smooth")}');
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
