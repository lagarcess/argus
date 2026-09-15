import { expect, test } from "bun:test";
import i18next from "i18next";
import { confirmationSupersedingHandlers } from "@/components/chat/confirmation-superseding";
import { nextExperimentAction } from "@/lib/chat-next-experiments";

test("the add-peer handler sends the row's identity to the endpoint", async () => {
  const originalFetch = globalThis.fetch;
  const mockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH;
  process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
  let requestBody: unknown;
  let requestUrl = "";
  globalThis.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    requestUrl = String(input);
    requestBody = JSON.parse(String(init?.body));
    return Response.json({ message: { id: "confirmation-message" } });
  }) as typeof fetch;
  try {
    const handlers = confirmationSupersedingHandlers(() => ({
      activeConversationId: () => "conversation",
      activeConfirmationId: () => "confirmation",
      hydrate: () => ({ messages: [] }),
      setMessages: () => {}, showToast: () => {}, hideToast: () => {},
      t: i18next.t,
    }));
    await handlers.handleAddConfirmationPeer(nextExperimentAction({
      kind: "research_add_peer:BTC", label: "Add Bitcoin", labelKey: "research",
      why: { code: "research_add_peer", params: { symbols: ["BTC"], peers: [
        {symbol: "BTC", name: "Bitcoin", asset_class: "crypto"},
      ] } },
    }));
    expect(requestUrl).toEndWith("/conversations/conversation/confirmations/confirmation/peer-assets");
    expect(requestBody).toEqual({ peers: [{symbol: "BTC", asset_class: "crypto"}] });
  } finally {
    globalThis.fetch = originalFetch;
    if (mockAuth === undefined) delete process.env.NEXT_PUBLIC_MOCK_AUTH;
    else process.env.NEXT_PUBLIC_MOCK_AUTH = mockAuth;
  }
});
