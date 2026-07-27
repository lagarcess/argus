import { afterEach, describe, expect, test } from "bun:test";

import { streamChatMessage } from "../lib/argus-api";
import type { ChatMention } from "../components/chat/types";

const identity: ChatMention = {
  id: "asset:equity:UNP",
  type: "asset",
  label: "Union Pacific Corp.",
  symbol: "UNP",
  asset_class: "equity",
  insert_text: "UNP",
};

function captureBody() {
  const sent: Array<Record<string, unknown>> = [];
  globalThis.fetch = (async (_url: string, init: RequestInit) => {
    sent.push(JSON.parse(String(init.body)));
    return {
      ok: true,
      body: new ReadableStream({
        start(controller) {
          controller.close();
        },
      }),
      headers: new Headers({ "X-Request-Id": "req-1" }),
    } as unknown as Response;
  }) as typeof globalThis.fetch;
  return sent;
}

/**
 * The request body is assembled before the stream is read, so an empty mock
 * stream terminating early is expected and irrelevant to what these assert.
 */
async function sendIgnoringStreamEnd(
  ...args: Parameters<typeof streamChatMessage>
) {
  try {
    await streamChatMessage(...args);
  } catch (error) {
    if ((error as { code?: string }).code !== "stream_interrupted") throw error;
  }
}

describe("chat stream carries mentions", () => {
  const originalFetch = globalThis.fetch;
  const originalMockAuth = process.env.NEXT_PUBLIC_MOCK_AUTH;

  afterEach(() => {
    globalThis.fetch = originalFetch;
    if (originalMockAuth === undefined) {
      delete process.env.NEXT_PUBLIC_MOCK_AUTH;
    } else {
      process.env.NEXT_PUBLIC_MOCK_AUTH = originalMockAuth;
    }
  });

  test("an action turn keeps the mentions its caller attached", async () => {
    // Live QA caught this: the body gated mentions on a string input, so a
    // discovery selection's resolver identity was silently dropped one layer
    // below the call site. Every unit test still passed.
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    const sent = captureBody();

    await sendIgnoringStreamEnd(
      "conversation-1",
      {
        type: "select_discovery_candidate",
        label: "Backtest UNP",
        payload: { symbol: "UNP", name: "Union Pacific Corp." },
      },
      "en",
      () => {},
      [identity],
    );

    expect(sent).toHaveLength(1);
    expect(sent[0].action).toBeDefined();
    expect(sent[0].mentions).toEqual([identity]);
  });

  test("an ordinary typed turn still carries its composer mentions", async () => {
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    const sent = captureBody();

    await sendIgnoringStreamEnd("conversation-1", "Backtest UNP", "en", () => {}, [
      identity,
    ]);

    expect(sent[0].message).toBe("Backtest UNP");
    expect(sent[0].mentions).toEqual([identity]);
  });

  test("no mentions means no mentions key, for either turn shape", async () => {
    process.env.NEXT_PUBLIC_MOCK_AUTH = "true";
    const sent = captureBody();

    await sendIgnoringStreamEnd("conversation-1", "plain text", "en", () => {}, []);
    await sendIgnoringStreamEnd(
      "conversation-1",
      { type: "run_backtest", label: "Run backtest" },
      "en",
      () => {},
      [],
    );

    expect(sent[0].mentions).toBeUndefined();
    expect(sent[1].mentions).toBeUndefined();
  });
});
