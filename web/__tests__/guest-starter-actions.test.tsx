import { describe, expect, test } from "bun:test";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = join(import.meta.dir, "..");

describe("shared starter actions", () => {
  test("extracts the three verified actions into one shared component", () => {
    const starterPath = join(root, "components/chat/StarterActions.tsx");
    expect(existsSync(starterPath)).toBe(true);
    if (!existsSync(starterPath)) return;

    const starter = readFileSync(starterPath, "utf-8");
    expect(starter).toContain("chat.starter_actions.tsla.label");
    expect(starter).toContain("chat.starter_actions.tsla.value");
    expect(starter).toContain("chat.starter_actions.btc.label");
    expect(starter).toContain("chat.starter_actions.btc.value");
    expect(starter).toContain("chat.starter_actions.dca.label");
    expect(starter).toContain("chat.starter_actions.dca.value");
    expect(starter).toContain("TrendingUp");
    expect(starter).toContain("Bitcoin");
    expect(starter).toContain("LineChart");
  });

  test("routes guest and registered empty chats through the same send owner", () => {
    const chat = readFileSync(
      join(root, "components/chat/ChatInterface.tsx"),
      "utf-8",
    );

    expect(chat).toContain("<StarterActions");
    expect(chat).toContain("onSelect={handleSend}");
    expect(chat).toContain(
      "const [isHydratingConversation, setIsHydratingConversation] = useState(true)",
    );
    expect(chat).toContain(
      "disabled={isStreamingResponse || isHydratingConversation}",
    );
    expect(chat.match(/<StarterActions/g)?.length).toBe(1);
    expect(chat).not.toContain(
      "onClick={() => handleSend(t('chat.starter_actions.tsla.value'",
    );
  });
});
