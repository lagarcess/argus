// #252 — locally executable p50/p95 measurement protocol.
//
// Protocol (docs/reports/transcript-cache-profile.md): 8 conversations x 30
// messages; warm = fresh-cache revisit inside the freshness window; cold =
// cache-miss with an immediately-resolving loader (zero-network stand-in);
// 50 samples per scenario; p50/p95 over per-navigation wall time in the bun
// runtime. Laboratory numbers on the local machine — the deployed-browser
// profile remains the issue's external gate.

import { describe, expect, test } from "bun:test";

import { TranscriptSessionCache } from "@/lib/chat-transcript-session-cache";

type Snapshot = { messages: string[] };

const SAMPLES = 50;
const CONVERSATIONS = 8;

function transcript(index: number): Snapshot {
  return {
    messages: Array.from(
      { length: 30 },
      (_, line) => `conversation-${index} message-${line} ${"x".repeat(80)}`,
    ),
  };
}

function percentile(samples: number[], fraction: number): number {
  const sorted = [...samples].sort((a, b) => a - b);
  const index = Math.min(
    sorted.length - 1,
    Math.ceil(fraction * sorted.length) - 1,
  );
  return sorted[Math.max(0, index)];
}

async function navigateOnce(
  cache: TranscriptSessionCache<Snapshot>,
  conversation: number,
  loads: { count: number },
): Promise<number> {
  const startedAt = performance.now();
  let readyAt = performance.now();
  const handle = cache.navigate({
    userId: "profile-user",
    conversationId: `conversation-${conversation}`,
    load: async () => {
      loads.count += 1;
      return transcript(conversation);
    },
    onState: (state) => {
      if (state.phase === "ready") {
        readyAt = performance.now();
      }
    },
  });
  await handle.completion;
  return readyAt - startedAt;
}

describe("transcript cache local latency profile", () => {
  test("warm fresh revisits and cold misses meet the local budgets", async () => {
    const cache = new TranscriptSessionCache<Snapshot>({
      maxEntries: CONVERSATIONS,
      freshForMs: 60_000,
    });
    const loads = { count: 0 };

    const coldSamples: number[] = [];
    for (let sample = 0; sample < SAMPLES; sample += 1) {
      const conversation = sample % CONVERSATIONS;
      // Cold: evict by navigating a fresh cache each round-robin lap.
      if (conversation === 0 && sample > 0) {
        cache.clearAuthenticatedState();
      }
      coldSamples.push(await navigateOnce(cache, conversation, loads));
    }

    const warmup = new TranscriptSessionCache<Snapshot>({
      maxEntries: CONVERSATIONS,
      freshForMs: 60_000,
    });
    for (let conversation = 0; conversation < CONVERSATIONS; conversation += 1) {
      await navigateOnce(warmup, conversation, loads);
    }
    const warmSamples: number[] = [];
    const warmLoads = { count: 0 };
    for (let sample = 0; sample < SAMPLES; sample += 1) {
      warmSamples.push(
        await navigateOnce(warmup, sample % CONVERSATIONS, warmLoads),
      );
    }

    const profile = {
      cold_p50_ms: percentile(coldSamples, 0.5),
      cold_p95_ms: percentile(coldSamples, 0.95),
      warm_p50_ms: percentile(warmSamples, 0.5),
      warm_p95_ms: percentile(warmSamples, 0.95),
      warm_loader_calls: warmLoads.count,
      samples_per_scenario: SAMPLES,
    };
    console.log(`transcript-cache-profile ${JSON.stringify(profile)}`);

    // Fresh revisits never touch the loader and resolve synchronously.
    expect(warmLoads.count).toBe(0);
    expect(profile.warm_p95_ms).toBeLessThan(5);
    // Cold misses are loader-bound; the cache layer itself stays cheap.
    expect(profile.cold_p95_ms).toBeLessThan(25);
  });
});
