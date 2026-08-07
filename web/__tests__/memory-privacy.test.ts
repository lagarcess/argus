import { afterEach, describe, expect, test } from "bun:test";
import {
  isConversationMemoryOptOut,
  setConversationMemoryOptOut,
} from "@/lib/memory-privacy";

type StorageOverrides = Partial<Pick<Storage, "setItem" | "getItem">>;

function installStorage(overrides: StorageOverrides = {}) {
  const store = new Map<string, string>();
  const storage = {
    getItem: (key: string) => store.get(key) ?? null,
    setItem: (key: string, value: string) => {
      store.set(key, value);
    },
    removeItem: (key: string) => {
      store.delete(key);
    },
    ...overrides,
  };
  (globalThis as { window?: unknown }).window = { localStorage: storage };
  return { store, storage };
}

afterEach(() => {
  delete (globalThis as { window?: unknown }).window;
});

describe("private chat opt-out state", () => {
  test("persists through storage on the happy path", () => {
    const { store } = installStorage();

    setConversationMemoryOptOut("conversation-happy", true);

    expect(isConversationMemoryOptOut("conversation-happy")).toBe(true);
    expect([...store.values()].join("")).toContain("conversation-happy");
  });

  test("stays authoritative in session when the storage write throws", () => {
    installStorage({
      setItem: () => {
        throw new Error("storage blocked");
      },
    });

    setConversationMemoryOptOut("conversation-blocked", true);

    // The toggle the user sees is the toggle the transport reads: opt-out
    // holds for this session even though nothing persisted.
    expect(isConversationMemoryOptOut("conversation-blocked")).toBe(true);
  });

  test("turning private chat off wins over stale persisted state", () => {
    const { store } = installStorage();
    setConversationMemoryOptOut("conversation-stale", true);
    expect([...store.values()].join("")).toContain("conversation-stale");

    // Storage becomes unwritable, so the persisted opt-out cannot be
    // removed; the session state must still win.
    (
      globalThis as unknown as { window: { localStorage: Storage } }
    ).window.localStorage.setItem = () => {
      throw new Error("storage blocked");
    };
    setConversationMemoryOptOut("conversation-stale", false);

    expect(isConversationMemoryOptOut("conversation-stale")).toBe(false);
    expect([...store.values()].join("")).toContain("conversation-stale");
  });

  test("session state works with no window at all", () => {
    delete (globalThis as { window?: unknown }).window;

    setConversationMemoryOptOut("conversation-ssr", true);

    expect(isConversationMemoryOptOut("conversation-ssr")).toBe(true);
  });
});
