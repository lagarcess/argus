import { describe, expect, test } from "bun:test";
import i18next from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";

import {
  ConversationActivityPresentationProvider,
} from "../components/chat/ConversationActivityIndicator";
import RecentsQuickPeek from "../components/sidebar/RecentsQuickPeek";
import type { HistoryItem } from "../lib/argus-api";
import type { ConversationActivityPresentation } from "../lib/conversation-activity-state";
import type { ConversationActivityOperationLabel } from "../lib/conversation-activity-state";

const presentations: Record<string, ConversationActivityPresentation> = {
  queued: "working",
  checking: "working",
  unread: "new_activity",
  attention: "needs_attention",
};

const operationLabels: Record<string, ConversationActivityOperationLabel> = {
  queued: "queued",
  checking: "checking",
};

const items: HistoryItem[] = Object.keys(presentations).map((id) => ({
  type: "chat",
  id,
  title: `${id} chat`,
  title_source: "user_renamed",
  subtitle: `${id} summary`,
  pinned: false,
  created_at: "2026-08-01T12:00:00Z",
  conversation_id: id,
}));

describe("RecentsQuickPeek conversation activity", () => {
  test("matches expanded Recents state and keeps selected markers with localized labels", async () => {
    const i18n = i18next.createInstance();
    await i18n.init({
      lng: "es-419",
      fallbackLng: false,
      interpolation: { escapeValue: false },
      resources: {
        "es-419": {
          translation: {
            chat: {
              new_chat: "Nuevo chat",
              activity: {
                working: "Trabajando",
                queued: "En espera",
                checking: "Consultando el estado",
                new_activity: "Actividad nueva",
                needs_attention: "Necesita atención",
              },
            },
            recents_quick_peek: {
              title: "Recientes",
              close: "Cerrar Recientes",
              empty: "Aún no hay chats recientes.",
            },
          },
        },
      },
    });

    const html = renderToStaticMarkup(
      <I18nextProvider i18n={i18n}>
        <ConversationActivityPresentationProvider
          selectPresentation={(conversationId) =>
            conversationId ? presentations[conversationId] ?? "none" : "none"
          }
          selectAggregatePresentation={() => "working"}
          selectOperationLabel={(conversationId) =>
            conversationId ? operationLabels[conversationId] ?? null : null
          }
        >
          <RecentsQuickPeek
            historyItems={items}
            activeConversationId="queued"
            onOpenItem={() => undefined}
            onClose={() => undefined}
          />
        </ConversationActivityPresentationProvider>
      </I18nextProvider>,
    );

    expect(html).toContain('aria-current="page"');
    expect(html).toContain('aria-label="queued chat. En espera."');
    expect(html).toContain(
      'aria-label="checking chat. Consultando el estado."',
    );
    expect(html).toContain('aria-label="unread chat. Actividad nueva."');
    expect(html).toContain('aria-label="attention chat. Necesita atención."');
    expect(html).toContain('data-conversation-activity="working"');
    expect(html).toContain('data-conversation-activity="new_activity"');
    expect(html).toContain('data-conversation-activity="needs_attention"');
  });

  test("keeps the marker out of the right quick-jump slot without shifting text", async () => {
    const source = await Bun.file(
      new URL("../components/sidebar/RecentsQuickPeek.tsx", import.meta.url),
    ).text();

    expect(source).toContain("ConversationActivityIndicator");
    expect(source).toContain("pointer-events-none absolute -left-");
    expect(source).toContain('presentation="shortcut_hint"');
    expect(source.indexOf("ConversationActivityIndicator")).toBeLessThan(
      source.indexOf("data-quick-jump-hint={number}"),
    );
  });
});
