import { describe, expect, test } from "bun:test";

import { writeClipboardText } from "../lib/clipboard";

describe("chat clipboard helpers", () => {
  test("uses the async clipboard when available", async () => {
    const writes: string[] = [];

    const copied = await writeClipboardText("message-id-1", {
      clipboard: {
        writeText: async (value: string) => {
          writes.push(value);
        },
      },
    });

    expect(copied).toBe(true);
    expect(writes).toEqual(["message-id-1"]);
  });

  test("falls back to a temporary textarea when clipboard permission fails", async () => {
    const calls: string[] = [];
    const removed: string[] = [];
    const textarea = {
      value: "",
      style: {},
      focus: () => calls.push("focus"),
      select: () => calls.push("select"),
      remove: () => removed.push("remove"),
    };

    const copied = await writeClipboardText("plain text", {
      clipboard: {
        writeText: async () => {
          throw new Error("denied");
        },
      },
      document: {
        createElement: () => textarea,
        body: {
          appendChild: () => calls.push("append"),
        },
        execCommand: (command: string) => {
          calls.push(command);
          return command === "copy";
        },
      },
    });

    expect(copied).toBe(true);
    expect(textarea.value).toBe("plain text");
    expect(calls).toEqual(["append", "focus", "select", "copy"]);
    expect(removed).toEqual(["remove"]);
  });

  test("returns false and cleans up when the textarea fallback is blocked", async () => {
    const calls: string[] = [];
    const removed: string[] = [];
    const textarea = {
      value: "",
      style: {},
      focus: () => calls.push("focus"),
      select: () => calls.push("select"),
      remove: () => removed.push("remove"),
    };

    const copied = await writeClipboardText("plain text", {
      clipboard: {
        writeText: async () => {
          throw new Error("denied");
        },
      },
      document: {
        createElement: () => textarea,
        body: {
          appendChild: () => calls.push("append"),
        },
        execCommand: () => {
          calls.push("copy");
          throw new Error("blocked");
        },
      },
    });

    expect(copied).toBe(false);
    expect(calls).toEqual(["append", "focus", "select", "copy"]);
    expect(removed).toEqual(["remove"]);
  });
});
