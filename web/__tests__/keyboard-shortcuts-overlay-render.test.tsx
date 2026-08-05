import { describe, expect, test } from "bun:test";
import i18next from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";

import KeyboardShortcutsOverlay from "../components/sidebar/KeyboardShortcutsOverlay";

async function renderOverlay(): Promise<string> {
  const i18n = i18next.createInstance();
  await i18n.init({
    lng: "en",
    fallbackLng: false,
    returnEmptyString: true,
    resources: {
      en: {
        translation: {
          keyboard_shortcuts: {
            shortcuts: {
              archive_focused_chat: "",
              toggle_read_focused_chat: "",
            },
          },
        },
      },
    },
  });

  return renderToStaticMarkup(
    <I18nextProvider i18n={i18n}>
      <KeyboardShortcutsOverlay onClose={() => undefined} />
    </I18nextProvider>,
  );
}

describe("KeyboardShortcutsOverlay presentation", () => {
  test("keeps complete fallback labels when a locale response is stale", async () => {
    const html = await renderOverlay();

    expect(html).toContain("Archive current chat");
    expect(html).toContain("Mark current chat as read or unread");
  });

  test("orders chat management safely with Delete last", async () => {
    const html = await renderOverlay();
    const labels = [
      "New chat",
      "Rename current chat",
      "Archive current chat",
      "Mark current chat as read or unread",
      "Pin or unpin current chat",
      "Delete current chat",
    ];
    const positions = labels.map((label) => html.indexOf(label));

    expect(positions.every((position) => position >= 0)).toBe(true);
    expect(positions).toEqual([...positions].sort((a, b) => a - b));
  });

  test("uses two desktop columns and lets Quick Jump span both", async () => {
    const html = await renderOverlay();

    expect(html).toContain("md:grid-cols-2");
    expect(html).toContain('data-shortcut-group="navigation"');
    expect(html).toContain('data-shortcut-group="chat"');
    expect(html).toMatch(
      /data-shortcut-group="quick_jump"[^>]*class="[^"]*md:col-span-2/,
    );
  });
});
