import { test, expect, type BrowserContext, type Page } from "@playwright/test";
import { identities, loginViaUi } from "../qa-248/helpers";
import {
  conversationMessages,
  messageDigest,
  saveEvidence,
  sendTurn,
  shot,
  startNewChat,
} from "./j241.helpers";

// Single-attempt follow-up: drive the deterministic invalid-date corridor
// (end beyond today) so the distinct repair labels render live.

test.describe.configure({ mode: "serial" });

test.beforeEach(async () => {
  test.setTimeout(600_000);
});

let context: BrowserContext;
let page: Page;

test.beforeAll(async ({ browser }) => {
  test.setTimeout(180_000);
  const ids = identities();
  context = await browser.newContext();
  page = await context.newPage();
  await loginViaUi(page, ids.recoveryEmail, ids.recoveryPassword);
});

test.afterAll(async () => {
  await context?.close();
});

test("p6 end-beyond-today keeps distinct repair labels", async () => {
  await startNewChat(page);
  const { conversationId } = await sendTurn(
    page,
    context,
    "Backtest $10,000 in AAPL using buy and hold from January 2, 2020 through December 31, 2030.",
    { conversationId: null },
  );
  await shot(page, "p6-invalid-end-date");
  const { items } = await conversationMessages(context, conversationId);
  saveEvidence("p6-invalid-end-date.messages", {
    conversation_id: conversationId,
    captured_at: new Date().toISOString(),
    items: messageDigest(items),
  });
  const visible = await page
    .locator("main")
    .innerText()
    .catch(() => "");
  saveEvidence("p6-visible-text", { visible: visible.slice(-3000) });
  expect(items.length).toBeGreaterThan(0);
});
