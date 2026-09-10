import { readFileSync } from "node:fs";
import path from "node:path";
import { researchTurn, turnDocument } from "../../__tests__/fixtures/receipt-turns";
import type { ApiMessage } from "../../lib/argus-api";
import type { EvidenceReceipt, ReceiptCandidates } from "../../lib/evidence-receipts";
import { receiptDocumentSupported, type SelectedReceiptDocument } from "../../lib/public-receipt-turns";
import type { ToolResultCard } from "../../lib/tool-result-card";

const root = path.resolve(__dirname, "../../../docs/reports/evidence/registry");
const read = (name: string) => JSON.parse(readFileSync(path.join(root, name), "utf8"));
const backtests = read("backtest-cards.json") as Record<string, { card: ToolResultCard; receipt: SelectedReceiptDocument }>;
const receipts = read("tool-receipts.json") as Record<string, SelectedReceiptDocument>;
const cards = read("tool-cards.json") as Record<string, ToolResultCard>;
export const REGISTRY_RECEIPT_CONVERSATION = "conversation-alpha";

/** Compose frozen, sanitized API fixtures. No model, calculator or public writer runs. */
export function registryReceiptFixture(language: "en" | "es-419") {
  const dca = backtests[language];
  const payload = turnDocument(researchTurn, ...dca.receipt.turns, ...receipts[language].turns);
  if (!receiptDocumentSupported(payload)) throw new Error("Unsupported frozen receipt fixture");
  const ids = ["research-message", "dca-message", "echo-message"];
  const candidates: ReceiptCandidates = { max_turns: 4, items: payload.turns.map((turn, index) => ({
    message_id: ids[index], kind: turn.kind, eligible: true,
    question: turn.kind === "backtest" ? turn.idea_title : turn.question,
  })) };
  const metadata = [{ research_sources: researchTurn.sources }, { tool_result_cards: [dca.card] }, { tool_result_cards: [cards.initial, cards.sibling] }];
  const messages = candidates.items.flatMap((candidate, index): ApiMessage[] => [
    { id: `question-${index}`, role: "user", content: candidate.question ?? "", metadata: {}, conversation_id: REGISTRY_RECEIPT_CONVERSATION, created_at: researchTurn.retrieved_at },
    { id: candidate.message_id, role: "assistant", content: index === 0 ? researchTurn.answer : "", metadata: metadata[index], conversation_id: REGISTRY_RECEIPT_CONVERSATION, created_at: researchTurn.retrieved_at },
  ]);
  const publicId = `registry-mixed-frozen-${language}-receipt`;
  const receipt: EvidenceReceipt = {
    id: `owner-${publicId}`, public_id: publicId, path: `/r/${publicId}`, title: researchTurn.question,
    symbols: researchTurn.anchor_symbols, kind: "mixed", created_at: researchTurn.retrieved_at,
  };
  return { payload, candidates, messages, receipt, publicView: {
    public_id: publicId, status: "available", indexing: "noindex, nofollow", created_at: receipt.created_at, payload,
  } };
}
