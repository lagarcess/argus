import { describe, expect, test } from "bun:test";
import { createInstance } from "i18next";
import { renderToStaticMarkup } from "react-dom/server";
import { I18nextProvider } from "react-i18next";
import ChatMessage from "../components/chat/ChatMessage";
import { hydrateMessagesFromApi, messageStreamPresentation, standaloneStreamStatusVisible } from "../components/chat/chat-message-projection";
import { recoverPendingBreakdown } from "../components/chat/usePendingBreakdownRecovery";
import type { Message } from "../components/chat/types";
import type { ApiMessage } from "../lib/argus-api";
import { retirePendingBreakdown } from "../lib/pending-result-breakdown";
import en from "../public/locales/en/common.json";
import es from "../public/locales/es-419/common.json";
import fixture from "./fixtures/pending-result-breakdown.json";

const request = fixture.running as ApiMessage;
const turn = request.metadata!.agent_runtime_turn as Record<string, unknown>;
function completed(language: "en" | "es-419", status = "completed"): ApiMessage[] {
  const text = language === "en" ? "A rough ride ended ahead of the benchmark." : "Un recorrido con altibajos terminó por encima del referente.";
  return [fixture.started as ApiMessage, {
    id: crypto.randomUUID(), conversation_id: request.conversation_id, role: "assistant", content: text, created_at: request.created_at,
    metadata: { agent_runtime_turn: { ...turn, status, terminal: true },
      ...(status === "completed" ? { artifact_presentation_kind: "breakdown", result_readout_content: {
        schema_version: "result_readout/v1", surface: "breakdown", language, text,
      } } : { recovery: { code: "runtime_failure", retryable: true } }),
    },
  }];
}
const apply = (view: Awaited<ReturnType<typeof recoverPendingBreakdown>>, messages: Message[]) =>
  typeof view.messages === "function" ? view.messages(messages) : view.messages;

describe("a reloaded Breakdown follows its durable request", () => {
  for (const language of ["en", "es-419"] as const) {
    test(`saved accepted and running requests show one ${language} working frame without local stream state`, async () => {
      const i18n = createInstance();
      await i18n.init({ lng: language, resources: { en: { translation: en }, "es-419": { translation: es } } });
      for (const item of [fixture.accepted, fixture.running]) {
        const messages = hydrateMessagesFromApi([item as ApiMessage]).messages;
        const pending = messages.find((message) => message.pendingBreakdown);
        expect(pending?.id).toBe(`pending-breakdown:${request.id}`);
        const html = renderToStaticMarkup(<I18nextProvider i18n={i18n}>{messages.map((message, index) => <ChatMessage key={message.id} message={message}
          isStreaming={messageStreamPresentation(messages, message, index, false, false).isWorkingMessage} />)}
          {standaloneStreamStatusVisible(messages, false) && <span>{i18n.t("chat.status.working")}</span>}
        </I18nextProvider>);
        expect(html.split(i18n.t("chat.status.working"))).toHaveLength(2);
        expect(html).toContain('aria-busy="true"');
        expect(html).not.toContain(i18n.t("chat.result_readout.unavailable"));
      }
    });
    test(`existing lifecycle readback replaces ${language} pending with the saved answer`, async () => {
      const messages = hydrateMessagesFromApi([request]).messages;
      const pending = messages.find((message) => message.pendingBreakdown)!;
      const final = completed(language);
      const snapshots = [[request], final];
      const view = await recoverPendingBreakdown(messages, pending, async () => snapshots.shift()!, "Load failed", { followUpDelayMs: 0, wait: async () => undefined });
      const settled = apply(view, messages);
      expect(settled.some((message) => message.pendingBreakdown)).toBe(false);
      expect(settled.at(-1)?.resultReadoutContent?.language).toBe(language);
      expect(settled.at(-1)?.id).toBe(final[1].id);
    });
  }
  test.each(["recoverable_failed", "reconciled"])("terminal %s read removes the pending frame", async (status) => {
    const messages = hydrateMessagesFromApi([request]).messages;
    const pending = messages.find((message) => message.pendingBreakdown)!;
    const view = await recoverPendingBreakdown(messages, pending, async () => completed("en", status), "Load failed");
    expect(apply(view, messages).some((message) => message.pendingBreakdown)).toBe(false);
  });
  test("abandoned request and load failure cannot leave a permanent working frame", async () => {
    const messages = hydrateMessagesFromApi([request]).messages;
    const pending = messages.find((message) => message.pendingBreakdown)!;
    for (const load of [async () => [fixture.abandoned as ApiMessage], async (): Promise<ApiMessage[]> => { throw new Error("offline"); }]) {
      const view = await recoverPendingBreakdown(messages, pending, load, "Load failed");
      expect(apply(view, messages).some((message) => message.pendingBreakdown)).toBe(false);
    }
  });
  test("navigation cancellation leaves the current view alone", async () => {
    const messages = hydrateMessagesFromApi([request]).messages;
    const pending = messages.find((message) => message.pendingBreakdown)!;
    const controller = new AbortController();
    const view = await recoverPendingBreakdown(messages, pending, async () => [request], "Load failed", { signal: controller.signal, wait: async () => controller.abort() });
    expect(apply(view, messages)).toBe(messages);
  });
  test("unrelated actions, unowned state and terminal requests cannot invent a pending Breakdown", () => {
    for (const patch of [ { chat_action: { type: "run_backtest" } }, { agent_runtime_turn: { ...turn, turn_id: crypto.randomUUID() } },
      { agent_runtime_turn: { ...turn, terminal: true } }, { agent_runtime_turn: { ...turn, status: "completed" } },
      { agent_runtime_turn: { ...turn, request_id: null } } ]) {
      expect(hydrateMessagesFromApi([{ ...request, metadata: { ...request.metadata, ...patch } }]).messages.some((message) => message.pendingBreakdown)).toBe(false);
    }
  });
  test("an already committed assistant owns a mixed publication snapshot", () => {
    const final = completed("en");
    const messages = hydrateMessagesFromApi([request, final[1]]).messages;
    expect(messages.some((message) => message.pendingBreakdown)).toBe(false);
    expect(messages.at(-1)?.id).toBe(final[1].id);
  });
  test("a live terminal retires only its reloaded request and pending cannot flash a fallback behind a later message", () => {
    const messages = hydrateMessagesFromApi([request]).messages;
    const pending = messages.find((message) => message.pendingBreakdown)!;
    const later: Message = { id: crypto.randomUUID(), role: "ai", kind: "text", content: "A later answer" };
    expect(messageStreamPresentation([...messages, later], pending, messages.indexOf(pending), false, false).isWorkingMessage).toBe(true);
    expect(retirePendingBreakdown(messages, crypto.randomUUID())).toEqual(messages);
    expect(retirePendingBreakdown(messages, pending.pendingBreakdown!.requestId)).toEqual(messages.filter((message) => message.id !== pending.id));
  });
});
