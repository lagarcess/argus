import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

describe("chat input send tooltip", () => {
  test("empty send button uses the shared tooltip and localized copy", () => {
    const input = readFileSync(join(root, "components/chat/ChatInput.tsx"), "utf-8");
    const en = readFileSync(join(root, "public/locales/en/common.json"), "utf-8");
    const es = readFileSync(join(root, "public/locales/es-419/common.json"), "utf-8");

    expect(input).toContain('import { Tooltip } from "@/components/ui/Tooltip";');
    expect(input).toContain("const sendDisabledReason =");
    expect(input).toContain("chat.message_empty");
    expect(input).toContain("Tooltip content={sendDisabledReason}");
    expect(input).toContain('data-testid="chat-send-disabled-tooltip"');
    expect(input).toContain('className="flex h-14 w-14 shrink-0 self-center items-center justify-center"');
    expect(input).toContain('className="inline-flex h-10 w-10 rounded-full"');
    expect(input).toContain('aria-disabled="true"');
    expect(input).toContain("tabIndex={0}");
    expect(input).toContain("event.stopPropagation()");
    expect(input).toContain("disabled={sendButtonDisabled}");
    expect(input).toContain("disabled:pointer-events-none");
    expect(input).toContain("inline-flex h-10 w-10 items-center justify-center");
    expect(input).toContain("absolute inset-y-0 left-14 flex items-center");
    expect(input).toContain("min-h-[1.45em]");
    expect(input).not.toContain("min-h-[34px]");
    expect(input).not.toContain("absolute left-14 top-2");
    expect(en).toContain('"message_empty": "Message is empty"');
    expect(es).toContain('"message_empty": "El mensaje está vacío"');
  });
});
