import type { Page } from "@playwright/test";
import type { ArgusLanguage } from "../../lib/language-features";
import type { PublicReceiptDocument, PublicReceiptTurn } from "../../lib/public-receipt-turns";
import { backtestTurn } from "../../__tests__/fixtures/receipt-turns";
import { CONVERSATIONS, installMobileShellFixture } from "./mobile-shell-fixture";

export const SHARING_PUBLIC_ID = "sharing-fixture-public-link-604";
const stamp = "2026-09-14T12:00:00Z";
export function sharingFixture(language: ArgusLanguage) {
  const es = language === "es-419";
  const turns: PublicReceiptTurn[] = [
    { ...backtestTurn, owner_note: null, content_language: language, question: es ? "Prueba aportes mensuales de $250 en Apple." : "Test monthly $250 contributions to Apple.", answer: es ? "Los aportes crecieron un 18.4% en el período probado." : "The contributions grew 18.4% across the tested period." },
    { kind: "answer", question: es ? "¿Qué significan los costos?" : "What do the costs mean?", answer: es ? "La simulación incluye una comisión y el deslizamiento. No se movió dinero real." : "The simulation includes a fee and slippage. No real money moved.", content_language: language, framing: "answer_not_advice", provenance_mark: "tested_with_argus" },
  ];
  const messages = turns.flatMap((turn, index) => [
    { id: `sharing-question-${index}`, role: "user", content: turn.kind === "backtest" ? turn.question : turn.question, created_at: stamp, metadata: {} },
    { id: `sharing-answer-${index}`, role: "assistant", content: turn.kind === "calculation" ? turn.answer_text : turn.answer, created_at: stamp, metadata: index === 0 ? { result_card: {
      version: "argus_result/v1", run_id: "sharing-run", status: "completed", title: es ? "Aportes mensuales en Apple" : "Monthly Apple contributions", strategy_label: es ? "Aportes periódicos" : "Recurring contributions", symbols: ["AAPL"], benchmark_symbol: "SPY", asset_class: "equity", date_range: { start: "2024-01-02", end: "2024-12-31" }, config_snapshot: backtestTurn.fact_bank.config_snapshot,
      metrics: [{ key: "contribution_return_pct", label: es ? "Retorno" : "Return", value: "+18.4%" }, { key: "max_drawdown_pct", label: es ? "Caída máxima" : "Worst drop", value: "-6.2%" }],
    } } : {} },
  ]);
  // A confirmation is still visible in the conversation, but the API supplies no selection unit for it.
  messages.push({ id: "sharing-confirmation", role: "assistant", content: es ? "Listo para probar otra idea." : "Ready to test another idea.", created_at: stamp, metadata: {} });
  const items = turns.map((turn, index) => ({ message_id: `sharing-answer-${index}`, question: turn.question, kind: turn.kind, eligible: true }));
  return { turns, messages, items };
}

export async function installSharingFixture(page: Page, language: ArgusLanguage, theme: "dark" | "light" = "dark") {
  await installMobileShellFixture(page, { account: "registered", language, theme });
  const fixture = sharingFixture(language);
  await page.route( /\/api\/v1\/conversations\/[^/]+\/messages(?:\?|$)/, (route) => route.fulfill({ json: { items: fixture.messages, next_cursor: null } }));
  await page.route("**/public-excerpt-candidates", (route) => route.fulfill({ json: { items: fixture.items } }));
  const publications: unknown[] = [];
  await page.route("**/public-excerpt-preview", async (route) => {
    const request = route.request().postDataJSON();
    const turns = fixture.turns.filter((_, index) => request.message_ids.includes(`sharing-answer-${index}`)).map((turn, index) => ({ ...turn, owner_note: index === 0 ? request.owner_note : null }));
    const payload: PublicReceiptDocument = { schema_version: 2, kind: "turns", turns };
    await route.fulfill({ json: { payload, payload_digest: "seeded-preview-digest", kind: turns.length > 1 ? "mixed" : turns[0].kind, existing_receipt: null } });
  });
  await page.route("**/api/v1/conversations/*/public-excerpt", async (route) => {
    publications.push(route.request().postDataJSON());
    await route.fulfill({ json: { receipt: { id: "seeded-receipt", public_id: SHARING_PUBLIC_ID, path: `/r/${SHARING_PUBLIC_ID}`, title: fixture.turns[0].question, symbols: ["AAPL"], kind: "mixed", created_at: stamp } } });
  });
  return { publications, conversationId: CONVERSATIONS[0].id };
}
