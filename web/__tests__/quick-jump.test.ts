import { describe, expect, test } from "bun:test";
import { existsSync } from "node:fs";
import { join } from "node:path";

const primitivePath = join(
  import.meta.dir,
  "../components/keyboard/useQuickJump.ts",
);

describe("shared quick-jump primitive", () => {
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
