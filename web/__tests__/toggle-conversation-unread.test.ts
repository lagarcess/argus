import { describe, expect, test } from "bun:test";
import { toggleConversationUnread } from "../components/chat/toggleConversationUnread";

function activityController({
  unread,
  pending = false,
}: {
  unread: boolean;
  pending?: boolean;
}) {
  const calls: string[] = [];
  return {
    calls,
    controller: {
      hasEffectiveUnread: () => unread,
      isMutationPending: () => pending,
      markRead: (_conversationId: string, cursor: string | null) => {
        calls.push(`read:${cursor}`);
        return Promise.resolve();
      },
      markUnread: () => {
        calls.push("unread");
        return Promise.resolve();
      },
      selectAttentionCursor: () => "attention:chat_turn:1",
    },
  };
}

describe("toggleConversationUnread", () => {
  test("marks a read conversation unread", async () => {
    const activity = activityController({ unread: false });

    await toggleConversationUnread(activity.controller, "conversation-1");

    expect(activity.calls).toEqual(["unread"]);
  });

  test("marks an unread conversation read through its attention cursor", async () => {
    const activity = activityController({ unread: true });

    await toggleConversationUnread(activity.controller, "conversation-1");

    expect(activity.calls).toEqual(["read:attention:chat_turn:1"]);
  });

  test("does nothing while the matching mutation is pending", async () => {
    const activity = activityController({ unread: false, pending: true });

    await toggleConversationUnread(activity.controller, "conversation-1");

    expect(activity.calls).toEqual([]);
  });
});
