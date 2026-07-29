import { describe, expect, test } from "bun:test";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  RECENTS_INITIAL_GROUP_LIMIT,
  getVisibleRecentChats,
  groupRecentChats,
  mergeRecentChats,
  projectConversationToRecentChat,
} from "../lib/chat-recents";
import type { Conversation, HistoryItem } from "../lib/argus-api";

const NOW = new Date(2026, 6, 28, 12, 0, 0);

function timestamp(daysAgo: number, hour = 12) {
  const value = new Date(NOW);
  value.setDate(NOW.getDate() - daysAgo);
  value.setHours(hour, 0, 0, 0);
  return value.toISOString();
}

function chat(
  id: string,
  daysAgo = 0,
  options: Readonly<{ pinned?: boolean }> = {},
): HistoryItem {
  return {
    type: "chat",
    id,
    title: `Conversation ${id}`,
    title_source: "user_renamed",
    subtitle: `Summary ${id}`,
    pinned: options.pinned ?? false,
    created_at: timestamp(daysAgo),
    conversation_id: id,
  };
}

describe("Recents projection", () => {
  test("maps a bounded conversation record to the existing chat-row contract", () => {
    const conversation: Conversation = {
      id: "chat-1",
      title: "AAPL notes",
      title_source: "ai_generated",
      pinned: true,
      archived: false,
      deleted_at: null,
      created_at: timestamp(8),
      updated_at: timestamp(1),
      last_message_preview: "Compare the result with SPY",
      language: "en",
    };

    expect(
      projectConversationToRecentChat(conversation, {
        guestExpiresAt: "2026-07-29T12:00:00Z",
      }),
    ).toEqual({
      type: "chat",
      id: "chat-1",
      title: "AAPL notes",
      title_source: "ai_generated",
      subtitle: "Compare the result with SPY",
      pinned: true,
      created_at: timestamp(1),
      conversation_id: "chat-1",
      expires_at: "2026-07-29T12:00:00Z",
    });
  });

  test("preserves every existing time group and keeps pinned chats distinct", () => {
    const groups = groupRecentChats(
      [
        chat("pinned", 90, { pinned: true }),
        chat("today", 0),
        chat("yesterday", 1),
        chat("week", 6),
        chat("month", 29),
        chat("earlier", 30),
      ],
      NOW,
    );

    expect(groups.map((group) => group.key)).toEqual([
      "pinned",
      "today",
      "yesterday",
      "last_7_days",
      "last_30_days",
      "earlier",
    ]);
    expect(groups[0]?.isPinned).toBe(true);
    expect(groups.slice(1).every((group) => !group.isPinned)).toBe(true);
  });

  test("caps an unpinned group at five while keeping an active sixth row visible", () => {
    const group = groupRecentChats(
      Array.from({ length: 7 }, (_, index) => chat(`today-${index + 1}`)),
      NOW,
    )[0]!;

    expect(RECENTS_INITIAL_GROUP_LIMIT).toBe(5);
    expect(
      getVisibleRecentChats(group, {
        expanded: false,
        selectedConversationId: null,
      }).map((item) => item.id),
    ).toEqual([
      "today-1",
      "today-2",
      "today-3",
      "today-4",
      "today-5",
    ]);
    expect(
      getVisibleRecentChats(group, {
        expanded: false,
        selectedConversationId: "today-7",
      }).map((item) => item.id),
    ).toEqual([
      "today-1",
      "today-2",
      "today-3",
      "today-4",
      "today-7",
    ]);
    expect(
      getVisibleRecentChats(group, {
        expanded: true,
        selectedConversationId: null,
      }),
    ).toHaveLength(7);
  });

  test("never caps pinned chats", () => {
    const group = groupRecentChats(
      Array.from({ length: 7 }, (_, index) =>
        chat(`pinned-${index + 1}`, 90, { pinned: true }),
      ),
      NOW,
    )[0]!;

    expect(
      getVisibleRecentChats(group, {
        expanded: false,
        selectedConversationId: null,
      }),
    ).toHaveLength(7);
  });

  test("deduplicates cursor pages by conversation identity", () => {
    const firstPage = [chat("chat-1"), chat("chat-2")];
    const secondPage = [chat("chat-2"), chat("chat-3")];

    expect(
      mergeRecentChats(firstPage, secondPage).map((item) => item.id),
    ).toEqual(["chat-1", "chat-2", "chat-3"]);
  });

  test("ships the approved English and Spanish disclosure copy", () => {
    const locale = (language: "en" | "es-419") =>
      JSON.parse(
        readFileSync(
          join(
            import.meta.dir,
            `../public/locales/${language}/common.json`,
          ),
          "utf-8",
        ),
      ) as {
        chat: {
          history: Record<string, string>;
          no_recent_activity: string;
        };
      };

    expect(locale("en").chat.history).toMatchObject({
      show_more: "Show more",
      show_less: "Show less",
      show_more_in: "Show more in {{group}}",
      show_less_in: "Show less in {{group}}",
      load_older: "Load older",
      loading_older: "Loading older chats…",
      no_older: "No older chats",
      load_older_error: "Couldn’t load older chats. Try again.",
    });
    expect(locale("en").chat.no_recent_activity).toBe(
      "No recent chats yet.",
    );
    expect(locale("es-419").chat.history).toMatchObject({
      earlier: "Anteriores",
      show_more: "Mostrar más",
      show_less: "Mostrar menos",
      show_more_in: "Mostrar más en {{group}}",
      show_less_in: "Mostrar menos en {{group}}",
      load_older: "Cargar chats anteriores",
      loading_older: "Cargando chats anteriores…",
      no_older: "No hay chats anteriores",
      load_older_error:
        "No se pudieron cargar los chats anteriores. Inténtalo de nuevo.",
    });
    expect(locale("es-419").chat.no_recent_activity).toBe(
      "Aún no hay chats recientes.",
    );
  });
});
