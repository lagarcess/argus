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
    const starter = readFileSync(
      join(root, "components/chat/StarterActions.tsx"),
      "utf-8",
    );
    const emptyChat = readFileSync(
      join(root, "components/chat/EmptyChatSurface.tsx"),
      "utf-8",
    );
    const initialSession = readFileSync(
      join(root, "components/chat/useInitialChatSession.ts"),
      "utf-8",
    );
    const guestExperience = readFileSync(
      join(root, "components/guest/useGuestExperience.ts"),
      "utf-8",
    );

    expect(emptyChat).toContain("<StarterActions");
    expect(chat).toContain("onSend={handleSend}");
    expect(emptyChat).toContain("onSelect={onSend}");
    expect(chat).toContain('profileState === "probing"');
    expect(chat).toContain("guestSubmissionPending");
    expect(chat).toContain("hasAcceptedUserInputRef.current = true");
    expect(initialSession).toContain("cancelled || hasAcceptedUserInputRef.current");
    expect(emptyChat.match(/<StarterActions/g)?.length).toBe(1);
    expect(`${chat}\n${emptyChat}`).not.toContain(
      "onClick={() => handleSend(t('chat.starter_actions.tsla.value'",
    );
    expect(starter).toMatch(/onSelect\(value,\s*\{\s*strategy_category\s*\}\)/);
    expect(starter).not.toContain("captureGuestFunnelEvent");
    expect(guestExperience).toContain("startGuestSession");
    expect(`${chat}\n${guestExperience}`).toContain("captureGuestFunnelEvent");
    const admissionOwner = guestExperience.slice(
      guestExperience.indexOf("const admitSend"),
    );
    expect(admissionOwner.indexOf("startGuestSession")).toBeLessThan(
      admissionOwner.indexOf("getUsageAllowances"),
    );
  });
});
