// #252 — behavior-level coverage for transcript navigation states.
//
// A new-key cache miss renders a neutral loading surface and never shows the
// previous conversation under the newly selected id; stale same-key content
// stays visible during silent revalidation.

import { describe, expect, test } from "bun:test";

import { applyTranscriptNavigationState } from "@/lib/chat-transcript-navigation";
import type { TranscriptNavigationState } from "@/lib/chat-transcript-session-cache";

type Snapshot = { messages: string[] };

function harness() {
  const calls: string[] = [];
  const deps = {
    applySnapshot: (snapshot: Snapshot) =>
      calls.push(`apply:${snapshot.messages.join(",")}`),
    clearToNeutralSurface: () => calls.push("clear"),
    setLoading: (loading: boolean) => calls.push(`loading:${loading}`),
    showLoadError: () => calls.push("load-error"),
    onMissingConversation: () => calls.push("missing"),
    onLoadFailure: () => calls.push("failure"),
    isMissingConversationError: (error: unknown) =>
      (error as { missing?: boolean })?.missing === true,
  };
  return { calls, deps };
}

function state(value: TranscriptNavigationState<Snapshot>) {
  return value;
}

describe("applyTranscriptNavigationState", () => {
  test("a new-key cache miss clears to a neutral loading surface", () => {
    const { calls, deps } = harness();
    applyTranscriptNavigationState(
      state({ phase: "loading", source: "cache_miss", snapshot: null }),
      deps,
    );
    expect(calls).toEqual(["clear", "loading:true"]);
  });

  test("stale same-key content stays visible while refreshing", () => {
    const { calls, deps } = harness();
    applyTranscriptNavigationState(
      state({
        phase: "refreshing",
        source: "stale_cache",
        snapshot: { messages: ["cached"] },
      }),
      deps,
    );
    expect(calls).toEqual(["apply:cached", "loading:false"]);
    expect(calls).not.toContain("clear");
  });

  test("ready snapshots render without an intermediate clear", () => {
    const { calls, deps } = harness();
    applyTranscriptNavigationState(
      state({
        phase: "ready",
        source: "network",
        snapshot: { messages: ["fresh"] },
      }),
      deps,
    );
    expect(calls).toEqual(["apply:fresh", "loading:false"]);
  });

  test("a failed silent refresh keeps the cached view and only toasts", () => {
    const { calls, deps } = harness();
    applyTranscriptNavigationState(
      state({
        phase: "error",
        source: "network",
        snapshot: { messages: ["cached"] },
        error: new Error("offline"),
      }),
      deps,
    );
    expect(calls).toEqual(["loading:false", "load-error"]);
  });

  test("a missing conversation prunes instead of rendering stale content", () => {
    const { calls, deps } = harness();
    applyTranscriptNavigationState(
      state({
        phase: "error",
        source: "network",
        snapshot: null,
        error: { missing: true },
      }),
      deps,
    );
    expect(calls).toEqual(["loading:false", "missing"]);
  });

  test("an unknown load failure renders the failure surface", () => {
    const { calls, deps } = harness();
    applyTranscriptNavigationState(
      state({
        phase: "error",
        source: "network",
        snapshot: null,
        error: new Error("boom"),
      }),
      deps,
    );
    expect(calls).toEqual(["loading:false", "failure"]);
  });
});
