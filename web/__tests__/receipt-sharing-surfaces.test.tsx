import { afterEach, describe, expect, test } from "bun:test";
import { isValidElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";
import { createInstance } from "i18next";
import ShareReceiptAction from "../components/chat/ShareReceiptAction";
import { ReceiptTurnChoice } from "../components/chat/ReceiptConversationSelection";
import ReceiptBody from "../components/receipt/ReceiptBody";
import ReceiptViewBeacon from "../components/receipt/ReceiptViewBeacon";
import ReceiptNotice from "../components/receipt/ReceiptNotice";
import ReceiptActionBar from "../components/receipt/ReceiptActionBar";
import { reportReceiptFunnelStage } from "../lib/receipt-funnel";
import { receiptCopy } from "../lib/receipt-copy";
import { normalizeEnabledLanguage } from "../lib/language-features";
import type { ReceiptKind } from "../lib/public-receipt-turns";
import { backtestTurn, researchTurn, turnDocument } from "./fixtures/receipt-turns";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";

const noop = () => {};
const originalFetch = globalThis.fetch;
afterEach(() => { globalThis.fetch = originalFetch; });

describe.each(["en", "es-419"] as const)("share surfaces in %s", (languageValue) => {
  const language = languageValue as "en" | "es-419";
  test("the transcript choice names the question and answer, with private turns disabled", async () => {
    const i18n = createInstance();
    await i18n.init({ lng: language, resources: { en: { translation: en }, "es-419": { translation: es } } });
    const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><ReceiptTurnChoice candidate={{ message_id: "private", eligible: false, reason: "unsafe_text", field: "answer" }} selected={false} onToggle={noop} /></I18nextProvider>);
    expect(markup).toContain('type="checkbox"');
    expect(markup).toContain('disabled=""');
    expect(markup).toContain(receiptCopy(normalizeEnabledLanguage(language)).selection.choose_turn);
    expect(markup).toContain(receiptCopy(normalizeEnabledLanguage(language)).selection.reasons.unsafe_text);
  });

  test("header shortcut announces sharing the conversation, not creating a link", async () => {
    const i18n = createInstance();
    await i18n.init({ lng: language, resources: { en: { translation: en }, "es-419": { translation: es } } });
    const markup = renderToStaticMarkup(<I18nextProvider i18n={i18n}><ShareReceiptAction conversationId="conversation" onShare={noop} /></I18nextProvider>);
    expect(markup).toContain(`aria-label="${receiptCopy(language).selection.title}"`);
    expect(markup).not.toContain(receiptCopy(language).owner.create);
    expect(markup).not.toContain("conversationId");
  });
});

function beaconCount(node: ReactNode): number {
  if (Array.isArray(node)) return node.reduce((count, child) => count + beaconCount(child), 0);
  if (!isValidElement<{ children?: ReactNode }>(node)) return 0;
  return Number(node.type === ReceiptViewBeacon) + beaconCount(node.props.children);
}
test.each(["revoked", "unavailable"] as const)("%s links have no attributed beacon and keep the bare CTA", (kind) => {
  const view = ReceiptNotice({ kind, copy: receiptCopy("en") });
  expect(beaconCount(view)).toBe(0);
  const markup = renderToStaticMarkup(view);
  expect(markup.match(/href="([^"]+)"/)?.[1]).toBe("/");
  expect(markup).toContain(receiptCopy("en").cta.action);
});

test("an unknown link CTA does not invent a backtest funnel event", () => {
  const requests: unknown[] = [];
  globalThis.fetch = (async (_url, init) => { requests.push(init?.body); return Response.json({}); }) as typeof fetch;
  function clickLink(node: ReactNode): void {
    if (Array.isArray(node)) { node.forEach(clickLink); return; }
    if (!isValidElement<{ children?: ReactNode; href?: string; onClick?: () => void }>(node)) return;
    if (node.props.href === "/") node.props.onClick?.();
    clickLink(node.props.children);
  }
  clickLink(ReceiptActionBar({ kind: null, framing: "Context", action: "Continue with Argus" }));
  expect(requests).toEqual([]);
});
test.each([1, 4])("%s turns mount one public beacon and zero preview beacons", (count) => {
  const payload = turnDocument(...Array.from({ length: Number(count) }, (_, index) => index % 2 ? backtestTurn : researchTurn));
  const props = { payload, createdAt: null, copy: receiptCopy("en"), language: "en" as const };
  expect(beaconCount(ReceiptBody(props))).toBe(1);
  expect(beaconCount(ReceiptBody({ ...props, preview: true }))).toBe(0);
});

test.each(["backtest", "research_answer", "mixed"] as ReceiptKind[])("funnel preserves %s without carrying a receipt identity", async (kind) => {
  const bodies: unknown[] = [];
  globalThis.fetch = (async (_url, init) => { bodies.push(JSON.parse(String(init?.body))); return Response.json({}); }) as typeof fetch;
  reportReceiptFunnelStage("viewed", kind);
  reportReceiptFunnelStage("try_argus", kind);
  expect(bodies).toEqual([{ stage: "viewed", kind }, { stage: "try_argus", kind }]);
});
